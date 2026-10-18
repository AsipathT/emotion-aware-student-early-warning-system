"""
Batch processing pipeline for behavioral trajectory classification.
Groups raw LMS behavior records and runs scale-free inference.
"""

from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from service.schemas import BehaviorRecord, TrajectoryRecord
from src.config import MIN_T
from src.inference import predict_trajectory


def classify_records(
    records: List[BehaviorRecord],
    bundle: Any,
    target_week: Optional[int] = None,
) -> Tuple[List[TrajectoryRecord], Dict[str, Any]]:
    """
    Groups behavior records by (pid, course_id), zero-fills missing weeks up to t,
    and predicts engagement trajectories.
    Ignored fields: login_count, session_minutes, video_* (reserved for future pilot data).
    Returns (records_sorted_by_pid_course, stats).
    """
    groups: Dict[Tuple[str, str], List[BehaviorRecord]] = {}
    for rec in records:
        key = (rec.pid, rec.course_id)
        if key not in groups:
            groups[key] = []
        groups[key].append(rec)

    received_groups = len(groups)
    classified = 0
    skipped = {
        "cold_start": 0,
        "no_row_for_week": 0,
        "error": 0,
    }
    label_counts: Dict[str, int] = {
        "declining": 0,
        "improving": 0,
        "stable": 0,
        "volatile": 0,
    }
    classified_records: List[TrajectoryRecord] = []

    for (pid, course_id), grp_records in groups.items():
        try:
            if target_week is not None:
                t = target_week
                has_target = any(r.week_index == target_week for r in grp_records)
                if not has_target:
                    skipped["no_row_for_week"] += 1
                    continue
            else:
                t = max(r.week_index for r in grp_records)

            if t < MIN_T:
                skipped["cold_start"] += 1
                continue

            # Build contiguous history 0..t
            by_week = {r.week_index: r for r in grp_records if r.week_index <= t}
            clicks: List[float] = []
            subs: List[float] = []
            delays: List[float] = []

            for w in range(t + 1):
                if w in by_week:
                    item = by_week[w]
                    clicks.append(float(item.clicks))
                    subs.append(float(item.submissions_count))
                    delays.append(float(item.avg_submission_delay_hours))
                else:
                    clicks.append(0.0)
                    subs.append(0.0)
                    delays.append(0.0)

            history = pd.DataFrame(
                {
                    "week": list(range(t + 1)),
                    "clicks": clicks,
                    "submissions_count": subs,
                    "avg_delay_hours": delays,
                }
            )

            res = predict_trajectory(history, bundle)
            if res is None:
                skipped["cold_start"] += 1
                continue

            traj = TrajectoryRecord(
                pid=pid,
                course_id=course_id,
                week_index=t,
                trajectory_label=res["trajectory_label"],
                confidence=res["confidence"],
                contributing_indicators=res["contributing_indicators"],
            )
            classified_records.append(traj)
            lbl = res["trajectory_label"]
            label_counts[lbl] = label_counts.get(lbl, 0) + 1
            classified += 1

        except Exception:
            skipped["error"] += 1
            continue

    classified_records.sort(key=lambda r: (r.pid, r.course_id))

    stats: Dict[str, Any] = {
        "received_groups": received_groups,
        "classified": classified,
        "skipped": skipped,
        "label_counts": label_counts,
    }

    return classified_records, stats

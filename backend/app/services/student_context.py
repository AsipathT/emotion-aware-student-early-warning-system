"""
backend/app/services/student_context.py

Feature 31: Student Context Assembly Service (Component 4 Context Construction).
Combines:
  - C1: Affective state & emotion scores (affective_weekly)
  - C2: Behavioral engagement trajectory & clickstream (engagement_trajectories, behavior_weekly)
  - C3: Dropout risk & causal modality vector (risk_assessments)
  - Interventions history: Past actions and outcomes (interventions, intervention_outcomes)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import collections as col
from app.services.affective_explain import (
    DISTRESS_LABELS,
    dominant_class,
    week_over_week_change,
)


async def get_analytics_snapshot(
    db: AsyncIOMotorDatabase,
    pid: str,
    course_id: str,
) -> Dict[str, Any]:
    """
    Returns a lightweight summary snapshot of the latest ML analytics for a student.

    Stable return shape (reused by F33 baseline snapshot and F35 follow-up):
    {
        "week_index": int,
        "risk_score": float | None,
        "risk_tier": str,
        "trajectory_label": str,
        "dominant_distress_class": str,
        "dominant_distress_score": float,
    }
    """
    clean_pid = str(pid).strip()
    cid = str(course_id).strip()

    # 1. Latest C3 Risk Assessment
    risk_doc = await db[col.RISK_ASSESSMENTS].find_one(
        {"pid": clean_pid, "course_id": cid},
        sort=[("week_index", -1)],
    )

    # 2. Latest C2 Engagement Trajectory
    traj_doc = await db[col.ENGAGEMENT_TRAJECTORIES].find_one(
        {"pid": clean_pid, "course_id": cid},
        sort=[("week_index", -1)],
    )

    # 3. Latest C1 Affective State
    aff_doc = await db[col.AFFECTIVE_WEEKLY].find_one(
        {"pid": clean_pid, "course_id": cid},
        sort=[("week_index", -1)],
    )

    # Determine highest observed week_index
    observed_weeks = [
        d["week_index"]
        for d in (risk_doc, traj_doc, aff_doc)
        if d and d.get("week_index") is not None
    ]
    max_week = max(observed_weeks) if observed_weeks else 0

    risk_score = round(float(risk_doc["risk_score"]), 4) if risk_doc and "risk_score" in risk_doc else None
    risk_tier = str(risk_doc.get("risk_tier") or "unknown") if risk_doc else "unknown"
    traj_label = str(traj_doc.get("trajectory_label") or "unknown") if traj_doc else "unknown"

    dom_cls, dom_score = ("none", 0.0)
    if aff_doc and aff_doc.get("emotion_scores"):
        dom_cls, dom_score = dominant_class(aff_doc["emotion_scores"])

    return {
        "week_index": max_week,
        "risk_score": risk_score,
        "risk_tier": risk_tier,
        "trajectory_label": traj_label,
        "dominant_distress_class": dom_cls,
        "dominant_distress_score": dom_score,
    }


def _determine_dominant_modality(modality_contributions: Optional[Dict[str, float]]) -> Tuple[str, float]:
    """Finds the highest-weighted modality in C3 ModalityContributions (affective, behavioral, academic)."""
    if not modality_contributions:
        return ("unknown", 0.0)
    modalities = ["affective", "behavioral", "academic"]
    best_mod = max(modalities, key=lambda m: float(modality_contributions.get(m, 0.0)))
    best_val = round(float(modality_contributions.get(best_mod, 0.0)), 4)
    return (best_mod, best_val)


def _build_summary_lines(
    c1: Dict[str, Any],
    c2: Dict[str, Any],
    c3: Dict[str, Any],
    behaviour: Dict[str, Any],
    interventions: Dict[str, Any],
) -> List[str]:
    """Builds 3-6 plain-language explanatory diagnostic bullet lines from deterministic templates (no LLM)."""
    lines: List[str] = []

    # Bullet 1: C3 Risk & Causal Modality
    c3_latest = c3.get("latest")
    if c3_latest:
        tier = str(c3_latest.get("risk_tier", "unknown")).upper()
        score = float(c3_latest.get("risk_score", 0.0))
        dom_mod, mod_val = _determine_dominant_modality(c3_latest.get("modality_contributions"))
        lines.append(
            f"Overall dropout risk is {tier} ({score:.2f}); {dom_mod} signals contribute most to the risk ({mod_val:.2f})."
        )
    else:
        lines.append("No multimodal risk assessment recorded yet.")

    # Bullet 2: C2 Engagement Trajectory
    c2_latest = c2.get("latest")
    if c2_latest:
        label = str(c2_latest.get("trajectory_label", "unknown")).capitalize()
        conf = float(c2_latest.get("confidence", 0.0))
        indicators = c2_latest.get("contributing_indicators", [])
        ind_str = ", ".join(f"'{i}'" for i in indicators[:3]) if indicators else "routine activity patterns"
        lines.append(
            f"Engagement trajectory is {label} ({conf * 100:.0f}% confidence) based on {ind_str}."
        )

    # Bullet 3: C1 Affective State & Change
    c1_latest = c1.get("latest")
    if c1_latest:
        dom_cls = c1_latest.get("dominant_class", "none")
        dom_score = float(c1_latest.get("dominant_score", 0.0))
        cls_name = DISTRESS_LABELS.get(dom_cls, dom_cls.replace("_", " ").title())
        stress_label = str(c1_latest.get("stress_label", "moderate")).capitalize()

        change_info = ""
        c1_change = c1.get("change_vs_previous") or {}
        if dom_cls in c1_change:
            delta = float(c1_change[dom_cls])
            if delta > 0.01:
                change_info = f", up {delta:.2f} from previous week"
            elif delta < -0.01:
                change_info = f", down {abs(delta):.2f} from previous week"

        lines.append(
            f"Primary affective signal: {cls_name} at {dom_score:.2f}{change_info} (classified as {stress_label} distress)."
        )

    # Bullet 4: Behavioral telemetry summary
    b_history = behaviour.get("history") or []
    if b_history:
        latest_b = b_history[-1]
        clicks = latest_b.get("clicks", 0)
        delay = float(latest_b.get("avg_submission_delay_hours", 0.0))
        delay_str = f"{delay:+.1f}h deadline offset" if delay != 0 else "on-time submissions"
        lines.append(
            f"LMS behavioral telemetry for Week {latest_b.get('week_index', 0) + 1}: {clicks} interaction clicks and {delay_str}."
        )

    # Bullet 5: Interventions history
    int_history = interventions.get("history") or []
    if int_history:
        lines.append(
            f"Intervention record: {len(int_history)} past support action(s) logged on file."
        )

    return lines


async def build_student_context(
    db: AsyncIOMotorDatabase,
    pid: str,
    course_id: str,
) -> Dict[str, Any]:
    """
    Constructs the comprehensive Component 4 student context representation.
    Synthesizes C1 affective distress, C2 engagement trajectories, C3 multimodal risk,
    LMS behavioral logs, and past intervention outcomes.
    """
    clean_pid = str(pid).strip()
    cid = str(course_id).strip()

    # ── 1. C1 Affective State ─────────────────────────────────────────────────
    aff_cursor = (
        db[col.AFFECTIVE_WEEKLY]
        .find({"pid": clean_pid, "course_id": cid})
        .sort("week_index", 1)
    )
    aff_docs = await aff_cursor.to_list(length=50)

    c1_data: Dict[str, Any] = {"latest": None, "change_vs_previous": {}, "history": []}
    if aff_docs:
        latest_aff = aff_docs[-1]
        prev_aff = aff_docs[-2] if len(aff_docs) > 1 else None

        cur_scores = {k: round(float(v), 4) for k, v in (latest_aff.get("emotion_scores") or {}).items()}
        prev_scores = {k: round(float(v), 4) for k, v in (prev_aff.get("emotion_scores") or {}).items()} if prev_aff else None

        dom_cls, dom_score = dominant_class(cur_scores)
        deltas = week_over_week_change(prev_scores, cur_scores)

        c1_data["latest"] = {
            "week_index": int(latest_aff["week_index"]),
            "emotion_scores": cur_scores,
            "dominant_class": dom_cls,
            "dominant_score": dom_score,
            "stress_label": str(latest_aff.get("stress_label") or "moderate"),
            "confidence": round(float(latest_aff.get("confidence") or 0.0), 4),
            "top_drivers": latest_aff.get("top_drivers") or [],
            "message_count": int(latest_aff.get("message_count") or 0),
        }
        c1_data["change_vs_previous"] = deltas

        for doc in aff_docs[-8:]:
            d_cls, d_score = dominant_class(doc.get("emotion_scores"))
            c1_data["history"].append({
                "week_index": int(doc["week_index"]),
                "dominant_class": d_cls,
                "dominant_score": d_score,
                "stress_label": str(doc.get("stress_label") or "moderate"),
            })

    # ── 2. C2 Engagement Trajectory ───────────────────────────────────────────
    traj_cursor = (
        db[col.ENGAGEMENT_TRAJECTORIES]
        .find({"pid": clean_pid, "course_id": cid})
        .sort("week_index", 1)
    )
    traj_docs = await traj_cursor.to_list(length=50)

    c2_data: Dict[str, Any] = {"latest": None, "history": []}
    if traj_docs:
        latest_traj = traj_docs[-1]
        c2_data["latest"] = {
            "week_index": int(latest_traj["week_index"]),
            "trajectory_label": str(latest_traj.get("trajectory_label") or "unknown"),
            "confidence": round(float(latest_traj.get("confidence") or 0.0), 4),
            "contributing_indicators": [str(i) for i in latest_traj.get("contributing_indicators") or []],
        }
        for doc in traj_docs[-8:]:
            c2_data["history"].append({
                "week_index": int(doc["week_index"]),
                "trajectory_label": str(doc.get("trajectory_label") or "unknown"),
                "confidence": round(float(doc.get("confidence") or 0.0), 4),
            })

    # ── 3. C3 Multimodal Risk Prediction ──────────────────────────────────────
    risk_cursor = (
        db[col.RISK_ASSESSMENTS]
        .find({"pid": clean_pid, "course_id": cid})
        .sort("week_index", 1)
    )
    risk_docs = await risk_cursor.to_list(length=50)

    c3_data: Dict[str, Any] = {"latest": None, "history": []}
    if risk_docs:
        latest_risk = risk_docs[-1]
        mod_contrib = {
            k: round(float(v), 4)
            for k, v in (latest_risk.get("modality_contributions") or {}).items()
        }
        dom_mod, _ = _determine_dominant_modality(mod_contrib)

        c3_data["latest"] = {
            "week_index": int(latest_risk["week_index"]),
            "risk_score": round(float(latest_risk.get("risk_score") or 0.0), 4),
            "risk_tier": str(latest_risk.get("risk_tier") or "unknown"),
            "modality_contributions": mod_contrib,
            "dominant_modality": dom_mod,
            "dominant_modality_value": mod_contrib.get(dom_mod, 0.0),
            "top_drivers": [str(d) for d in latest_risk.get("top_drivers") or []],
        }
        for doc in risk_docs[-10:]:
            c3_data["history"].append({
                "week_index": int(doc["week_index"]),
                "risk_score": round(float(doc.get("risk_score") or 0.0), 4),
                "risk_tier": str(doc.get("risk_tier") or "unknown"),
            })

    # ── 4. Behavioral Telemetry (Last 4 Weeks) ────────────────────────────────
    beh_cursor = (
        db[col.BEHAVIOR_WEEKLY]
        .find({"pid": clean_pid, "course_id": cid})
        .sort("week_index", 1)
    )
    beh_docs = await beh_cursor.to_list(length=50)

    behaviour_data: Dict[str, Any] = {"history": []}
    if beh_docs:
        for doc in beh_docs[-4:]:
            behaviour_data["history"].append({
                "week_index": int(doc["week_index"]),
                "login_count": int(doc.get("login_count") or 0),
                "session_minutes": round(float(doc.get("session_minutes") or 0.0), 1),
                "clicks": int(doc.get("clicks") or 0),
                "video_play_count": int(doc.get("video_play_count") or 0),
                "video_pause_count": int(doc.get("video_pause_count") or 0),
                "video_completion_pct": round(float(doc.get("video_completion_pct") or 0.0), 1),
                "submissions_count": int(doc.get("submissions_count") or 0),
                "avg_submission_delay_hours": round(float(doc.get("avg_submission_delay_hours") or 0.0), 2),
            })

    # ── 5. Interventions & Outcomes History ───────────────────────────────────
    int_history: List[Dict[str, Any]] = []
    try:
        int_cursor = (
            db[col.INTERVENTIONS]
            .find({"pid": clean_pid})
            .sort("created_at", -1)
            .limit(20)
        )
        int_docs = await int_cursor.to_list(length=20)
        for doc in int_docs:
            rec_id = doc.get("recommendation_id")
            outcome_data = None
            if rec_id:
                outcome_doc = await db[col.INTERVENTION_OUTCOMES].find_one({"recommendation_id": rec_id})
                if outcome_doc:
                    outcome_data = {
                        "decision": str(outcome_doc.get("decision") or "unknown"),
                        "completed": bool(outcome_doc.get("completed", False)),
                        "observed_change": outcome_doc.get("observed_change"),
                        "notes_present": bool(outcome_doc.get("notes_present", False)),
                    }

            int_history.append({
                "intervention_id": str(doc.get("intervention_id") or doc.get("_id")),
                "recommendation_id": rec_id,
                "course_id": str(doc.get("course_id") or cid),
                "intervention_type": str(doc.get("intervention_type") or "Advisor Outreach"),
                "status": str(doc.get("status") or "proposed"),
                "created_at": doc.get("created_at"),
                "outcome": outcome_data,
            })
    except Exception:
        # Tolerates missing collections gracefully
        int_history = []

    # ── 6. Data Freshness & Latest Common Week ────────────────────────────────
    latest_weeks = {
        "c1": c1_data["latest"]["week_index"] if c1_data["latest"] else None,
        "c2": c2_data["latest"]["week_index"] if c2_data["latest"] else None,
        "c3": c3_data["latest"]["week_index"] if c3_data["latest"] else None,
        "behaviour": behaviour_data["history"][-1]["week_index"] if behaviour_data["history"] else None,
    }

    available_weeks = [w for w in latest_weeks.values() if w is not None]
    max_observed_week = max(available_weeks) if available_weeks else 0
    latest_common_week = min(available_weeks) if available_weeks else 0

    lagging_sources: List[Dict[str, Any]] = []
    for source_name, w in latest_weeks.items():
        if w is None:
            lagging_sources.append({"source": source_name, "status": "missing", "lag_weeks": None})
        elif w < max_observed_week:
            lagging_sources.append({"source": source_name, "status": "lagging", "lag_weeks": max_observed_week - w})

    freshness_info = {
        "c1_week": latest_weeks["c1"],
        "c2_week": latest_weeks["c2"],
        "c3_week": latest_weeks["c3"],
        "behaviour_week": latest_weeks["behaviour"],
        "max_observed_week": max_observed_week,
        "lagging_sources": lagging_sources,
    }

    # ── 7. Explanatory Summary Bullets ────────────────────────────────────────
    interventions_dict = {"history": int_history}
    summary_lines = _build_summary_lines(c1_data, c2_data, c3_data, behaviour_data, interventions_dict)

    return {
        "identity": {"pid": clean_pid},
        "c1": c1_data,
        "c2": c2_data,
        "c3": c3_data,
        "behaviour": behaviour_data,
        "interventions": interventions_dict,
        "latest_common_week": latest_common_week,
        "data_freshness": freshness_info,
        "summary_lines": summary_lines,
    }

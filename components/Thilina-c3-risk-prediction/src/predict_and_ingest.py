"""
components/Thilina-c3-risk-prediction/src/predict_and_ingest.py

Live Pipeline Inference & Ingestion Runner for Component 3.
Fetches weekly data from LMS and upstream ML components:
  - C1 Affective: GET /api/v1/export/affective
  - C2 Trajectory: GET /api/v1/export/trajectory
  - LMS Behavior:  GET /api/v1/export/behavior
  - LMS Academic:  GET /api/v1/export/academic

Fuses multimodal features, performs imputation on missing / unobserved signals,
computes risk probabilities and SHAP modality contributions, and transmits
contract-compliant RiskAssessment records back to the LMS platform:
  - POST /api/v1/ingest/risk
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, List, Optional
import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Ensure component root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.model import MultimodalRiskModel, ALL_FEATURE_COLS
from src.ingest_client import C3IngestClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("c3.predict_and_ingest")
load_dotenv()


class MultimodalInferencePipeline:
    def __init__(self, platform_url: Optional[str] = None, component_key: Optional[str] = None, model_dir: Optional[str] = None):
        self.platform_url = (platform_url or os.getenv("PLATFORM_URL", "http://localhost:8000")).rstrip("/")
        self.component_key = component_key or os.getenv("C3_COMPONENT_KEY", "")
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.model_dir = model_dir or os.path.join(self.base_dir, "models")

        logger.info(f"Loading C3 model artifacts from {self.model_dir}...")
        self.model = MultimodalRiskModel.load(self.model_dir)
        self.ingest_client = C3IngestClient(platform_url=self.platform_url, component_key=self.component_key)

    def _fetch_export(self, path: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetches paginated export records from the LMS platform."""
        headers = {"X-Component-Key": self.component_key}
        url = f"{self.platform_url}{path}"
        all_records = []
        page = 1
        page_size = 200

        while True:
            q_params = dict(params)
            q_params["page"] = page
            q_params["page_size"] = page_size

            resp = requests.get(url, headers=headers, params=q_params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()

            items = payload.get("data", [])
            all_records.extend(items)

            total = payload.get("total", len(all_records))
            if len(all_records) >= total or not items:
                break
            page += 1

        return all_records

    def run(self, course_id: Optional[str] = None, week_index: Optional[int] = None, dry_run: bool = False) -> Dict[str, Any]:
        """
        Executes end-to-end multimodal inference for a given course and week.
        """
        query_params = {}
        if course_id:
            query_params["course_id"] = course_id
        if week_index is not None:
            query_params["week_from"] = week_index
            query_params["week_to"] = week_index

        logger.info(f"Fetching multimodal records for course_id={course_id}, week_index={week_index}...")

        # 1. Fetch upstream exports
        try:
            aff_records = self._fetch_export("/api/v1/export/affective", query_params)
            logger.info(f"Retrieved {len(aff_records)} affective records (C1)")
        except Exception as e:
            logger.warning(f"Could not retrieve affective records: {e}")
            aff_records = []

        try:
            traj_records = self._fetch_export("/api/v1/export/trajectory", query_params)
            logger.info(f"Retrieved {len(traj_records)} trajectory records (C2)")
        except Exception as e:
            logger.warning(f"Could not retrieve trajectory records: {e}")
            traj_records = []

        try:
            beh_records = self._fetch_export("/api/v1/export/behavior", query_params)
            logger.info(f"Retrieved {len(beh_records)} behavior records (LMS)")
        except Exception as e:
            logger.warning(f"Could not retrieve behavior records: {e}")
            beh_records = []

        try:
            acad_records = self._fetch_export("/api/v1/export/academic", query_params)
            logger.info(f"Retrieved {len(acad_records)} academic records (LMS)")
        except Exception as e:
            logger.warning(f"Could not retrieve academic records: {e}")
            acad_records = []

        # 2. Extract distinct student keys (pid, course_id, week_index)
        all_keys = set()
        for r in beh_records + acad_records + aff_records + traj_records:
            all_keys.add((str(r["pid"]), str(r["course_id"]), int(r["week_index"])))

        if not all_keys:
            logger.info("No multimodal records found for the specified filters.")
            return {"status": "empty", "records_processed": 0}

        logger.info(f"Identified {len(all_keys)} distinct student-course-week instances to assess.")

        # Index records for fast O(1) lookup
        aff_by_key = {(r["pid"], r["course_id"], r["week_index"]): r for r in aff_records}
        traj_by_key = {(r["pid"], r["course_id"], r["week_index"]): r for r in traj_records}
        beh_by_key = {(r["pid"], r["course_id"], r["week_index"]): r for r in beh_records}
        acad_by_key = {(r["pid"], r["course_id"], r["week_index"]): r for r in acad_records}

        # 3. Assemble feature rows
        rows = []
        meta_keys = []
        for pid, c_id, w_idx in all_keys:
            k = (pid, c_id, w_idx)
            aff = aff_by_key.get(k, {})
            traj = traj_by_key.get(k, {})
            beh = beh_by_key.get(k, {})
            acad = acad_by_key.get(k, {})

            # Affective features (handle missing messages / unobserved affect)
            msg_count = int(aff.get("message_count", 0))
            stress_lbl = str(aff.get("stress_label", "no_data" if msg_count == 0 else "none"))
            aff_conf = float(aff.get("confidence", 0.0 if msg_count == 0 else 0.5))
            emotions = aff.get("emotion_scores") or {}

            # Behavioral trajectory features (handle weeks 0-2 missingness)
            traj_lbl = str(traj.get("trajectory_label", "unobserved"))
            beh_conf = float(traj.get("confidence", 0.5))

            # LMS Academic features
            quiz_scores = acad.get("quiz_scores", [])
            avg_quiz = float(np.mean(quiz_scores)) if quiz_scores else np.nan

            row = {
                # Identifiers
                "pid": pid,
                "course_id": c_id,
                "week_index": w_idx,

                # Affective
                "message_count": msg_count,
                "exam_anxiety": emotions.get("exam_anxiety", np.nan),
                "conceptual_confusion": emotions.get("conceptual_confusion", np.nan),
                "academic_helplessness": emotions.get("academic_helplessness", np.nan),
                "course_frustration": emotions.get("course_frustration", np.nan),
                "motivation_erosion": emotions.get("motivation_erosion", np.nan),
                "stress_label": stress_lbl,
                "confidence": aff_conf,

                # Behavioral (LMS + Trajectory)
                "trajectory_label": traj_lbl,
                "login_count": beh.get("login_count", np.nan),
                "session_minutes": beh.get("session_minutes", np.nan),
                "clicks": beh.get("clicks", np.nan),
                "video_play_count": beh.get("video_play_count", np.nan),
                "video_pause_count": beh.get("video_pause_count", np.nan),
                "video_rewind_count": beh.get("video_rewind_count", np.nan),
                "video_skip_count": beh.get("video_skip_count", np.nan),
                "video_completion_pct": beh.get("video_completion_pct", np.nan),
                "submissions_count": beh.get("submissions_count", np.nan),
                "avg_submission_delay_hours": beh.get("avg_submission_delay_hours", np.nan),

                # Academic
                "attendance_pct": acad.get("attendance_pct", np.nan),
                "ca_marks": acad.get("ca_marks", np.nan),
                "midterm_mark": acad.get("midterm_mark", np.nan),
                "quiz_score": avg_quiz,
                "submission_delay_hours": acad.get("submission_delay_hours", np.nan),
            }
            rows.append(row)
            meta_keys.append((pid, c_id, w_idx))

        feature_df = pd.DataFrame(rows)

        # 4. Predict risk and SHAP attribution
        logger.info(f"Executing multimodal model inference and SHAP attribution on {len(feature_df)} rows...")
        predictions = self.model.predict_risk(feature_df)

        # 5. Format into contract-compliant RiskAssessment records
        risk_assessments = []
        observation_count = 0
        active_prediction_count = 0

        for (pid, c_id, w_idx), pred in zip(meta_keys, predictions):
            if w_idx < 5:
                observation_count += 1
            else:
                active_prediction_count += 1

            record = {
                "pid": pid,
                "course_id": c_id,
                "week_index": w_idx,
                "risk_score": pred["risk_score"],
                "risk_tier": pred["risk_tier"],
                "modality_contributions": pred["modality_contributions"],
                "top_drivers": pred["top_drivers"],
            }
            risk_assessments.append(record)

        logger.info(
            f"Successfully constructed {len(risk_assessments)} risk assessments "
            f"({active_prediction_count} active predictions [weeks >= 5], "
            f"{observation_count} observation baseline [weeks 0-4])."
        )

        # 6. Ingest back to LMS
        logger.info(f"Sending risk assessments to {self.platform_url}/api/v1/ingest/risk (dry_run={dry_run})...")
        ingest_res = self.ingest_client.send_assessments(risk_assessments, dry_run=dry_run)
        logger.info(f"Ingestion response: {ingest_res}")

        return {
            "status": "success",
            "records_evaluated": len(risk_assessments),
            "ingest_result": ingest_res,
            "sample_assessment": risk_assessments[0] if risk_assessments else None,
        }


def main():
    parser = argparse.ArgumentParser(description="Component 3 Live Inference & Ingestion Runner")
    parser.add_argument("--course-id", type=str, default=None, help="Target course ID")
    parser.add_argument("--week-index", type=int, default=None, help="Target academic week index")
    parser.add_argument("--dry-run", action="store_true", help="Perform contract validation without DB commit")
    args = parser.parse_args()

    pipeline = MultimodalInferencePipeline()
    result = pipeline.run(course_id=args.course_id, week_index=args.week_index, dry_run=args.dry_run)
    print("\n" + "=" * 60)
    print("  C3 INFERENCE & INGESTION PIPELINE EXECUTION SUMMARY")
    print("=" * 60)
    import pprint
    pprint.pprint(result)
    print("=" * 60)


if __name__ == "__main__":
    main()

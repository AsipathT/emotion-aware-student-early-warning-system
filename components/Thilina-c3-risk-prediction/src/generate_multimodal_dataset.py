"""
components/Thilina-c3-risk-prediction/src/generate_multimodal_dataset.py

Contract-Driven Multimodal Dataset Generator for Component 3 (Multimodal Risk Prediction).
Synthesizes weekly student records combining:
  1. Affective signals (C1 contract: 5 distress dimensions, dominant stress, confidence)
  2. Behavioral velocity (C2 contract: trajectory label, clicks, video watch mins, active days)
  3. Academic indicators (LMS continuous assessment, quiz scores, submission lateness, attendance)
  4. Ground truth dropout outcome and risk tier
"""

import os
import argparse
import random
import numpy as np
import pandas as pd


def generate_multimodal_data(
    num_students: int = 400,
    num_weeks: int = 12,
    course_codes: list = None,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generates longitudinal weekly multimodal data for early warning risk prediction.
    Correlates student disengagement across emotions, behaviors, and academic metrics.
    """
    np.random.seed(seed)
    random.seed(seed)

    if course_codes is None:
        course_codes = ["CS101", "CS102", "ENG201", "MATH101"]

    records = []

    for s_idx in range(num_students):
        pid = f"STU_{hash(f'student_{s_idx}') & 0xFFFFFFFF:08x}"
        course = random.choice(course_codes)

        # Baseline student latent traits (0.0 to 1.0)
        # academic_ability: higher means better grades
        # resilience: higher means less prone to academic panic/distress
        # diligence: higher means more consistent LMS engagement and on-time submissions
        academic_ability = np.clip(np.random.normal(0.60, 0.20), 0.1, 0.95)
        resilience = np.clip(np.random.normal(0.55, 0.22), 0.05, 0.95)
        diligence = np.clip(np.random.normal(0.65, 0.20), 0.1, 0.95)

        # Longitudinal trend modifier: simulates a student encountering a shock or disengagement halfway
        is_at_risk_trajectory = np.random.rand() < 0.28  # ~28% of students experience significant risk
        shock_week = random.randint(3, 7) if is_at_risk_trajectory else 999

        current_motivation = 0.85
        current_confusion = 0.15
        current_anxiety = 0.20

        for week in range(num_weeks):
            # Apply shock/drift if past shock week
            if week >= shock_week:
                decay_factor = 0.85 ** (week - shock_week + 1)
                academic_ability_week = academic_ability * decay_factor
                diligence_week = diligence * (0.80 ** (week - shock_week + 1))
                current_motivation = max(0.05, current_motivation - np.random.uniform(0.10, 0.18))
                current_confusion = min(0.95, current_confusion + np.random.uniform(0.12, 0.22))
                current_anxiety = min(0.95, current_anxiety + np.random.uniform(0.08, 0.18))
            else:
                academic_ability_week = academic_ability + np.random.normal(0, 0.03)
                diligence_week = diligence + np.random.normal(0, 0.03)
                current_motivation = np.clip(current_motivation + np.random.normal(0, 0.02), 0.3, 0.95)
                current_confusion = np.clip(current_confusion + np.random.normal(0, 0.02), 0.05, 0.5)
                current_anxiety = np.clip(current_anxiety + np.random.normal(0, 0.03), 0.05, 0.6)

            # ── 1. Academic Performance Features ─────────────────────────────
            quiz_score = np.clip(academic_ability_week * 100 + np.random.normal(0, 6), 0.0, 100.0)
            assignment_score = np.clip(
                (academic_ability_week * 0.7 + diligence_week * 0.3) * 100 + np.random.normal(0, 7),
                0.0,
                100.0,
            )

            # Late submission: negative means submitted early, positive means late
            submission_delay_days = np.round(
                np.clip((1.0 - diligence_week) * 7 - np.random.uniform(0, 3), -5.0, 14.0), 1
            )
            attendance_pct = np.clip(diligence_week * 100 + np.random.normal(0, 5), 10.0, 100.0)
            cumulative_grade = np.round((quiz_score * 0.4 + assignment_score * 0.6), 1)

            # ── 2. Behavioral Engagement Features (C2) ────────────────────────
            base_clicks = int(np.clip(diligence_week * 180 + np.random.normal(0, 25), 5, 350))
            active_days = int(np.clip(round(diligence_week * 6 + np.random.normal(0, 1)), 0, 7))
            video_watch_mins = np.round(np.clip(diligence_week * 60 + np.random.normal(0, 10), 0.0, 120.0), 1)
            forum_posts = max(0, int(np.random.poisson(lam=max(0.2, diligence_week * 2.5))))

            # Determine C2 Trajectory Label
            if week >= shock_week + 1:
                trajectory_label = "declining"
            elif is_at_risk_trajectory and week >= shock_week:
                trajectory_label = "volatile"
            elif diligence_week > 0.75:
                trajectory_label = "improving" if week > 3 else "stable"
            else:
                trajectory_label = "stable"

            trajectory_conf = np.round(np.random.uniform(0.72, 0.96), 2)

            # ── 3. Affective Distress Features (C1) ───────────────────────────
            exam_anxiety = float(np.round(np.clip(current_anxiety + (1.0 - resilience) * 0.25, 0.02, 0.98), 3))
            conceptual_confusion = float(np.round(np.clip(current_confusion + (1.0 - academic_ability_week) * 0.3, 0.02, 0.98), 3))
            academic_helplessness = float(np.round(np.clip((1.0 - resilience) * current_confusion * 1.2, 0.01, 0.95), 3))
            course_frustration = float(np.round(np.clip(conceptual_confusion * 0.7 + np.random.normal(0, 0.05), 0.01, 0.92), 3))
            motivation_erosion = float(np.round(np.clip(1.0 - current_motivation, 0.02, 0.95), 3))

            emotions = {
                "exam_anxiety": exam_anxiety,
                "conceptual_confusion": conceptual_confusion,
                "academic_helplessness": academic_helplessness,
                "course_frustration": course_frustration,
                "motivation_erosion": motivation_erosion,
            }
            dominant_stress = max(emotions, key=emotions.get)
            if max(emotions.values()) < 0.25:
                dominant_stress = "neutral"

            affective_conf = float(np.round(np.random.uniform(0.70, 0.95), 2))

            # ── 4. Ground Truth Risk Target ───────────────────────────────────
            # True composite risk score combines all three dimensions:
            # 40% Academic + 35% Behavioral + 25% Affective
            acad_risk = 1.0 - (cumulative_grade / 100.0)
            behav_risk = 1.0 - min(1.0, (base_clicks / 150.0) * 0.6 + (active_days / 5.0) * 0.4)
            affect_risk = (exam_anxiety * 0.25 + conceptual_confusion * 0.35 + academic_helplessness * 0.40)

            composite_risk = float(
                np.clip(0.40 * acad_risk + 0.35 * behav_risk + 0.25 * affect_risk + np.random.normal(0, 0.04), 0.0, 1.0)
            )

            # Assign risk tier
            if composite_risk >= 0.85:
                risk_tier = "critical"
                dropout = 1
            elif composite_risk >= 0.60:
                risk_tier = "high"
                dropout = 1 if (week >= num_weeks - 2 and np.random.rand() < 0.75) else 0
            elif composite_risk >= 0.30:
                risk_tier = "medium"
                dropout = 0
            else:
                risk_tier = "low"
                dropout = 0

            records.append({
                "pid": pid,
                "course_id": course,
                "week_index": week,
                # Academic Modality
                "quiz_avg_score": round(quiz_score, 1),
                "assignment_avg_score": round(assignment_score, 1),
                "assignment_submission_delay_days": submission_delay_days,
                "attendance_percentage": round(attendance_pct, 1),
                "cumulative_grade": cumulative_grade,
                # Behavioral Modality
                "weekly_clicks": base_clicks,
                "active_days_count": active_days,
                "video_watch_minutes": video_watch_mins,
                "forum_post_count": forum_posts,
                "trajectory_label": trajectory_label,
                "trajectory_confidence": trajectory_conf,
                # Affective Modality
                "exam_anxiety": exam_anxiety,
                "conceptual_confusion": conceptual_confusion,
                "academic_helplessness": academic_helplessness,
                "course_frustration": course_frustration,
                "motivation_erosion": motivation_erosion,
                "dominant_stress_label": dominant_stress,
                "affective_confidence": affective_conf,
                # Targets
                "actual_composite_risk": round(composite_risk, 3),
                "risk_tier": risk_tier,
                "actual_dropout": dropout,
            })

    df = pd.DataFrame(records)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate multimodal synthetic dataset for C3 Risk Prediction")
    parser.add_argument("--students", type=int, default=500, help="Number of unique students")
    parser.add_argument("--weeks", type=int, default=12, help="Number of academic weeks")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path")
    args = parser.parse_args()

    output_path = args.output
    if not output_path:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_path = os.path.join(base_dir, "data", "multimodal_risk_training_data.csv")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    print(f"[*] Generating multimodal student dataset ({args.students} students across {args.weeks} weeks)...")
    df = generate_multimodal_data(num_students=args.students, num_weeks=args.weeks)
    df.to_csv(output_path, index=False)
    print(f"[OK] Saved {len(df)} multimodal records to: {output_path}")
    print("\nDataset Summary Preview:")
    print(df[["cumulative_grade", "weekly_clicks", "conceptual_confusion", "actual_composite_risk", "risk_tier"]].describe())

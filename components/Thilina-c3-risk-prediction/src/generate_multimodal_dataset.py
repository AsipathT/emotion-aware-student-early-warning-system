"""
components/Thilina-c3-risk-prediction/src/generate_multimodal_dataset.py

Contract-Driven Multimodal Dataset Generator for Component 3 (Multimodal Risk Prediction).
Simulates longitudinal latent-state random walks with planted modality drivers,
realistic withdrawal hazard processes, and missing affect telemetry.
"""

import os
import argparse
import random
import numpy as np
import pandas as pd


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def generate_multimodal_data(
    num_students: int = 600,
    num_weeks: int = 30,
    k_weeks: int = 4,
    seed: int = 42,
    output_dir: str = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generates contract-compliant multimodal training dataset with latent random-walk state simulation,
    planted driver attribution, realistic withdrawal hazards, and separate ground-truth logs.
    """
    np.random.seed(seed)
    random.seed(seed)

    if output_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(base_dir, "data")
    os.makedirs(output_dir, exist_ok=True)

    courses = ["CS101", "CS102", "ENG201", "MATH101"]
    cohorts = ["cohort_1", "cohort_2", "cohort_3"]

    training_rows = []
    truth_rows = []

    # Assign students evenly to 3 cohorts
    students_per_cohort = num_students // 3

    for s_idx in range(num_students):
        pid = f"STU_{s_idx + 1:08x}"
        cohort = cohorts[min(s_idx // students_per_cohort, 2)]
        course_id = random.choice(courses)

        # ── 1. Latent State Initialization & Archetypes ───────────────────────
        archetype_roll = np.random.rand()
        if archetype_roll < 0.12:
            # Resilient perfectionist: high distress, high engagement, high performance
            d_init = np.random.uniform(0.55, 0.75)
            e_init = np.random.uniform(0.75, 0.92)
            p_init = np.random.uniform(0.75, 0.95)
            archetype = "perfectionist"
        elif archetype_roll < 0.22:
            # Quiet struggler: modest distress, low engagement, low performance, few messages
            d_init = np.random.uniform(0.30, 0.45)
            e_init = np.random.uniform(0.25, 0.42)
            p_init = np.random.uniform(0.25, 0.45)
            archetype = "quiet_struggler"
        elif archetype_roll < 0.30:
            # Sudden dropout: stable initially, then sudden collapse
            d_init = np.random.uniform(0.15, 0.30)
            e_init = np.random.uniform(0.65, 0.85)
            p_init = np.random.uniform(0.60, 0.80)
            archetype = "sudden_dropout"
        else:
            # Standard student distribution
            d_init = np.clip(np.random.normal(0.25, 0.10), 0.05, 0.60)
            e_init = np.clip(np.random.normal(0.68, 0.15), 0.20, 0.95)
            p_init = np.clip(np.random.normal(0.65, 0.15), 0.20, 0.95)
            archetype = "standard"

        # Target ~25-30% overall withdrawal rate:
        is_crisis_student = np.random.rand() < 0.45
        planted_driver = random.choice(["affective", "behavioural", "academic"])

        if is_crisis_student:
            onset_week = int(np.random.randint(4, 22))
        else:
            onset_week = -1  # No crisis onset

        d_t = d_init
        e_t = e_init
        p_t = p_init

        # Track history to compute noisy trajectory labels
        e_history = []
        withdraw_week = -1

        student_week_snapshots = []

        for week in range(num_weeks):
            # ── 3. Latent Random-Walk Evolution ──────────────────────────────
            # Base Gaussian noise on states
            noise_d = np.random.normal(0, 0.015)
            noise_e = np.random.normal(0, 0.015)
            noise_p = np.random.normal(0, 0.015)

            if is_crisis_student and week >= onset_week:
                steps_since_onset = week - onset_week
                lag = 2  # secondary modalities begin sliding after lag

                if archetype == "sudden_dropout" and steps_since_onset >= 1:
                    # Acute collapse
                    d_t += 0.20
                    e_t -= 0.25
                    p_t -= 0.20
                elif planted_driver == "affective":
                    # Distress jumps immediately; engagement & performance lag
                    d_t += 0.045
                    if steps_since_onset >= lag:
                        e_t -= 0.035
                        p_t -= 0.030
                elif planted_driver == "behavioural":
                    # Engagement collapses first; performance & distress lag
                    e_t -= 0.050
                    if steps_since_onset >= lag:
                        p_t -= 0.035
                        d_t += 0.035
                elif planted_driver == "academic":
                    # Performance drops first; distress & engagement lag
                    p_t -= 0.050
                    if steps_since_onset >= lag:
                        d_t += 0.040
                        e_t -= 0.035
            else:
                # Normal minor drift
                d_t += noise_d
                e_t += noise_e
                p_t += noise_p

            d_t = float(np.clip(d_t, 0.02, 0.98))
            e_t = float(np.clip(e_t, 0.02, 0.98))
            p_t = float(np.clip(p_t, 0.02, 0.98))
            e_history.append(e_t)

            # ── 4. Weekly Hazard of Withdrawal ───────────────────────────────
            # Baseline hazard logit calibrated to yield ~25-30% cumulative withdrawal
            hazard_logit = -4.1 + 3.4 * d_t - 3.0 * e_t - 2.8 * p_t
            if archetype == "perfectionist":
                hazard_logit -= 1.8  # Perfectionists rarely drop out despite high distress

            h_t = float(sigmoid(hazard_logit))

            # Sample withdrawal event
            if withdraw_week == -1 and np.random.rand() < h_t:
                withdraw_week = week

            # Store snapshot
            student_week_snapshots.append({
                "week_index": week,
                "d_t": d_t,
                "e_t": e_t,
                "p_t": p_t,
                "e_history": list(e_history),
            })

            # Truncation: After withdrawal, no more rows for this student
            if withdraw_week != -1:
                break

        # Record Ground Truth in separate table
        truth_rows.append({
            "pid": pid,
            "cohort": cohort,
            "planted_driver": planted_driver if is_crisis_student else "none",
            "onset_week": onset_week if is_crisis_student else None,
            "withdraw_week": withdraw_week if withdraw_week != -1 else None,
            "seed": seed,
        })

        # ── 5. Generate Contract-Compliant Observed Features ─────────────────
        for snap in student_week_snapshots:
            w = snap["week_index"]
            d = snap["d_t"]
            e = snap["e_t"]
            p = snap["p_t"]
            hist = snap["e_history"]

            # Label: withdraws_within_k_weeks (1 if withdrawal occurs in w+1 .. w+k)
            if withdraw_week != -1 and (w < withdraw_week <= w + k_weeks):
                withdraw_label = 1
            else:
                withdraw_label = 0

            # ── A. Affective Modality (C1 Contract) ──────────────────────────
            # ~20% of student-weeks have message_count = 0 and null emotion scores
            is_affect_missing = (np.random.rand() < 0.20) or (archetype == "quiet_struggler" and np.random.rand() < 0.45)

            if is_affect_missing:
                message_count = 0
                exam_anxiety = np.nan
                conceptual_confusion = np.nan
                academic_helplessness = np.nan
                course_frustration = np.nan
                motivation_erosion = np.nan
                stress_label = "neutral"
                confidence = float(np.round(np.clip(0.60 + 0.15 * np.random.rand(), 0.50, 0.95), 2))
            else:
                message_count = int(max(1, np.random.poisson(lam=max(1.0, e * 7))))
                exam_anxiety = float(np.round(np.clip(d * 0.85 + np.random.normal(0, 0.08), 0.01, 0.99), 3))
                conceptual_confusion = float(np.round(np.clip(d * 0.55 + (1.0 - p) * 0.40 + np.random.normal(0, 0.07), 0.01, 0.99), 3))
                academic_helplessness = float(np.round(np.clip(d * 0.50 + (1.0 - p) * 0.45 + np.random.normal(0, 0.06), 0.01, 0.99), 3))
                course_frustration = float(np.round(np.clip(d * 0.60 + (1.0 - e) * 0.35 + np.random.normal(0, 0.07), 0.01, 0.99), 3))
                motivation_erosion = float(np.round(np.clip((1.0 - e) * 0.75 + d * 0.20 + np.random.normal(0, 0.06), 0.01, 0.99), 3))

                emotions = {
                    "exam_anxiety": exam_anxiety,
                    "conceptual_confusion": conceptual_confusion,
                    "academic_helplessness": academic_helplessness,
                    "course_frustration": course_frustration,
                    "motivation_erosion": motivation_erosion,
                }
                stress_label = max(emotions, key=emotions.get)
                confidence = float(np.round(np.clip(0.70 + 0.25 * e + np.random.normal(0, 0.04), 0.50, 0.99), 2))

            # ── B. Behavioral Modality (BehaviorWeeklyRecord & Trajectory) ────
            login_count = int(max(0, np.random.poisson(lam=max(0.5, e * 6.5))))
            session_minutes = float(np.round(max(0.0, e * 160.0 + np.random.normal(0, 22.0)), 1))
            clicks = int(max(0, np.random.poisson(lam=max(4.0, e * 175.0 + np.random.normal(0, 20.0)))))
            video_play_count = int(max(0, np.random.poisson(lam=max(0.2, e * 5.0))))
            video_pause_count = int(max(0, np.random.poisson(lam=max(0.1, video_play_count * 1.8 + d * 2.0))))
            video_rewind_count = int(max(0, np.random.poisson(lam=max(0.1, d * 3.5 + (1.0 - p) * 2.5))))
            video_skip_count = int(max(0, np.random.poisson(lam=max(0.0, (1.0 - e) * 3.0))))
            video_completion_pct = float(np.round(np.clip(e * 95.0 - d * 15.0 + np.random.normal(0, 8.0), 0.0, 100.0), 1))
            submissions_count = 1 if (w % 2 == 1 and np.random.rand() < e * 0.95 + 0.05) else (1 if np.random.rand() < 0.15 else 0)
            avg_submission_delay_hours = float(np.round((1.0 - e) * 45.0 - e * 12.0 + np.random.normal(0, 6.0), 1))

            # Trajectory label (lowercase, derived from noisy delta over past 3 weeks)
            if len(hist) >= 3:
                delta_e = hist[-1] - hist[-3]
                var_e = np.std(hist[-3:])
                if delta_e < -0.06:
                    trajectory_label = "declining"
                elif delta_e > 0.06:
                    trajectory_label = "improving"
                elif var_e > 0.08:
                    trajectory_label = "volatile"
                else:
                    trajectory_label = "stable"
            else:
                trajectory_label = "stable"

            # ── C. Academic Modality (AcademicRecord Contract) ────────────────
            attendance_pct = float(np.round(np.clip(e * 98.0 + np.random.normal(0, 5.0), 0.0, 100.0), 1))
            ca_marks = float(np.round(np.clip(p * 100.0 + np.random.normal(0, 5.5), 0.0, 100.0), 1))
            # Midterm mark recorded in or after week 15
            midterm_mark = float(np.round(np.clip(p * 100.0 + np.random.normal(0, 6.0), 0.0, 100.0), 1)) if w >= 15 else np.nan
            quiz_score = float(np.round(np.clip(p * 100.0 + np.random.normal(0, 7.0), 0.0, 100.0), 1))
            submission_delay_hours = avg_submission_delay_hours

            training_rows.append({
                # Identifiers & Split
                "pid": pid,
                "course_id": course_id,
                "cohort": cohort,
                "week_index": w,
                # C1 Affective Fields
                "message_count": message_count,
                "exam_anxiety": exam_anxiety,
                "conceptual_confusion": conceptual_confusion,
                "academic_helplessness": academic_helplessness,
                "course_frustration": course_frustration,
                "motivation_erosion": motivation_erosion,
                "stress_label": stress_label,
                "confidence": confidence,
                # C2 Behavioral & Trajectory Fields
                "trajectory_label": trajectory_label,
                "login_count": login_count,
                "session_minutes": session_minutes,
                "clicks": clicks,
                "video_play_count": video_play_count,
                "video_pause_count": video_pause_count,
                "video_rewind_count": video_rewind_count,
                "video_skip_count": video_skip_count,
                "video_completion_pct": video_completion_pct,
                "submissions_count": submissions_count,
                "avg_submission_delay_hours": avg_submission_delay_hours,
                # LMS Academic Fields
                "attendance_pct": attendance_pct,
                "ca_marks": ca_marks,
                "midterm_mark": midterm_mark,
                "quiz_score": quiz_score,
                "submission_delay_hours": submission_delay_hours,
                # Target Label
                "withdraws_within_k_weeks": withdraw_label,
            })

    train_df = pd.DataFrame(training_rows)
    truth_df = pd.DataFrame(truth_rows)

    return train_df, truth_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate contract-compliant multimodal dataset for C3 Risk Prediction")
    parser.add_argument("--students", type=int, default=600, help="Number of students")
    parser.add_argument("--weeks", type=int, default=30, help="Number of observation weeks")
    parser.add_argument("--k", type=int, default=4, help="Withdrawal lookahead window (weeks)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output_dir", type=str, default=None, help="Output folder")
    args = parser.parse_args()

    base_dir = args.output_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    train_csv = os.path.join(base_dir, "multimodal_risk_training_data.csv")
    truth_csv = os.path.join(base_dir, "truth_labels.csv")

    print(f"[*] Simulating {args.students} students across {args.weeks} weeks (lookahead k={args.k})...")
    train_df, truth_df = generate_multimodal_data(
        num_students=args.students,
        num_weeks=args.weeks,
        k_weeks=args.k,
        seed=args.seed,
        output_dir=base_dir,
    )

    train_df.to_csv(train_csv, index=False)
    truth_df.to_csv(truth_csv, index=False)

    withdrawn_count = (truth_df["withdraw_week"].notna()).sum()
    withdraw_rate = (withdrawn_count / len(truth_df)) * 100
    pos_rate = (train_df["withdraws_within_k_weeks"].sum() / len(train_df)) * 100
    missing_affect_rate = (train_df["message_count"] == 0).sum() / len(train_df) * 100

    print(f"[OK] Training dataset saved to: {train_csv} ({len(train_df)} rows, {len(train_df.columns)} columns)")
    print(f"[OK] Ground-truth labels saved to: {truth_csv} ({len(truth_df)} students)")
    print(f"     - Student withdrawal rate: {withdraw_rate:.1f}% ({withdrawn_count}/{len(truth_df)})")
    print(f"     - Weekly positive label rate (withdraws_within_{args.k}_weeks): {pos_rate:.1f}%")
    print(f"     - Weeks with missing affect (message_count=0): {missing_affect_rate:.1f}%")
    print(f"     - Cohort breakdown: {train_df['cohort'].value_counts().to_dict()}")

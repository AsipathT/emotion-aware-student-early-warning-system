from sqlalchemy import create_engine
from sqlalchemy import inspect
from app.core.config import settings

uri = f"postgresql://{settings.postgres_user}:{settings.postgres_password}@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
engine = create_engine(uri)
inspector = inspect(engine)

required_tables = [
    "enrollments", "assignments", "assignment_submissions", "quizzes", 
    "quiz_questions", "quiz_options", "quiz_attempts", "quiz_answers", 
    "gradebook_entries", "attendance_sessions", "attendance_records", 
    "user_sessions", "click_events", "weekly_features", "affect_weekly", 
    "trajectory_labels", "risk_scores", "synthetic_ground_truth", "courses"
]

print("=== TABLE EXISTENCE ===")
for tbl in required_tables:
    exists = inspector.has_table(tbl)
    print(f"{tbl}: {'Yes' if exists else 'No'}")

if inspector.has_table("courses"):
    cols = [c["name"] for c in inspector.get_columns("courses")]
    print(f"courses.start_date exists: {'start_date' in cols}")
    print(f"courses.end_date exists: {'end_date' in cols}")

def check_cols(tbl, expected):
    if inspector.has_table(tbl):
        cols = [c["name"] for c in inspector.get_columns(tbl)]
        print(f"--- {tbl} cols ---")
        for e in expected:
            print(f"{e}: {'Yes' if e in cols else 'No'}")

check_cols("weekly_features", [
    "session_frequency", "clicks_total", "active_days", "active_duration_trend", 
    "submission_delay_days", "video_interaction_intensity", "missed_assessments", 
    "prev_attempts", "studied_credits", "attendance_rate", "score_so_far", 
    "week_index", "student_id", "course_id"
])

check_cols("affect_weekly", [
    "exam_anxiety", "conceptual_confusion", "academic_helplessness", 
    "course_frustration", "motivation_erosion", "confidence", "message_count", 
    "week_index", "course_id"
])

check_cols("trajectory_labels", [
    "label", "p_stable", "p_improving", "p_declining", "p_volatile", "confidence", "indicators"
])

check_cols("risk_scores", [
    "risk_score", "risk_tier", "calibrated", "modality_weights", "top_features", 
    "c1_snapshot", "c2_snapshot", "missing_modalities", "schema_version"
])

print("=== ROW COUNTS ===")
from sqlalchemy import text
with engine.connect() as conn:
    for tbl in required_tables:
        if inspector.has_table(tbl):
            count = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
            print(f"{tbl}: {count} rows")

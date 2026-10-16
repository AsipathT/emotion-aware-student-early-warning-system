"""Seed data: one admin user, demo students and some past recommendations.

The server creates any missing data file on start-up. To reset all demo data:
    python -m app.seed --reset
"""
import argparse

from . import config
from .auth import hash_password
from .recommend import build_assessment

ADMIN = {"username": "admin", "password": "admin123", "name": "Admin Counselor", "role": "Counselor"}

STUDENTS = [
    {"id": "IT23149076", "name": "Kavindu Perera"},
    {"id": "IT23157030", "name": "Sanduni Fernando"},
    {"id": "IT23168421", "name": "Ravindu Silva"},
    {"id": "IT23179205", "name": "Tharindu Jayasinghe"},
    {"id": "IT23184567", "name": "Nethmi Dissanayake"},
    {"id": "IT23193614", "name": "Hasini Gunawardena"},
    {"id": "IT23204783", "name": "Ishara Wickramasinghe"},
    {"id": "IT23215892", "name": "Pasindu Bandara"},
    {"id": "IT23226405", "name": "Dilshan Rathnayake"},
    {"id": "IT23237918", "name": "Chamodi Herath"},
    {"id": "IT23248506", "name": "Yasiru Karunaratne"},
    {"id": "IT23259631", "name": "Amaya Senanayake"},
]

# (student, date, C1, C2, dropout risk score, (affective, behavioural, academic))
PAST_ASSESSMENTS = [
    ("IT23184567", "2026-08-12T04:15:00+00:00", "Exam Anxiety", "Stable", 0.45, (0.45, 0.30, 0.25)),
    ("IT23184567", "2026-09-16T05:30:00+00:00", "Conceptual Confusion", "Declining", 0.62, (0.25, 0.30, 0.45)),
    ("IT23149076", "2026-09-03T03:45:00+00:00", "Motivation Erosion", "Declining", 0.71, (0.30, 0.45, 0.25)),
    ("IT23157030", "2026-08-20T06:00:00+00:00", "Course Pacing Frustration", "Improving", 0.38, (0.20, 0.50, 0.30)),
    ("IT23157030", "2026-09-24T04:40:00+00:00", "Course Pacing Frustration", "Stable", 0.22, (0.20, 0.45, 0.35)),
    ("IT23179205", "2026-09-10T08:20:00+00:00", "Academic Helplessness", "Volatile", 0.83, (0.50, 0.30, 0.20)),
    ("IT23204783", "2026-09-29T07:10:00+00:00", "Exam Anxiety", "Improving", 0.18, (0.55, 0.20, 0.25)),
    ("IT23226405", "2026-08-28T05:05:00+00:00", "Conceptual Confusion", "Stable", 0.56, (0.20, 0.30, 0.50)),
]


def seed_users() -> list[dict]:
    user = {k: v for k, v in ADMIN.items() if k != "password"}
    user["password_hash"] = hash_password(ADMIN["password"])
    return [user]


def seed_assessments(model) -> list[dict]:
    records = []
    for student_id, created_at, c1, c2, risk, (aff, beh, aca) in PAST_ASSESSMENTS:
        inputs = {"c1_condition": c1, "c2_trajectory": c2, "risk_probability": risk,
                  "c3": {"affective": aff, "behavioural": beh, "academic": aca}}
        records.append(build_assessment(model, student_id, inputs, ADMIN["username"], created_at))
    return records


def ensure_seed_data(users_store, students_store, assessments_store, model, reset: bool = False) -> None:
    if reset or not users_store.path.exists():
        users_store.write(seed_users())
    if reset or not students_store.path.exists():
        students_store.write(STUDENTS)
    if reset or not assessments_store.path.exists():
        assessments_store.write(seed_assessments(model))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create the demo JSON data files.")
    parser.add_argument("--reset", action="store_true", help="overwrite existing data files")
    args = parser.parse_args()

    from .model_service import InterventionModel
    from .storage import JsonStore

    ensure_seed_data(
        JsonStore(config.DATA_DIR / "users.json"),
        JsonStore(config.DATA_DIR / "students.json"),
        JsonStore(config.DATA_DIR / "assessments.json"),
        InterventionModel(config.MODEL_PATH, config.TRAINING_DATA_PATH),
        reset=args.reset,
    )
    print("Seed data ready in", config.DATA_DIR)

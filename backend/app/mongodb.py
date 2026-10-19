"""MongoDB persistence for users and intervention recommendations."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument


class MongoStore:
    def __init__(self, uri: str, database: str, recommendations_collection: str):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self.database = self.client[database]
        self.users = self.database["users"]
        self.recommendations = self.database[recommendations_collection]

    def verify_connection(self) -> None:
        self.client.admin.command("ping")
        self.recommendations.create_index([("id", ASCENDING)], unique=True)
        self.recommendations.create_index([("student_id", ASCENDING), ("created_at", DESCENDING)])

    def close(self) -> None:
        self.client.close()

    def find_login_user(self, identity: str) -> dict[str, Any] | None:
        return self.users.find_one(
            {"$or": [{"email": identity}, {"id": identity}]},
            {"_id": 0},
        )

    def find_user(self, identity: str) -> dict[str, Any] | None:
        return self.users.find_one(
            {"$or": [{"email": identity}, {"id": identity}]},
            {"_id": 0},
        )

    def students(self) -> list[dict[str, Any]]:
        records = self.users.find(
            {"role": "student"},
            {"_id": 0, "id": 1, "student_id": 1, "full_name": 1, "email": 1, "pid": 1},
        ).sort("full_name", ASCENDING)
        return [self._student_record(record) for record in records]

    def student(self, student_id: str) -> dict[str, Any] | None:
        record = self.users.find_one(
            {"role": "student", "student_id": student_id},
            {"_id": 0, "id": 1, "student_id": 1, "full_name": 1, "email": 1, "pid": 1},
        )
        return self._student_record(record) if record else None

    def assessments(self, student_id: str | None = None) -> list[dict[str, Any]]:
        query = {"student_id": student_id} if student_id is not None else {}
        return [self._without_mongo_id(record) for record in self.recommendations.find(query).sort("created_at", DESCENDING)]

    def append_assessment(self, record: dict[str, Any]) -> dict[str, Any]:
        stored = deepcopy(record)
        self.recommendations.insert_one(stored)
        return record

    def update_assessment(self, assessment_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
        result = self.recommendations.find_one_and_update(
            {"id": assessment_id},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
        )
        return self._without_mongo_id(result) if result else None

    @staticmethod
    def _student_record(record: dict[str, Any] | None) -> dict[str, Any] | None:
        if record is None:
            return None
        student_id = record.get("student_id") or record.get("id")
        return {
            "id": student_id,
            "name": record.get("full_name") or record.get("email") or student_id,
            "user_id": record.get("id"),
            "email": record.get("email"),
            "pid": record.get("pid"),
        }

    @staticmethod
    def _without_mongo_id(record: dict[str, Any]) -> dict[str, Any]:
        result = dict(record)
        result.pop("_id", None)
        return result

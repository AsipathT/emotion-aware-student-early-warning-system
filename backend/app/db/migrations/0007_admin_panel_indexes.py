"""
backend/app/db/migrations/0007_admin_panel_indexes.py

Feature 40: Admin Panel Query Optimization Indexes.
Adds indexes for admin query patterns:
- users: compound role/status, created_at, full_name
- courses: is_published, title
- enrolments: compound (course_id, status, pid)
- audit_logs: compound (actor_id, timestamp), (action, timestamp), (target_type, timestamp)
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.db import collections as col

MIGRATION_ID = "0007_admin_panel_indexes"

ADMIN_INDEXES = {
    col.USERS: [
        IndexModel([("role", ASCENDING), ("is_active", ASCENDING)], name="idx_users_role_status"),
        IndexModel([("created_at", DESCENDING)], name="idx_users_created_at_desc"),
        IndexModel([("full_name", ASCENDING)], name="idx_users_full_name"),
    ],
    col.COURSES: [
        IndexModel([("is_published", ASCENDING)], name="idx_courses_is_published"),
        IndexModel([("title", ASCENDING)], name="idx_courses_title"),
    ],
    col.ENROLMENTS: [
        IndexModel(
            [("course_id", ASCENDING), ("status", ASCENDING), ("pid", ASCENDING)],
            name="idx_enrolments_course_status_pid",
        ),
    ],
    col.AUDIT_LOGS: [
        IndexModel([("actor_id", ASCENDING), ("timestamp", DESCENDING)], name="idx_audit_actor_timestamp"),
        IndexModel([("action", ASCENDING), ("timestamp", DESCENDING)], name="idx_audit_action_timestamp"),
        IndexModel([("target_type", ASCENDING), ("timestamp", DESCENDING)], name="idx_audit_target_type_timestamp"),
    ],
}


async def upgrade(db: AsyncIOMotorDatabase) -> None:
    """
    Applies admin panel query optimization indexes to MongoDB collections.
    """
    for collection_name, index_list in ADMIN_INDEXES.items():
        try:
            await db[collection_name].create_indexes(index_list)
        except Exception as exc:
            print(f"Notice: Index creation note on {collection_name}: {exc}")

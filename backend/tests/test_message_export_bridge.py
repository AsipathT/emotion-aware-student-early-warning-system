"""
backend/tests/test_message_export_bridge.py

Unit tests for pure functions in Feature 17:
- compute_week_index (date arithmetic, window matching, timezone handling)
- _prepare_clean_text (privacy scrubbing & CleanText constraint validation)
- _is_student role checks
- TextMessageStorage contract persistence formatting

Note: Pure unit tests only. No database connection or I/O is performed.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from app.db.storage_models import TextMessageStorage
from app.models.user import UserRole
from app.schemas.contract.common import SourceType
from app.services.message_export_bridge import (
    _is_student,
    _prepare_clean_text,
)
from app.services.week_index import compute_week_index


class TestComputeWeekIndex:
    """Tests pure calculation of academic week indices."""

    def test_matching_course_week_doc_aware_datetime(self):
        start = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 7, 23, 59, 59, tzinfo=timezone.utc)
        target = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        course_weeks = [
            {"week_index": 0, "start_date": start, "end_date": end},
        ]
        result = compute_week_index(target, course_weeks, None)
        assert result == 0

    def test_matching_course_week_doc_naive_datetimes(self):
        # Motor returns naive UTC datetimes
        start = datetime(2026, 10, 8, 0, 0)
        end = datetime(2026, 10, 14, 23, 59, 59)
        target = datetime(2026, 10, 10, 12, 0)
        course_weeks = [
            {"week_index": 1, "start_date": start, "end_date": end},
        ]
        result = compute_week_index(target, course_weeks, None)
        assert result == 1

    def test_fallback_to_course_created_at_floor_seven_days(self):
        course_created = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        # 16 days later -> 16 // 7 = week 2
        target = course_created + timedelta(days=16)
        result = compute_week_index(target, [], course_created)
        assert result == 2

    def test_fallback_clamps_negative_days_to_zero(self):
        course_created = datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc)
        target = datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc)
        result = compute_week_index(target, [], course_created)
        assert result == 0

    def test_fallback_with_missing_created_at_returns_zero(self):
        target = datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc)
        result = compute_week_index(target, [], None)
        assert result == 0


class TestPrepareCleanText:
    """Tests PII redaction and CleanText validation."""

    def test_scrubs_known_name_and_replaces(self):
        raw = "Hello, my name is Alice Smith and I need help."
        cleaned = _prepare_clean_text(raw, "Alice Smith")
        assert cleaned is not None
        assert "Alice Smith" not in cleaned
        assert "[NAME]" in cleaned

    def test_scrubs_email_pattern(self):
        raw = "Contact me at student@myuni.edu please."
        cleaned = _prepare_clean_text(raw, None)
        assert cleaned is not None
        assert "student@myuni.edu" not in cleaned
        assert "[EMAIL]" in cleaned

    def test_scrubs_registration_id_pattern(self):
        raw = "My student ID is IT23123456."
        cleaned = _prepare_clean_text(raw, None)
        assert cleaned is not None
        assert "IT23123456" not in cleaned
        assert "[REG_ID]" in cleaned

    def test_empty_or_whitespace_returns_none(self):
        assert _prepare_clean_text("", None) is None
        assert _prepare_clean_text("   \n\t  ", None) is None


class TestRoleCheck:
    """Tests verification of student author role."""

    def test_student_role_accepted(self):
        user = Mock(role=UserRole.STUDENT)
        assert _is_student(user) is True

    def test_non_student_role_rejected(self):
        for role in [UserRole.LECTURER, UserRole.ADMIN, UserRole.COUNSELLOR]:
            user = Mock(role=role)
            assert _is_student(user) is False


class TestTextMessageStorageModel:
    """Tests TextMessageStorage serialization contract."""

    def test_valid_storage_model_serialization(self):
        now = datetime.now(timezone.utc)
        doc = TextMessageStorage(
            id="test-msg-1",
            message_id="test-msg-1",
            pid="STU_a1b2c3d4",
            course_id="CS101",
            week_index=3,
            source_type=SourceType.FORUM,
            clean_text="I feel confused about trees.",
            timestamp=now,
            response_latency_seconds=42.5,
            message_length_chars=28,
            message_length_words=6,
            reply_to_id=None,
            source="lms",
            source_version="1.0",
        )
        d = doc.model_dump(by_alias=True)
        assert d["_id"] == "test-msg-1"
        assert d["message_id"] == "test-msg-1"
        assert d["pid"] == "STU_a1b2c3d4"
        assert d["course_id"] == "CS101"
        assert d["week_index"] == 3
        assert d["clean_text"] == "I feel confused about trees."
        assert d["source"] == "lms"
        assert d["source_version"] == "1.0"

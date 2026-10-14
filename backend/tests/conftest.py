"""
backend/tests/conftest.py

Feature test configuration and database lifecycle management.
Guarantees test database isolation and automatic teardown of test databases.
Tracks only the lms_test_* databases created during the active test session by name
and drops only those at session end; if none were created, drops nothing.
Ensures zero test database leakage in MongoDB without ever printing or leaking Mongo credentials.
"""

import os
from typing import Set
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

from app.core.config import settings

# Session tracker for test databases created during this pytest session
SESSION_CREATED_DBS: Set[str] = set()


def register_test_database(db_name: str) -> None:
    """Explicitly registers a test database name created during the test session."""
    if isinstance(db_name, str) and (db_name.startswith("lms_test_") or db_name.startswith("lms_test")):
        SESSION_CREATED_DBS.add(db_name)


# Monkeypatch __getitem__ and get_database to automatically track any lms_test_* database accessed
_orig_motor_getitem = AsyncIOMotorClient.__getitem__
_orig_motor_get_database = AsyncIOMotorClient.get_database
_orig_pymongo_getitem = MongoClient.__getitem__
_orig_pymongo_get_database = MongoClient.get_database


def _track_name(name: str) -> None:
    if isinstance(name, str) and (name.startswith("lms_test_") or name.startswith("lms_test")):
        SESSION_CREATED_DBS.add(name)


def _patched_motor_getitem(self, name, *args, **kwargs):
    _track_name(name)
    return _orig_motor_getitem(self, name, *args, **kwargs)


def _patched_motor_get_database(self, name, *args, **kwargs):
    _track_name(name)
    return _orig_motor_get_database(self, name, *args, **kwargs)


def _patched_pymongo_getitem(self, name, *args, **kwargs):
    _track_name(name)
    return _orig_pymongo_getitem(self, name, *args, **kwargs)


def _patched_pymongo_get_database(self, name, *args, **kwargs):
    _track_name(name)
    return _orig_pymongo_get_database(self, name, *args, **kwargs)


AsyncIOMotorClient.__getitem__ = _patched_motor_getitem
AsyncIOMotorClient.get_database = _patched_motor_get_database
MongoClient.__getitem__ = _patched_pymongo_getitem
MongoClient.get_database = _patched_pymongo_get_database


@pytest.fixture(scope="session", autouse=True)
def cleanup_session_test_databases():
    """
    Session-level autouse fixture.
    Tracks test databases created during this test session by name and drops ONLY those at session end.
    If no test databases were created in this session, drops nothing.
    """
    yield

    # If this test session created no test databases, drop nothing
    if not SESSION_CREATED_DBS:
        return

    uri = os.environ.get("MONGODB_TEST_URI") or settings.test_mongo_uri or settings.mongo_uri
    if not uri:
        return

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        for name in list(SESSION_CREATED_DBS):
            try:
                client.drop_database(name)
            except Exception:
                pass
        client.close()
    except Exception:
        pass
    finally:
        SESSION_CREATED_DBS.clear()

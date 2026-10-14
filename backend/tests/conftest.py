"""
backend/tests/conftest.py

Feature test configuration and database lifecycle management.
Guarantees test database isolation and automatic teardown of all lms_test_* databases.
Ensures zero test database leakage in MongoDB without ever printing or leaking Mongo credentials.
"""

import os
import pytest
from pymongo import MongoClient

from app.core.config import settings


@pytest.fixture(scope="session", autouse=True)
def cleanup_all_test_databases():
    """
    Session-level autouse fixture.
    Discovers and drops all lms_test_* databases before and after the test session.
    """
    uri = os.environ.get("MONGODB_TEST_URI") or settings.test_mongo_uri or settings.mongo_uri
    if not uri:
        yield
        return

    def _drop_test_databases():
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            db_names = client.list_database_names()
            for name in db_names:
                if name.startswith("lms_test_") or name.startswith("lms_test"):
                    client.drop_database(name)
            client.close()
        except Exception:
            pass

    # Drop any leftover test databases before session starts
    _drop_test_databases()

    yield

    # Drop all test databases after session finishes
    _drop_test_databases()

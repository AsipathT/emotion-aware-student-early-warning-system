"""
backend/conftest.py

Pytest configuration providing a single shared event loop across all async tests,
preventing Motor AsyncIOMotorClient 'Event loop is closed' errors.
"""

import asyncio
import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the whole test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

"""
backend/app/core/db.py

Re-exports Motor MongoDB database dependencies from database.py for backward compatibility.
"""

from app.core.database import client, db, get_database, get_db

__all__ = ["client", "db", "get_database", "get_db"]

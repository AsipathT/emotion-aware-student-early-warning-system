"""
backend/app/core/database.py

MongoDB Atlas client and database initialization using Motor (asynchronous driver).
"""

from typing import AsyncGenerator
import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

# Singleton Motor client connection to MongoDB Atlas
client: AsyncIOMotorClient = AsyncIOMotorClient(
    settings.mongo_uri,
    tlsCAFile=certifi.where(),
)
db: AsyncIOMotorDatabase = client[settings.mongo_db_name]


def get_database() -> AsyncIOMotorDatabase:
    """Returns the active MongoDB database instance."""
    return db


async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """
    FastAPI dependency yielding the MongoDB database instance.
    Inject into route handlers with:
        db: AsyncIOMotorDatabase = Depends(get_db)
    """
    yield db

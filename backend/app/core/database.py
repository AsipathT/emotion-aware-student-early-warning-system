"""
backend/app/core/database.py

MongoDB Atlas client and database initialization using Motor (asynchronous driver).
"""

from typing import AsyncGenerator
import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

def create_mongo_client(uri: str | None = None) -> AsyncIOMotorClient:
    """Creates a new Motor client instance configured with tz_aware=True and SSL certificates."""
    target_uri = uri or settings.mongo_uri
    kwargs = {"tz_aware": True}
    if target_uri.startswith("mongodb+srv://") or "ssl=true" in target_uri.lower() or "tls=true" in target_uri.lower():
        kwargs["tlsCAFile"] = certifi.where()
    return AsyncIOMotorClient(target_uri, **kwargs)


# Singleton Motor client connection to MongoDB Atlas
client: AsyncIOMotorClient = create_mongo_client()
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

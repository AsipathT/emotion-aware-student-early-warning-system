"""
backend/app/core/dependencies.py

Reusable FastAPI dependency functions shared across all routers.
Provides get_current_user, require_roles, and get_current_admin using MongoDB.
"""

from typing import Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.models.user import User, UserRole

# HTTPBearer extracts the `Authorization: Bearer <token>` header.
_bearer_scheme = HTTPBearer(auto_error=True)


# ── get_current_user ──────────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> User:
    """
    Decode the Bearer JWT from the Authorization header, verify it is an
    access token, and return the matching active User from MongoDB.
    """
    _unauth = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise _unauth

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise _unauth

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise _unauth

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise _unauth

    user_doc = await db.users.find_one({"_id": user_id})
    if not user_doc:
        user_doc = await db.users.find_one({"id": user_id})

    if not user_doc or not user_doc.get("is_active", True):
        raise _unauth

    return User(**user_doc)


# ── require_roles ─────────────────────────────────────────────────────────────

def require_roles(*allowed: UserRole) -> Callable:
    """
    Dependency factory that enforces role-based access control.
    """
    allowed_set: frozenset[UserRole] = frozenset(allowed)

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access denied. Required role(s): "
                    f"{', '.join((r.value if hasattr(r, 'value') else str(r)) for r in allowed_set)}."
                ),
            )
        return current_user

    return _check


# ── get_current_admin ─────────────────────────────────────────────────────────

async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensures the authenticated user has the ADMIN role.
    Raises HTTP 403 Forbidden if the user is not an administrator.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required. Access denied.",
        )
    return current_user

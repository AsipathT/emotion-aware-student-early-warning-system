"""
backend/app/core/dependencies.py

Reusable FastAPI dependency functions shared across all routers.

Provided dependencies
---------------------
  get_current_user   – Validates Bearer JWT and returns the active User ORM object.
  require_roles      – Factory that returns a dependency enforcing a role allowlist.

Usage
-----
    from app.core.dependencies import get_current_user, require_roles
    from app.models.user import UserRole

    # Any authenticated user:
    @router.get("/me")
    async def me(user: User = Depends(get_current_user)):
        ...

    # Admin or Counsellor only:
    @router.get("/{user_id}", dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.COUNSELLOR))])
    async def get_user(...):
        ...
"""

from typing import Callable, Sequence

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.models.user import User, UserRole

# HTTPBearer extracts the `Authorization: Bearer <token>` header.
# auto_error=True (default) returns 403 automatically when the header is absent.
_bearer_scheme = HTTPBearer(auto_error=True)


# ── get_current_user ──────────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the Bearer JWT from the Authorization header, verify it is an
    access token, and return the matching active User from the database.

    Raises HTTP 401 for any of:
      - Missing / malformed token
      - Expired token
      - Token type is not "access"
      - User not found or deactivated
    """
    _unauth = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise _unauth

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise _unauth

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise _unauth

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user: User | None = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise _unauth

    return user


# ── require_roles ─────────────────────────────────────────────────────────────

def require_roles(*allowed: UserRole) -> Callable:
    """
    Dependency factory that enforces role-based access control.

    Parameters
    ----------
    *allowed : UserRole
        One or more roles that are permitted to access the endpoint.

    Returns
    -------
    Callable
        A FastAPI dependency function that raises HTTP 403 if the current
        user's role is not in *allowed*.

    Example
    -------
        @router.get("/admin-only", dependencies=[Depends(require_roles(UserRole.ADMIN))])
        async def admin_endpoint(): ...
    """
    allowed_set: frozenset[UserRole] = frozenset(allowed)

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access denied. Required role(s): "
                    f"{', '.join(r.value for r in allowed_set)}."
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


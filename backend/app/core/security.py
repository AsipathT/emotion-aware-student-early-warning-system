"""
backend/app/core/security.py

Password hashing (bcrypt) and JWT token creation / validation.

Token design
------------
  Access token   – short-lived (default 30 min), carries `sub` (user UUID)
                   and `role`.  Used to authorise API calls.
  Refresh token  – long-lived (default 7 days), used only to mint a new
                   token pair at POST /api/v1/auth/refresh.

Both tokens include a `type` claim ("access" | "refresh") so the refresh
endpoint can reject an access token presented in its place (and vice-versa).

All timestamps are UTC (datetime.now(timezone.utc)).

Library choice
--------------
`python-jose[cryptography]` is used instead of raw PyJWT because it is
already pinned in requirements.txt and provides a compatible interface with
richer claim validation out of the box.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ── Constants ─────────────────────────────────────────────────────────────────
ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

# ── bcrypt context ────────────────────────────────────────────────────────────
# `deprecated="auto"` means older hash schemes are transparently re-hashed on
# next login – useful for future algorithm migrations.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """Return the bcrypt hash of *plain_password*."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if *plain_password* matches *hashed_password*."""
    return _pwd_context.verify(plain_password, hashed_password)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _build_token(
    data: Dict[str, Any],
    token_type: str,
    expires_delta: timedelta,
) -> str:
    """
    Internal helper – stamps `iat`, `exp`, and `type` claims then signs the
    payload with HS256.
    """
    now = datetime.now(timezone.utc)
    payload = {
        **data,
        "iat": now,
        "exp": now + expires_delta,
        "type": token_type,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(subject: str, role: str) -> str:
    """
    Create a short-lived access JWT.

    Parameters
    ----------
    subject : str
        The user's UUID (as a string).
    role : str
        The user's role value (e.g. "student").
    """
    return _build_token(
        data={"sub": subject, "role": role},
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: str, role: str) -> str:
    """
    Create a long-lived refresh JWT.

    Parameters
    ----------
    subject : str
        The user's UUID (as a string).
    role : str
        The user's role value (e.g. "student").
    """
    return _build_token(
        data={"sub": subject, "role": role},
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT.

    Returns the decoded payload dict on success.
    Raises `jose.JWTError` if the token is invalid, expired, or tampered.
    Callers are responsible for checking the `type` claim.
    """
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])

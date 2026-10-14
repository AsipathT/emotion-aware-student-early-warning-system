"""Password hashing and JWT login for the seeded admin users (data/users.json)."""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config

ITERATIONS = 310_000
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_b64, hash_b64 = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iterations))
        return hmac.compare_digest(digest, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


def create_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": username, "iat": now, "exp": now + timedelta(hours=config.JWT_EXPIRE_HOURS)}
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def public_user(user: dict) -> dict:
    return {k: v for k, v in user.items() if k != "password_hash"}


def make_current_user_dependency(users_store):
    def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
        unauthorised = HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Please log in again.", headers={"WWW-Authenticate": "Bearer"})
        if credentials is None:
            raise unauthorised
        try:
            payload = jwt.decode(credentials.credentials, config.JWT_SECRET, algorithms=["HS256"])
        except jwt.PyJWTError:
            raise unauthorised
        user = next((u for u in users_store.read() if u["username"] == payload.get("sub")), None)
        if user is None:
            raise unauthorised
        return public_user(user)

    return current_user

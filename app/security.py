from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    password_bytes = password.encode()
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode()


def verify_password(password: str, password_hash: str) -> bool:
    password_bytes = password.encode()
    hash_bytes = password_hash.encode()
    return bcrypt.checkpw(password_bytes, hash_bytes)


def create_access_token(user_id: int) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None

    try:
        # a validly-signed token of another kind (e.g. a share token) has no
        # sub claim and must not authenticate anyone
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None


def create_share_token(project_id: int) -> str:
    expires_at = datetime.now(UTC) + timedelta(hours=settings.share_token_expires_hours)
    payload = {"project_id": project_id, "purpose": "share", "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_share_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None

    # the purpose claim keeps access tokens and share tokens from being
    # swapped for one another
    if payload.get("purpose") != "share":
        return None
    project_id = payload.get("project_id")
    return project_id if isinstance(project_id, int) else None

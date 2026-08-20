from datetime import UTC, datetime, timedelta

import jwt

from app.config import settings
from app.security import (
    ALGORITHM,
    create_access_token,
    create_share_token,
    decode_access_token,
    decode_share_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    password = "supersecret1"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


def test_token_roundtrip():
    token = create_access_token(42)

    user_id = decode_access_token(token)

    assert user_id == 42


def test_tampered_token_is_rejected():
    token = create_access_token(42)

    result = decode_access_token(token + "x")

    assert result is None


def test_expired_token_is_rejected():
    expired_payload = {"sub": "42", "exp": datetime.now(UTC) - timedelta(minutes=1)}
    expired_token = jwt.encode(expired_payload, settings.jwt_secret, algorithm=ALGORITHM)

    result = decode_access_token(expired_token)

    assert result is None


def test_share_token_roundtrip():
    token = create_share_token(7)

    project_id = decode_share_token(token)

    assert project_id == 7


def test_token_kinds_are_not_interchangeable():
    # both are validly signed, but each decoder must reject the other kind
    assert decode_share_token(create_access_token(1)) is None
    assert decode_access_token(create_share_token(1)) is None

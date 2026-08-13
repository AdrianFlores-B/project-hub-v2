import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.main import app
from app.storage import get_storage

TEST_DATABASE_URL = "postgresql+asyncpg://projecthub:projecthub@localhost:5432/projecthub_test"

# NullPool: every session opens a fresh connection, so nothing is tied to the
# event loop that asyncio.run() creates for the schema reset below.
test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


async def _reset_schema() -> None:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _override_get_db():
    async with TestSession() as session:
        yield session


class FakeStorage:
    """In-memory stand-in for S3Storage, same interface."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def save(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    def open(self, key: str):
        return iter([self.objects[key]])

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        for key in [k for k in self.objects if k.startswith(prefix)]:
            del self.objects[key]


@pytest.fixture()
def storage():
    return FakeStorage()


@pytest.fixture()
def client(storage):
    asyncio.run(_reset_schema())
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_storage] = lambda: storage
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def make_user(client):
    """Register a user and return auth headers for them."""

    def _make(login: str) -> dict[str, str]:
        resp = client.post(
            "/auth",
            json={"login": login, "password": "supersecret1", "repeat_password": "supersecret1"},
        )
        assert resp.status_code == 201, resp.text
        resp = client.post("/login", json={"login": login, "password": "supersecret1"})
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _make

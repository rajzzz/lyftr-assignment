import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import hashlib
import hmac
import json
from app.config import settings


from app.main import app
from app.models import Base
from app.storage import get_db

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, future=True)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db() -> AsyncSession:
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def test_client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def seed_data(test_client: AsyncClient):
    messages = [
        {"message_id": "m1", "from": "+1111111111", "to": "+1011111111", "ts": "2025-01-01T10:00:00Z", "text": "apple banana"},
        {"message_id": "m2", "from": "+2222222222", "to": "+1011111111", "ts": "2025-01-01T11:00:00Z", "text": "orange grape"},
        {"message_id": "m3", "from": "+1111111111", "to": "+1111111111", "ts": "2025-01-01T12:00:00Z", "text": "apple kiwi"},
        {"message_id": "m4", "from": "+3333333333", "to": "+1222222222", "ts": "2025-01-01T13:00:00Z", "text": "banana cherry"},
    ]
    for msg in messages:
        signature = hmac.new(
            settings.WEBHOOK_SECRET.encode(),
            json.dumps(msg, separators=(",", ":")).encode(),
            hashlib.sha256,
        ).hexdigest()
        await test_client.post("/webhook", json=msg, headers={"X-Signature": signature})

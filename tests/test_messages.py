import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_get_messages_default(test_client: AsyncClient):
    response = await test_client.get("/messages")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4
    assert data["limit"] == 50
    assert data["offset"] == 0
    assert len(data["data"]) == 4
    assert [m["message_id"] for m in data["data"]] == ["m1", "m2", "m3", "m4"]


async def test_get_messages_pagination(test_client: AsyncClient):
    response = await test_client.get("/messages?limit=2&offset=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4
    assert data["limit"] == 2
    assert data["offset"] == 1
    assert len(data["data"]) == 2
    assert [m["message_id"] for m in data["data"]] == ["m2", "m3"]


async def test_get_messages_filter_from(test_client: AsyncClient):
    response = await test_client.get("/messages?from=%2B1111111111")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["data"]) == 2
    assert [m["message_id"] for m in data["data"]] == ["m1", "m3"]


async def test_get_messages_filter_since(test_client: AsyncClient):
    response = await test_client.get("/messages?since=2025-01-01T11:30:00Z")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["data"]) == 2
    assert [m["message_id"] for m in data["data"]] == ["m3", "m4"]


async def test_get_messages_filter_q(test_client: AsyncClient):
    response = await test_client.get("/messages?q=apple")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["data"]) == 2
    assert [m["message_id"] for m in data["data"]] == ["m1", "m3"]

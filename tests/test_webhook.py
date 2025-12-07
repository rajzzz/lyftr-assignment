import hashlib
import hmac
import json
from datetime import datetime

import pytest
from httpx import AsyncClient

from app.config import settings

pytestmark = pytest.mark.asyncio


async def test_webhook_invalid_signature(test_client: AsyncClient):
    body = {"message_id": "m1", "from": "+1234567890", "to": "+9876543210", "ts": "2025-01-01T12:00:00Z", "text": "hello"}
    response = await test_client.post(
        "/webhook",
        json=body,
        headers={"X-Signature": "invalid"},
    )
    assert response.status_code == 401


async def test_webhook_valid_signature(test_client: AsyncClient):
    body = {"message_id": "m1", "from": "+1234567890", "to": "+9876543210", "ts": "2025-01-01T12:00:00Z", "text": "hello"}
    signature = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        json.dumps(body, separators=(",", ":")).encode(),
        hashlib.sha256,
    ).hexdigest()
    response = await test_client.post(
        "/webhook",
        json=body,
        headers={"X-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_webhook_duplicate(test_client: AsyncClient):
    body = {"message_id": "m1", "from": "+1234567890", "to": "+9876543210", "ts": "2025-01-01T12:00:00Z", "text": "hello"}
    signature = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        json.dumps(body, separators=(",", ":")).encode(),
        hashlib.sha256,
    ).hexdigest()

    response1 = await test_client.post(
        "/webhook",
        json=body,
        headers={"X-Signature": signature},
    )
    assert response1.status_code == 200

    response2 = await test_client.post(
        "/webhook",
        json=body,
        headers={"X-Signature": signature},
    )
    assert response2.status_code == 200


async def test_webhook_invalid_payload(test_client: AsyncClient):
    body = {"message_id": "m1"}  # Missing required fields
    signature = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        json.dumps(body, separators=(",", ":")).encode(),
        hashlib.sha256,
    ).hexdigest()
    response = await test_client.post(
        "/webhook",
        json=body,
        headers={"X-Signature": signature},
    )
    assert response.status_code == 422

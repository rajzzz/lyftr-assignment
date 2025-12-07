import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_get_stats(test_client: AsyncClient):
    response = await test_client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_messages"] == 4
    assert data["senders_count"] == 3
    assert data["first_message_ts"] == "2025-01-01T10:00:00Z"
    assert data["last_message_ts"] == "2025-01-01T13:00:00Z"

    senders = data["messages_per_sender"]
    assert len(senders) == 3
    # Note: The order of senders with the same count is not guaranteed by the query.
    # We convert to a dictionary keyed by 'from' to make the assertion order-independent.
    senders_by_from = {s["from"]: s for s in senders}

    assert senders_by_from["+1111111111"]["count"] == 2
    assert senders_by_from["+2222222222"]["count"] == 1
    assert senders_by_from["+3333333333"]["count"] == 1
    
    # Check that the top sender is first
    assert senders[0]["from"] == "+1111111111"

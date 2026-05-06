import httpx
import pytest

from discord_bot.domain.models import KirokuRequestContext, RouteDecision
from discord_bot.transport.kiroku_client import KirokuClient


@pytest.mark.asyncio
async def test_outbound_request_contains_required_headers():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(201, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = KirokuClient(
            base_url="http://localhost:8000",
            internal_api_token="secret",
            timeout_videos_seconds=5,
            timeout_videos_batch_seconds=6,
            timeout_receipts_seconds=7,
            timeout_receipts_manual_seconds=8,
            timeout_study_japanese_seconds=9,
            timeout_default_seconds=10,
            max_retries=3,
            client=http_client,
        )
        decision = RouteDecision(
            endpoint="/api/v1/videos",
            method="POST",
            content_type="application/json",
            payload={"url": "https://youtu.be/abc"},
        )
        ctx = KirokuRequestContext(
            guild_id="g1",
            channel_id="c1",
            message_id="m1",
            user_id="u1",
            idempotency_key="discord:g1:c1:m1",
        )

        response = await client.send(decision=decision, ctx=ctx)

    assert response.ok is True
    assert captured["headers"]["authorization"] == "Bearer secret"
    assert captured["headers"]["x-source"] == "discord-bot"
    assert captured["headers"]["x-source-message-id"] == "m1"
    assert captured["headers"]["x-source-user-id"] == "u1"
    assert captured["headers"]["idempotency-key"] == "discord:g1:c1:m1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint", "expected_timeout"),
    [
        ("/api/v1/videos", 11),
        ("/api/v1/videos/batch", 22),
        ("/api/v1/receipts", 33),
        ("/api/v1/receipts/manual", 44),
        ("/api/v1/study-assets/japanese", 55),
        ("/api/v1/unknown", 66),
    ],
)
async def test_outbound_request_uses_timeout_mapped_by_endpoint(
    endpoint: str, expected_timeout: int
):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["extensions"] = request.extensions
        return httpx.Response(201, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = KirokuClient(
            base_url="http://localhost:8000",
            internal_api_token="secret",
            timeout_videos_seconds=11,
            timeout_videos_batch_seconds=22,
            timeout_receipts_seconds=33,
            timeout_receipts_manual_seconds=44,
            timeout_study_japanese_seconds=55,
            timeout_default_seconds=66,
            max_retries=3,
            client=http_client,
        )
        decision = RouteDecision(
            endpoint=endpoint,
            method="POST",
            content_type="application/json",
            payload={"ok": True},
        )
        ctx = KirokuRequestContext(
            guild_id="g1",
            channel_id="c1",
            message_id="m1",
            user_id="u1",
            idempotency_key="discord:g1:c1:m1",
        )

        response = await client.send(decision=decision, ctx=ctx)

    assert response.ok is True
    timeout = captured["extensions"]["timeout"]
    assert timeout["connect"] == expected_timeout
    assert timeout["read"] == expected_timeout
    assert timeout["write"] == expected_timeout
    assert timeout["pool"] == expected_timeout

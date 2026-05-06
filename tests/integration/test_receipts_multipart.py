import httpx
import pytest

from discord_bot.domain.models import KirokuRequestContext, RouteDecision
from discord_bot.transport.kiroku_client import KirokuClient


@pytest.mark.asyncio
async def test_receipts_request_sends_expected_multipart_fields():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["content_type"] = request.headers.get("content-type", "")
        captured["body"] = await request.aread()
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
            endpoint="/api/v1/receipts",
            method="POST",
            content_type="multipart/form-data",
            multipart_files={
                "receipt_image": ("receipt.jpg", b"img-bytes", "image/jpeg")
            },
            multipart_data={"store_hint": "Falabella"},
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
    assert "multipart/form-data" in captured["content_type"]
    assert b'name="receipt_image"' in captured["body"]
    assert b'name="store_hint"' in captured["body"]

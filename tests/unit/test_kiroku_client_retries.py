from __future__ import annotations

import httpx
import pytest

from discord_bot.domain.models import KirokuRequestContext, RouteDecision
from discord_bot.transport.kiroku_client import KirokuClient


def _decision() -> RouteDecision:
    return RouteDecision(
        endpoint="/api/v1/videos",
        method="POST",
        content_type="application/json",
        payload={"url": "https://youtu.be/abc"},
    )


def _ctx() -> KirokuRequestContext:
    return KirokuRequestContext(
        guild_id="g1",
        channel_id="c1",
        message_id="m1",
        user_id="u1",
        idempotency_key="discord:g1:c1:m1",
    )


@pytest.mark.asyncio
async def test_send_retries_on_connect_error_then_succeeds() -> None:
    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.ConnectError("network down", request=request)
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

        response = await client.send(decision=_decision(), ctx=_ctx())

    assert attempts["count"] == 2
    assert response.ok is True
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_send_fails_on_connect_error_when_retries_exhausted() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down", request=request)

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
            max_retries=1,
            client=http_client,
        )

        response = await client.send(decision=_decision(), ctx=_ctx())

    assert response.ok is False
    assert response.status_code == 503

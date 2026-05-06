from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from discord_bot.domain.models import (
    KirokuRequestContext,
    ProcessingError,
    RouteDecision,
)
from discord_bot.transport.error_mapper import map_http_error
from discord_bot.transport.retry_policy import evaluate_retry


@dataclass
class KirokuResponse:
    ok: bool
    status_code: int
    payload: dict[str, Any] | None = None
    error: ProcessingError | None = None


class KirokuClient:
    def __init__(
        self,
        *,
        base_url: str,
        internal_api_token: str,
        timeout_videos_seconds: float,
        timeout_videos_batch_seconds: float,
        timeout_receipts_seconds: float,
        timeout_receipts_manual_seconds: float,
        timeout_study_japanese_seconds: float,
        timeout_default_seconds: float,
        max_retries: int,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = internal_api_token
        self._timeout_videos = timeout_videos_seconds
        self._timeout_videos_batch = timeout_videos_batch_seconds
        self._timeout_receipts = timeout_receipts_seconds
        self._timeout_receipts_manual = timeout_receipts_manual_seconds
        self._timeout_study_japanese = timeout_study_japanese_seconds
        self._timeout_default = timeout_default_seconds
        self._max_retries = max_retries
        self._client = client or httpx.AsyncClient(timeout=self._timeout_default)

    async def close(self) -> None:
        await self._client.aclose()

    async def send(
        self, *, decision: RouteDecision, ctx: KirokuRequestContext
    ) -> KirokuResponse:
        headers = self._build_headers(ctx)

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._dispatch(decision=decision, headers=headers)
                if response.status_code in {200, 201}:
                    return KirokuResponse(
                        ok=True,
                        status_code=response.status_code,
                        payload=_safe_json(response),
                    )

                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                retry_decision = evaluate_retry(
                    attempt=attempt,
                    max_attempts=self._max_retries,
                    status_code=response.status_code,
                    retry_after=retry_after,
                    timed_out=False,
                    transient_error=False,
                )
                if retry_decision.should_retry:
                    await asyncio.sleep(retry_decision.wait_seconds)
                    continue

                return KirokuResponse(
                    ok=False,
                    status_code=response.status_code,
                    error=map_http_error(response.status_code),
                    payload=_safe_json(response),
                )
            except httpx.TimeoutException:
                retry_decision = evaluate_retry(
                    attempt=attempt,
                    max_attempts=self._max_retries,
                    status_code=None,
                    retry_after=None,
                    timed_out=True,
                    transient_error=False,
                )
                if retry_decision.should_retry:
                    await asyncio.sleep(retry_decision.wait_seconds)
                    continue
                return KirokuResponse(
                    ok=False,
                    status_code=408,
                    error=ProcessingError(
                        status_code=408,
                        error_type=map_http_error(503).error_type,
                        user_message="Request timed out.",
                    ),
                )
            except httpx.TransportError:
                retry_decision = evaluate_retry(
                    attempt=attempt,
                    max_attempts=self._max_retries,
                    status_code=None,
                    retry_after=None,
                    timed_out=False,
                    transient_error=True,
                )
                if retry_decision.should_retry:
                    await asyncio.sleep(retry_decision.wait_seconds)
                    continue
                return KirokuResponse(
                    ok=False,
                    status_code=503,
                    error=map_http_error(503),
                )

        return KirokuResponse(ok=False, status_code=503, error=map_http_error(503))

    async def _dispatch(
        self, *, decision: RouteDecision, headers: dict[str, str]
    ) -> httpx.Response:
        url = f"{self._base_url}{decision.endpoint}"
        timeout = self._resolve_timeout(decision.endpoint)
        if decision.content_type == "application/json":
            return await self._client.request(
                "POST",
                url,
                json=decision.payload or {},
                headers=headers,
                timeout=timeout,
            )

        return await self._client.request(
            "POST",
            url,
            files=decision.multipart_files,
            data=decision.multipart_data or {},
            headers=headers,
            timeout=timeout,
        )

    def _resolve_timeout(self, endpoint: str) -> float:
        endpoint_timeouts = {
            "/api/v1/videos": self._timeout_videos,
            "/api/v1/videos/batch": self._timeout_videos_batch,
            "/api/v1/receipts": self._timeout_receipts,
            "/api/v1/receipts/manual": self._timeout_receipts_manual,
            "/api/v1/study-assets/japanese": self._timeout_study_japanese,
        }
        return endpoint_timeouts.get(endpoint, self._timeout_default)

    def _build_headers(self, ctx: KirokuRequestContext) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "X-Source": "discord-bot",
            "X-Source-Message-Id": ctx.message_id,
            "X-Source-User-Id": ctx.user_id,
            "Idempotency-Key": ctx.idempotency_key,
        }


def _safe_json(response: httpx.Response) -> dict[str, Any] | None:
    try:
        data = response.json()
        if isinstance(data, dict):
            return data
        return {"data": data}
    except Exception:
        return None


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = float(value)
        return parsed if parsed >= 0 else None
    except ValueError:
        return None

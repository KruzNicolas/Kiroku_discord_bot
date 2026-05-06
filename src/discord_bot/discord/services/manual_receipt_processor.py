from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import time
from typing import Any

from discord_bot.config import BotConfig
from discord_bot.domain.idempotency import build_idempotency_key
from discord_bot.domain.models import KirokuRequestContext, NormalizedMessage
from discord_bot.routing.channel_router import route_manual_receipt_payload
from discord_bot.security.allowlists import AllowlistPolicy, validate_message
from discord_bot.transport.kiroku_client import KirokuClient


class ManualReceiptDuplicateError(ValueError):
    pass


class ManualReceiptProcessor:
    def __init__(
        self,
        *,
        config: BotConfig,
        client: KirokuClient,
        metrics: Any,
        dedupe_store: OrderedDict[str, float] | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._metrics = metrics
        self._policy = AllowlistPolicy(
            guild_ids=config.allowed_guild_ids,
            user_ids=config.allowed_user_ids,
        )
        self._dedupe_store = dedupe_store if dedupe_store is not None else OrderedDict()

    def validate_interaction(self, interaction: Any) -> tuple[bool, str]:
        normalized = NormalizedMessage(
            guild_id=str(getattr(getattr(interaction, "guild", None), "id", "")),
            channel_id=str(getattr(getattr(interaction, "channel", None), "id", "")),
            channel_name=str(
                getattr(getattr(interaction, "channel", None), "name", "")
            ),
            user_id=str(getattr(getattr(interaction, "user", None), "id", "")),
            message_id=str(getattr(interaction, "id", "")),
            content="/receipt_manual",
            attachments=[],
        )
        validation = validate_message(self._policy, normalized)
        if not validation.allowed:
            return False, validation.reason or "Rejected by policy"

        expected_channel_id = self._config.route_channel_ids.get("receipts-manual", "")
        if normalized.channel_id != expected_channel_id:
            return (
                False,
                "Manual receipts only work in <#{channel_id}>. "
                "Dale, use that channel so routing and audit are consistent.".format(
                    channel_id=expected_channel_id
                ),
            )

        return True, ""

    async def submit(
        self,
        *,
        interaction: Any,
        payload: dict[str, Any],
    ):
        normalized = NormalizedMessage(
            guild_id=str(getattr(getattr(interaction, "guild", None), "id", "")),
            channel_id=str(getattr(getattr(interaction, "channel", None), "id", "")),
            channel_name=str(
                getattr(getattr(interaction, "channel", None), "name", "")
            ),
            user_id=str(getattr(getattr(interaction, "user", None), "id", "")),
            message_id=str(getattr(interaction, "id", "")),
            content="/receipt_manual",
            attachments=[],
        )

        self._check_duplicate(normalized=normalized, payload=payload)

        decision = route_manual_receipt_payload(
            channel_id=normalized.channel_id,
            route_channel_ids=self._config.route_channel_ids,
            payload=payload,
        )
        ctx = KirokuRequestContext(
            guild_id=normalized.guild_id,
            channel_id=normalized.channel_id,
            message_id=normalized.message_id,
            user_id=normalized.user_id,
            idempotency_key=build_idempotency_key(
                guild_id=normalized.guild_id,
                channel_id=normalized.channel_id,
                message_id=normalized.message_id,
            ),
        )
        response = await self._client.send(decision=decision, ctx=ctx)
        status = "success" if response.ok else "failure"
        self._metrics.inc_request(decision.endpoint, status)
        if not response.ok:
            error_type = (
                response.error.error_type.value if response.error else "unknown"
            )
            self._metrics.inc_failure(decision.endpoint, error_type)
        return response

    def _check_duplicate(
        self, *, normalized: NormalizedMessage, payload: dict[str, Any]
    ) -> None:
        now = time.monotonic()
        ttl = float(self._config.manual_receipt_dedupe_window_seconds)
        self._evict_expired(now=now, ttl=ttl)
        dedupe_key = self._build_dedupe_key(normalized=normalized, payload=payload)
        if dedupe_key in self._dedupe_store:
            raise ManualReceiptDuplicateError(
                "⚠️ This manual receipt was already submitted moments ago. "
                "No resend was performed to avoid duplicates."
            )

        self._dedupe_store[dedupe_key] = now

    def _evict_expired(self, *, now: float, ttl: float) -> None:
        expired_keys = [
            key for key, seen_at in self._dedupe_store.items() if now - seen_at > ttl
        ]
        for key in expired_keys:
            self._dedupe_store.pop(key, None)

    @staticmethod
    def _build_dedupe_key(
        *, normalized: NormalizedMessage, payload: dict[str, Any]
    ) -> str:
        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        return (
            f"{normalized.guild_id}:{normalized.channel_id}:{normalized.user_id}:"
            f"{payload_hash}"
        )

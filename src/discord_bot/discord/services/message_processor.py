from __future__ import annotations

from typing import Any

from discord_bot.attachments.normalizer import normalize_attachment
from discord_bot.config import BotConfig
from discord_bot.domain.idempotency import build_idempotency_key
from discord_bot.domain.models import KirokuRequestContext, NormalizedMessage
from discord_bot.observability.logging import CorrelationContext
from discord_bot.routing.channel_router import route_message
from discord_bot.security.allowlists import AllowlistPolicy, validate_message
from discord_bot.transport.kiroku_client import KirokuClient

from .feedback import DiscordFeedbackService


class MessageProcessor:
    def __init__(
        self,
        *,
        config: BotConfig,
        client: KirokuClient,
        logger: Any,
        metrics: Any,
        feedback: DiscordFeedbackService,
    ) -> None:
        self._config = config
        self._client = client
        self._logger = logger
        self._metrics = metrics
        self._feedback = feedback
        self._policy = AllowlistPolicy(
            guild_ids=config.allowed_guild_ids,
            user_ids=config.allowed_user_ids,
        )

    async def normalize_message(self, message: Any) -> NormalizedMessage:
        attachments = []
        for item in getattr(message, "attachments", []) or []:
            data = await item.read()
            attachments.append(
                normalize_attachment(
                    filename=item.filename,
                    content_type=item.content_type or "",
                    data=data,
                    max_size_bytes=self._config.max_attachment_size_bytes,
                )
            )

        return NormalizedMessage(
            guild_id=str(getattr(message.guild, "id", "")),
            channel_id=str(getattr(message.channel, "id", "")),
            channel_name=str(getattr(message.channel, "name", "")),
            user_id=str(getattr(message.author, "id", "")),
            message_id=str(getattr(message, "id", "")),
            content=message.content or "",
            attachments=attachments,
        )

    def validate(self, normalized: NormalizedMessage):
        return validate_message(self._policy, normalized)

    async def process(self, *, message: Any, normalized: NormalizedMessage) -> None:
        decision = route_message(normalized, self._config.route_channel_ids)
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

        context = CorrelationContext(
            source="discord-bot",
            guild_id=ctx.guild_id,
            channel_id=ctx.channel_id,
            message_id=ctx.message_id,
            user_id=ctx.user_id,
            endpoint=decision.endpoint,
            status_code=response.status_code,
        )

        if response.ok:
            await message.add_reaction("✅")
            self._logger.info(
                "Forwarded message successfully", extra={"context": context}
            )
            return

        await message.add_reaction("❌")
        user_message = (
            response.error.user_message if response.error else "Processing failed"
        )
        await message.reply(user_message)
        error_type = response.error.error_type.value if response.error else "unknown"
        self._metrics.inc_failure(decision.endpoint, error_type)
        self._logger.error("Forwarding failed", extra={"context": context})

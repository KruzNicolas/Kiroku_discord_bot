from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from discord_bot.attachments.normalizer import AttachmentNormalizationError
from discord_bot.config import BotConfig
from discord_bot.discord.handlers import DiscordMessageHandler, MessageHandlerDeps
from discord_bot.domain.models import ErrorType, ProcessingError
from discord_bot.transport.kiroku_client import KirokuResponse


def _config() -> BotConfig:
    return BotConfig(
        discord_bot_token="token",
        allowed_guild_ids={"g1"},
        allowed_user_ids={"u1"},
        api_base_url="https://api.example.com",
        internal_api_token="internal",
        route_channel_id_videos="c-videos",
        route_channel_id_receipts_photos="c-receipts",
        route_channel_id_receipts_manual="c-receipts-manual",
        route_channel_id_study_japanese="c-japanese",
        request_timeout_videos_seconds=120.0,
        request_timeout_videos_batch_seconds=120.0,
        request_timeout_receipts_seconds=300.0,
        request_timeout_receipts_manual_seconds=120.0,
        request_timeout_study_japanese_seconds=90.0,
        request_timeout_default_seconds=120.0,
    )


def _message(
    *, channel_id: str = "c-videos", content: str = "https://youtu.be/abc"
) -> Any:
    message = SimpleNamespace(
        author=SimpleNamespace(bot=False, id="u1"),
        guild=SimpleNamespace(id="g1"),
        channel=SimpleNamespace(id=channel_id, name="videos"),
        id="m1",
        content=content,
        attachments=[],
    )
    message.add_reaction = AsyncMock()
    message.clear_reaction = AsyncMock()
    message.reply = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_processing_reaction_removed_on_success() -> None:
    client = Mock()
    client.send = AsyncMock(return_value=KirokuResponse(ok=True, status_code=200))
    logger = Mock()
    metrics = Mock()
    handler = DiscordMessageHandler(
        MessageHandlerDeps(
            config=_config(), client=client, logger=logger, metrics=metrics
        )
    )

    message = _message()
    await handler.on_message(message)

    message.add_reaction.assert_any_await("⏳")
    message.add_reaction.assert_any_await("✅")
    message.clear_reaction.assert_awaited_once_with("⏳")


@pytest.mark.asyncio
async def test_processing_reaction_removed_on_failure() -> None:
    client = Mock()
    client.send = AsyncMock(
        return_value=KirokuResponse(
            ok=False,
            status_code=503,
            error=ProcessingError(
                status_code=503,
                error_type=ErrorType.TRANSIENT,
                user_message="Temporary upstream issue. Please retry shortly.",
            ),
        )
    )
    logger = Mock()
    metrics = Mock()
    handler = DiscordMessageHandler(
        MessageHandlerDeps(
            config=_config(), client=client, logger=logger, metrics=metrics
        )
    )

    message = _message()
    await handler.on_message(message)

    message.add_reaction.assert_any_await("⏳")
    message.add_reaction.assert_any_await("❌")
    message.clear_reaction.assert_awaited_once_with("⏳")


@pytest.mark.asyncio
async def test_processing_reaction_removed_on_routing_failure_after_added() -> None:
    client = Mock()
    client.send = AsyncMock()
    logger = Mock()
    metrics = Mock()
    handler = DiscordMessageHandler(
        MessageHandlerDeps(
            config=_config(), client=client, logger=logger, metrics=metrics
        )
    )

    message = _message(channel_id="c-unknown")
    await handler.on_message(message)

    message.add_reaction.assert_any_await("⏳")
    message.add_reaction.assert_any_await("❌")
    message.clear_reaction.assert_awaited_once_with("⏳")


@pytest.mark.asyncio
async def test_attachment_normalization_error_is_handled_gracefully() -> None:
    client = Mock()
    client.send = AsyncMock()
    logger = Mock()
    metrics = Mock()
    handler = DiscordMessageHandler(
        MessageHandlerDeps(
            config=_config(), client=client, logger=logger, metrics=metrics
        )
    )

    message = _message(channel_id="c-japanese", content="")
    attachment = SimpleNamespace(
        filename="study.jpg",
        content_type="image/jpeg",
        read=AsyncMock(
            side_effect=AttachmentNormalizationError("Unsupported attachment type")
        ),
    )
    message.attachments = [attachment]

    await handler.on_message(message)

    message.add_reaction.assert_awaited_once_with("❌")
    message.reply.assert_awaited_once_with("Unsupported attachment type")
    message.clear_reaction.assert_not_called()
    client.send.assert_not_called()


@pytest.mark.asyncio
async def test_help_manual_replies_with_template_and_does_not_forward() -> None:
    client = Mock()
    client.send = AsyncMock()
    logger = Mock()
    metrics = Mock()
    handler = DiscordMessageHandler(
        MessageHandlerDeps(
            config=_config(), client=client, logger=logger, metrics=metrics
        )
    )

    message = _message(channel_id="c-receipts-manual", content="!help-manual")
    await handler.on_message(message)

    message.reply.assert_awaited_once()
    reply_text = message.reply.await_args.args[0]
    assert "Manual receipts template" in reply_text
    assert (
        "Categories: Groceries, Pharmacy, Transport, Utilities, Subscriptions, Debt, Leisure, Others"
        in reply_text
    )
    assert "/receipt_manual" in reply_text
    assert 'store="Falabella"' in reply_text
    assert 'items="Item | Quantity | Price ; Item 2 | Quantity | Price"' in reply_text
    assert "Arepas | 1 | 5000" in reply_text
    assert "Example:" in reply_text
    client.send.assert_not_called()
    message.add_reaction.assert_not_called()
    message.clear_reaction.assert_not_called()


@pytest.mark.asyncio
async def test_help_manual_still_enforces_allowlist() -> None:
    config = BotConfig(
        discord_bot_token="token",
        allowed_guild_ids={"g1"},
        allowed_user_ids={"u2"},
        api_base_url="https://api.example.com",
        internal_api_token="internal",
        route_channel_id_videos="c-videos",
        route_channel_id_receipts_photos="c-receipts",
        route_channel_id_receipts_manual="c-receipts-manual",
        route_channel_id_study_japanese="c-japanese",
        request_timeout_videos_seconds=120.0,
        request_timeout_videos_batch_seconds=120.0,
        request_timeout_receipts_seconds=300.0,
        request_timeout_receipts_manual_seconds=120.0,
        request_timeout_study_japanese_seconds=90.0,
        request_timeout_default_seconds=120.0,
    )
    client = Mock()
    client.send = AsyncMock()
    logger = Mock()
    metrics = Mock()
    handler = DiscordMessageHandler(
        MessageHandlerDeps(config=config, client=client, logger=logger, metrics=metrics)
    )

    message = _message(channel_id="c-receipts-manual", content="!help-manual")
    await handler.on_message(message)

    message.add_reaction.assert_awaited_once_with("❌")
    message.reply.assert_awaited_once_with("User is not allowlisted")
    client.send.assert_not_called()


@pytest.mark.asyncio
async def test_non_command_receipts_manual_message_routes_normally() -> None:
    client = Mock()
    client.send = AsyncMock(return_value=KirokuResponse(ok=True, status_code=201))
    logger = Mock()
    metrics = Mock()
    handler = DiscordMessageHandler(
        MessageHandlerDeps(
            config=_config(), client=client, logger=logger, metrics=metrics
        )
    )

    message = _message(
        channel_id="c-receipts-manual",
        content='/receipt_manual date=2026-03-20 category=Others store="Shop" items="Item|1|100"',
    )
    await handler.on_message(message)

    client.send.assert_awaited_once()
    message.add_reaction.assert_any_await("⏳")
    message.add_reaction.assert_any_await("✅")
    message.clear_reaction.assert_awaited_once_with("⏳")

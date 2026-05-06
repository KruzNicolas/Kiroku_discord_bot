from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from discord import app_commands

from discord_bot.config import BotConfig
from discord_bot.main import build_handler, sync_app_commands


def _config(*, guild_ids: set[str], sync_global_commands: bool = False) -> BotConfig:
    return BotConfig(
        discord_bot_token="token",
        allowed_guild_ids=guild_ids,
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
        manual_receipt_dedupe_window_seconds=60,
        sync_global_commands=sync_global_commands,
    )


@pytest.mark.asyncio
async def test_sync_app_commands_syncs_each_allowlisted_guild_only() -> None:
    tree = Mock()
    tree.copy_global_to = Mock()
    tree.sync = AsyncMock(side_effect=[["cmd-1"], ["cmd-2"]])
    logger = Mock()
    config = _config(guild_ids={"20", "10"}, sync_global_commands=False)

    await sync_app_commands(tree=tree, config=config, logger=logger)

    assert tree.copy_global_to.call_count == 2
    assert tree.sync.await_count == 2
    guild_ids = [str(call.kwargs["guild"].id) for call in tree.sync.await_args_list]
    assert guild_ids == ["10", "20"]
    logger.exception.assert_not_called()


@pytest.mark.asyncio
async def test_sync_app_commands_continues_when_one_guild_fails() -> None:
    tree = Mock()
    tree.copy_global_to = Mock()
    failure = app_commands.CommandLimitReached(guild_id=10, limit=100)
    tree.sync = AsyncMock(side_effect=[failure, ["cmd-2"]])
    logger = Mock()
    config = _config(guild_ids={"10", "20"})

    await sync_app_commands(tree=tree, config=config, logger=logger)

    assert tree.sync.await_count == 2
    logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_sync_app_commands_global_sync_is_optional() -> None:
    tree = Mock()
    tree.copy_global_to = Mock()
    tree.sync = AsyncMock(side_effect=[["guild-cmd"], ["global-cmd"]])
    logger = Mock()
    config = _config(guild_ids={"10"}, sync_global_commands=True)

    await sync_app_commands(tree=tree, config=config, logger=logger)

    assert tree.sync.await_count == 2
    assert tree.sync.await_args_list[0].kwargs.keys() == {"guild"}
    assert tree.sync.await_args_list[1].kwargs == {}


def test_build_handler_wires_kiroku_client_instance() -> None:
    config = _config(guild_ids={"123456789012345678"})

    handler, kiroku_client = build_handler(config)

    assert handler is not None
    assert kiroku_client is not None

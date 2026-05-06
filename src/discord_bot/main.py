from __future__ import annotations

import asyncio
from contextlib import suppress
import signal

import discord
from discord import app_commands

from discord_bot.config import BotConfig
from discord_bot.discord.handlers import (
    MANUAL_RECEIPT_COMMAND_DESCRIPTION,
    DiscordMessageHandler,
    MessageHandlerDeps,
)
from discord_bot.observability.logging import get_logger
from discord_bot.observability.metrics import MetricsRegistry
from discord_bot.transport.kiroku_client import KirokuClient


def build_handler(config: BotConfig) -> tuple[DiscordMessageHandler, KirokuClient]:
    logger = get_logger()
    metrics = MetricsRegistry()
    kiroku_client = KirokuClient(
        base_url=config.api_base_url,
        internal_api_token=config.internal_api_token,
        timeout_videos_seconds=config.request_timeout_videos_seconds,
        timeout_videos_batch_seconds=config.request_timeout_videos_batch_seconds,
        timeout_receipts_seconds=config.request_timeout_receipts_seconds,
        timeout_receipts_manual_seconds=config.request_timeout_receipts_manual_seconds,
        timeout_study_japanese_seconds=config.request_timeout_study_japanese_seconds,
        timeout_default_seconds=config.request_timeout_default_seconds,
        max_retries=config.max_retries,
    )
    deps = MessageHandlerDeps(
        config=config, client=kiroku_client, logger=logger, metrics=metrics
    )
    return DiscordMessageHandler(deps), kiroku_client


async def sync_app_commands(
    tree: discord.app_commands.CommandTree,
    config: BotConfig,
    logger,
) -> None:
    for guild_id in sorted(config.allowed_guild_ids):
        try:
            guild = discord.Object(id=int(guild_id))
            tree.copy_global_to(guild=guild)
            synced = await tree.sync(guild=guild)
            logger.info(
                "Synced guild app commands",
                extra={"guild_id": guild_id, "count": len(synced)},
            )
        except (ValueError, app_commands.AppCommandError, discord.DiscordException):
            logger.exception(
                "Failed to sync guild app commands",
                extra={"guild_id": guild_id},
            )

    if config.sync_global_commands:
        try:
            synced = await tree.sync()
            logger.info(
                "Synced global app commands",
                extra={"count": len(synced)},
            )
        except (app_commands.AppCommandError, discord.DiscordException):
            logger.exception("Failed to sync global app commands")


async def _run_async() -> None:
    config = BotConfig.from_env()
    handler, kiroku_client = build_handler(config)
    logger = get_logger()

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    tree = discord.app_commands.CommandTree(client)

    @tree.command(
        name="receipt_manual",
        description=MANUAL_RECEIPT_COMMAND_DESCRIPTION,
    )
    async def receipt_manual(interaction: discord.Interaction) -> None:
        await handler.open_manual_receipt_modal(interaction)

    @client.event
    async def on_ready() -> None:
        await sync_app_commands(tree=tree, config=config, logger=logger)

    @client.event
    async def on_message(message):
        await handler.on_message(message)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_shutdown(sig: signal.Signals) -> None:
        logger.info("Shutdown signal received", extra={"signal": sig.name})
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_shutdown, sig)
        except NotImplementedError:
            # Windows event loop may not support signal handlers.
            pass

    discord_task = asyncio.create_task(client.start(config.discord_bot_token))
    stop_task = asyncio.create_task(stop_event.wait())

    try:
        done, _ = await asyncio.wait(
            {discord_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if stop_task in done and not discord_task.done():
            await client.close()

        await discord_task
    finally:
        stop_task.cancel()
        with suppress(asyncio.CancelledError):
            await stop_task
        await kiroku_client.close()


def run() -> None:
    asyncio.run(_run_async())


if __name__ == "__main__":
    run()

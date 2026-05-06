from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from discord_bot.config import BotConfig
from discord_bot.discord.handlers import (
    DiscordMessageHandler,
    ManualReceiptDatePickerView,
    MessageHandlerDeps,
)
from discord_bot.routing.channel_router import (
    RECEIPT_MANUAL_ALLOWED_CATEGORIES,
    parse_receipt_manual_fields,
)
from discord_bot.transport.kiroku_client import KirokuResponse


def _config(*, allowed_users: set[str] | None = None) -> BotConfig:
    return BotConfig(
        discord_bot_token="token",
        allowed_guild_ids={"g1"},
        allowed_user_ids=allowed_users or {"u1"},
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
    )


def _handler(
    *, allowed_users: set[str] | None = None
) -> tuple[DiscordMessageHandler, Any]:
    client = Mock()
    client.send = AsyncMock(return_value=KirokuResponse(ok=True, status_code=201))
    logger = Mock()
    metrics = Mock()
    handler = DiscordMessageHandler(
        MessageHandlerDeps(
            config=_config(allowed_users=allowed_users),
            client=client,
            logger=logger,
            metrics=metrics,
        )
    )
    return handler, client


def _interaction(*, channel_id: str = "c-receipts-manual", user_id: str = "u1") -> Any:
    response = SimpleNamespace(
        is_done=Mock(return_value=False),
        defer=AsyncMock(),
        send_message=AsyncMock(),
        send_modal=AsyncMock(),
    )
    return SimpleNamespace(
        id="ix-1",
        guild=SimpleNamespace(id="g1"),
        channel=SimpleNamespace(
            id=channel_id, name="receipts-manual", send=AsyncMock()
        ),
        user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(delete=AsyncMock(), edit=AsyncMock()),
        response=response,
        followup=SimpleNamespace(send=AsyncMock()),
    )


@pytest.mark.asyncio
async def test_submit_manual_receipt_modal_duplicate_is_rejected_without_resend() -> (
    None
):
    handler, client = _handler()
    interaction = _interaction()

    await handler.submit_manual_receipt_modal(
        interaction=interaction,
        date="2026-03-20",
        category="Groceries",
        store="Seijo Ishii",
        items="Milk|1|298",
    )
    await handler.submit_manual_receipt_modal(
        interaction=interaction,
        date="2026-03-20",
        category="Groceries",
        store="Seijo Ishii",
        items="Milk|1|298",
    )

    client.send.assert_awaited_once()
    interaction.followup.send.assert_awaited()
    duplicate_error = interaction.followup.send.await_args.args[0]
    assert "already submitted" in duplicate_error.lower()


@pytest.mark.asyncio
async def test_submit_manual_receipt_modal_maps_payload_and_forwards() -> None:
    handler, client = _handler()
    interaction = _interaction()

    await handler.submit_manual_receipt_modal(
        interaction=interaction,
        date="2026-03-20",
        category="Groceries",
        store="Seijo Ishii",
        items="Milk|1|298;Eggs|1|258",
    )

    client.send.assert_awaited_once()
    call = client.send.await_args.kwargs
    decision = call["decision"]
    ctx = call["ctx"]

    assert decision.endpoint == "/api/v1/receipts/manual"
    assert decision.payload == {
        "date": "2026-03-20",
        "category": "Groceries",
        "store": "Seijo Ishii",
        "items": [
            {"product": "Milk", "quantity": 1.0, "price": 298.0},
            {"product": "Eggs", "quantity": 1.0, "price": 258.0},
        ],
    }
    assert ctx.guild_id == "g1"
    assert ctx.channel_id == "c-receipts-manual"
    assert ctx.user_id == "u1"
    assert ctx.idempotency_key == "discord:g1:c-receipts-manual:ix-1"
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    interaction.response.send_message.assert_not_called()
    interaction.followup.send.assert_not_called()
    interaction.channel.send.assert_awaited_once()
    summary = interaction.channel.send.await_args.args[0]
    assert "✅ Manual receipt submitted" in summary
    assert "date: 2026-03-20" in summary
    assert "category: Groceries" in summary
    assert "store: Seijo Ishii" in summary
    assert "items: 2" in summary
    assert "total: 556.00" in summary


@pytest.mark.asyncio
async def test_submit_manual_receipt_modal_validation_failure_is_ephemeral() -> None:
    handler, client = _handler()
    interaction = _interaction()

    await handler.submit_manual_receipt_modal(
        interaction=interaction,
        date="03-20-2026",
        category="Groceries",
        store="Seijo Ishii",
        items="Milk|1|298",
    )

    client.send.assert_not_called()
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    interaction.response.send_message.assert_not_called()
    interaction.followup.send.assert_awaited_once()
    error_text = interaction.followup.send.await_args.args[0]
    assert "Date must use YYYY-MM-DD or MM-DD format" in error_text
    assert interaction.followup.send.await_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_submit_manual_receipt_modal_reuses_done_interaction_without_defer() -> (
    None
):
    handler, _ = _handler()
    interaction = _interaction()
    interaction.response.is_done.return_value = True

    await handler.submit_manual_receipt_modal(
        interaction=interaction,
        date="2026-03-20",
        category="Groceries",
        store="Falabella",
        items="Arepas|1|5000",
    )

    interaction.response.defer.assert_not_called()
    interaction.followup.send.assert_not_called()
    interaction.channel.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_open_manual_receipt_modal_rejects_wrong_channel_with_guidance() -> None:
    handler, _ = _handler()
    interaction = _interaction(channel_id="c-videos")

    await handler.open_manual_receipt_modal(interaction)

    interaction.response.send_modal.assert_not_called()
    interaction.response.send_message.assert_awaited_once()
    msg = interaction.response.send_message.await_args.args[0]
    assert "Manual receipts only work in" in msg
    assert "<#c-receipts-manual>" in msg
    assert interaction.response.send_message.await_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_open_manual_receipt_modal_rejects_non_allowlisted_user() -> None:
    handler, _ = _handler(allowed_users={"u2"})
    interaction = _interaction(user_id="u1")

    await handler.open_manual_receipt_modal(interaction)

    interaction.response.send_modal.assert_not_called()
    interaction.response.send_message.assert_awaited_once_with(
        "User is not allowlisted", ephemeral=True
    )


@pytest.mark.asyncio
async def test_open_manual_receipt_modal_sends_date_picker_view() -> None:
    handler, _ = _handler()
    interaction = _interaction()

    await handler.open_manual_receipt_modal(interaction)

    interaction.response.send_message.assert_awaited_once()
    kwargs = interaction.response.send_message.await_args.kwargs
    assert kwargs["ephemeral"] is True
    assert isinstance(kwargs["view"], ManualReceiptDatePickerView)
    assert len(kwargs["view"].children) == 2
    category_select = kwargs["view"].children[0]
    month_select = kwargs["view"].children[1]
    assert [option.value for option in category_select.options] == list(
        RECEIPT_MANUAL_ALLOWED_CATEGORIES
    )
    assert len(month_select.options) == 12
    assert interaction.response.send_modal.await_count == 0


@pytest.mark.asyncio
async def test_date_picker_view_opens_modal_when_month_selected() -> None:
    handler, _ = _handler()
    interaction = _interaction()
    view = ManualReceiptDatePickerView(handler)
    view.category = "Groceries"
    view.month = "03"

    await view.handle_selection(interaction)

    interaction.response.send_modal.assert_awaited_once()
    modal = interaction.response.send_modal.await_args.args[0]
    current_day = date.today().day
    expected_day = current_day
    try:
        _ = date(date.today().year, 3, current_day)
    except ValueError:
        expected_day = 1

    assert modal.date.default == f"{date.today().year}-03-{expected_day:02d}"
    assert modal.category.default == "Groceries"


@pytest.mark.asyncio
async def test_date_picker_view_partial_selection_does_not_send_intermediate_messages() -> (
    None
):
    handler, _ = _handler()
    interaction = _interaction()
    view = ManualReceiptDatePickerView(handler)

    view.month = "03"
    await view.handle_selection(interaction)

    interaction.response.defer.assert_awaited_once_with()
    interaction.response.send_message.assert_not_called()
    interaction.response.send_modal.assert_not_called()

    view.month = None
    view.category = "Groceries"
    await view.handle_selection(interaction)

    assert interaction.response.defer.await_count == 2
    interaction.response.send_message.assert_not_called()
    interaction.response.send_modal.assert_not_called()


@pytest.mark.asyncio
async def test_submit_manual_receipt_modal_success_attempts_step_message_cleanup() -> (
    None
):
    handler, _ = _handler()
    interaction = _interaction()
    initial_step_message = SimpleNamespace(delete=AsyncMock(), edit=AsyncMock())

    await handler.submit_manual_receipt_modal(
        interaction=interaction,
        date="2026-03-20",
        category="Groceries",
        store="Seijo Ishii",
        items="Milk|1|298",
        initial_step_message=initial_step_message,
    )

    initial_step_message.delete.assert_awaited_once()
    initial_step_message.edit.assert_not_called()


def test_parse_receipt_manual_fields_maps_mm_dd_to_current_year() -> None:
    payload = parse_receipt_manual_fields(
        date="03-20",
        category="Groceries",
        store="Seijo Ishii",
        items="Milk|1|298",
    )

    assert payload["date"] == f"{date.today().year}-03-20"


def test_parse_receipt_manual_fields_accepts_items_with_spaces() -> None:
    payload = parse_receipt_manual_fields(
        date="2026-03-20",
        category="Groceries",
        store="Seijo Ishii",
        items="Milk | 1 | 298 ; Bread | 1 | 198",
    )

    assert payload["items"] == [
        {"product": "Milk", "quantity": 1.0, "price": 298.0},
        {"product": "Bread", "quantity": 1.0, "price": 198.0},
    ]


def test_parse_receipt_manual_fields_rejects_category_outside_whitelist() -> None:
    with pytest.raises(ValueError) as exc_info:
        parse_receipt_manual_fields(
            date="2026-03-20",
            category="Pets",
            store="Falabella",
            items="Arepas|1|5000",
        )

    assert "Category must be one of:" in str(exc_info.value)
    assert "Groceries" in str(exc_info.value)
    assert "Others" in str(exc_info.value)

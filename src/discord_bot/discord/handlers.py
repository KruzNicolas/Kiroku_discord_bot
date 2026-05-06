from __future__ import annotations

from datetime import date
from dataclasses import dataclass
from typing import Any

import discord

from discord_bot.attachments.normalizer import AttachmentNormalizationError
from discord_bot.config import BotConfig
from discord_bot.domain.models import NormalizedMessage
from discord_bot.discord.services import (
    DiscordFeedbackService,
    ManualReceiptProcessor,
    MessageProcessor,
)
from discord_bot.discord.services.manual_receipt_processor import (
    ManualReceiptDuplicateError,
)
from discord_bot.routing.channel_router import (
    RECEIPT_MANUAL_ALLOWED_CATEGORIES,
    RoutingError,
    parse_receipt_manual_fields,
)
from discord_bot.transport.kiroku_client import KirokuClient

MANUAL_RECEIPT_HELP_TRIGGER = "!help-manual"
MANUAL_RECEIPT_COMMAND_DESCRIPTION = "Open manual receipt flow. Items format: Item | Quantity | Price ; Item 2 | Quantity | Price"
MANUAL_RECEIPT_ALLOWED_CATEGORIES_TEXT = ", ".join(RECEIPT_MANUAL_ALLOWED_CATEGORIES)
MANUAL_RECEIPT_HELP_TEXT = (
    "Manual receipts template (copy/paste):\n"
    f"Categories: {MANUAL_RECEIPT_ALLOWED_CATEGORIES_TEXT}\n"
    '`/receipt_manual date=YYYY-MM-DD category=Others store="Falabella" '
    'items="Item | Quantity | Price ; Item 2 | Quantity | Price"`\n\n'
    "Example:\n"
    '`/receipt_manual date=2026-03-20 category=Groceries store="Falabella" '
    'items="Arepas | 1 | 5000 ; Jugo | 2 | 2500"`'
)


class ManualReceiptModal(discord.ui.Modal):
    def __init__(
        self,
        handler: "DiscordMessageHandler",
        *,
        selected_month_day: str | None = None,
        selected_category: str | None = None,
        initial_step_message: Any | None = None,
    ) -> None:
        super().__init__(title="Manual Receipt")
        self._handler = handler
        self._selected_month_day = selected_month_day
        self._initial_step_message = initial_step_message
        date_preview = _build_current_year_date(selected_month_day)

        self.date = discord.ui.TextInput(
            label="Date (optional override)",
            placeholder="MM-DD or YYYY-MM-DD (empty uses selected date)",
            required=False,
            max_length=10,
            default=date_preview,
        )
        self.category = discord.ui.TextInput(
            label="Category (fixed set)",
            placeholder="Groceries | Pharmacy | ... | Others",
            required=True,
            max_length=64,
            default=selected_category,
        )
        self.store = discord.ui.TextInput(
            label="Store",
            placeholder="Falabella",
            required=True,
            max_length=128,
        )
        self.items = discord.ui.TextInput(
            label="Items (Item | Quantity | Price)",
            placeholder="Arepas | 1 | 5000 ; Jugo | 2 | 2500",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=1500,
        )

        self.add_item(self.date)
        self.add_item(self.category)
        self.add_item(self.store)
        self.add_item(self.items)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        resolved_date = str(self.date.value or "").strip() or str(
            self._selected_month_day or ""
        )
        await self._handler.submit_manual_receipt_modal(
            interaction=interaction,
            date=resolved_date,
            category=str(self.category.value or ""),
            store=str(self.store.value or ""),
            items=str(self.items.value or ""),
            initial_step_message=self._initial_step_message,
        )


class ManualReceiptMonthSelect(discord.ui.Select):
    def __init__(self, view: "ManualReceiptDatePickerView") -> None:
        options = [
            discord.SelectOption(label=f"{month:02d}", value=f"{month:02d}")
            for month in range(1, 13)
        ]
        super().__init__(
            placeholder="Pick month",
            options=options,
            min_values=1,
            max_values=1,
        )
        self._date_view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        self._date_view.month = self.values[0]
        await self._date_view.handle_selection(interaction)


class ManualReceiptDatePickerView(discord.ui.View):
    def __init__(self, handler: "DiscordMessageHandler") -> None:
        super().__init__(timeout=180)
        self._handler = handler
        self.month: str | None = None
        self.category: str | None = None

        self.add_item(ManualReceiptCategorySelect(self))
        self.add_item(ManualReceiptMonthSelect(self))

    async def handle_selection(self, interaction: discord.Interaction) -> None:
        if not self.category or not self.month:
            if not interaction.response.is_done():
                await interaction.response.defer()
            return

        await interaction.response.send_modal(
            self._handler._build_manual_receipt_modal(
                selected_month_day=_build_prefill_month_day(self.month),
                selected_category=self.category,
                initial_step_message=getattr(interaction, "message", None),
            )
        )


class ManualReceiptCategorySelect(discord.ui.Select):
    def __init__(self, view: "ManualReceiptDatePickerView") -> None:
        options = [
            discord.SelectOption(label=category, value=category)
            for category in RECEIPT_MANUAL_ALLOWED_CATEGORIES
        ]
        super().__init__(
            placeholder="Pick category",
            options=options,
            min_values=1,
            max_values=1,
        )
        self._date_view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        self._date_view.category = self.values[0]
        await self._date_view.handle_selection(interaction)


def _build_current_year_date(month_day: str | None) -> str | None:
    if not month_day:
        return None
    try:
        month, day = month_day.split("-", maxsplit=1)
        month_int = int(month)
        day_int = int(day)
    except ValueError:
        return None

    current_year = date.today().year
    return f"{current_year}-{month_int:02d}-{day_int:02d}"


def _build_prefill_month_day(selected_month: str | None) -> str | None:
    if not selected_month:
        return None

    try:
        month_int = int(selected_month)
    except ValueError:
        return None

    if month_int < 1 or month_int > 12:
        return None

    today = date.today()
    fallback_day = today.day
    try:
        _ = date(today.year, month_int, fallback_day)
    except ValueError:
        fallback_day = 1

    return f"{month_int:02d}-{fallback_day:02d}"


@dataclass
class MessageHandlerDeps:
    config: BotConfig
    client: KirokuClient
    logger: Any
    metrics: Any


class DiscordMessageHandler:
    def __init__(self, deps: MessageHandlerDeps) -> None:
        self._deps = deps
        self._feedback = DiscordFeedbackService()
        self._message_processor = MessageProcessor(
            config=deps.config,
            client=deps.client,
            logger=deps.logger,
            metrics=deps.metrics,
            feedback=self._feedback,
        )
        self._manual_processor = ManualReceiptProcessor(
            config=deps.config,
            client=deps.client,
            metrics=deps.metrics,
        )

    async def on_message(self, message: Any) -> None:
        if getattr(message.author, "bot", False):
            return

        processing_reaction_added = False

        try:
            normalized = await self._message_processor.normalize_message(message)
            validation = self._message_processor.validate(normalized)
            if not validation.allowed:
                await self._feedback.fail_feedback(
                    message, validation.reason or "Rejected by policy"
                )
                return

            if self._is_manual_help_command(normalized.content):
                await message.reply(MANUAL_RECEIPT_HELP_TEXT)
                return

            await message.add_reaction("⏳")
            processing_reaction_added = True
            await self._message_processor.process(
                message=message, normalized=normalized
            )
        except (RoutingError, AttachmentNormalizationError) as exc:
            await self._feedback.fail_feedback(message, str(exc))
            return
        finally:
            if processing_reaction_added:
                await self._feedback.clear_processing_reaction(message)

    async def open_manual_receipt_modal(self, interaction: Any) -> None:
        authorized, reason = self._manual_processor.validate_interaction(interaction)
        if not authorized:
            await self._feedback.respond_interaction_ephemeral(interaction, reason)
            return

        await interaction.response.send_message(
            "Step 1/2 — Pick category and month, then we open the receipt modal.",
            view=ManualReceiptDatePickerView(self),
            ephemeral=True,
        )

    async def submit_manual_receipt_modal(
        self,
        *,
        interaction: Any,
        date: str,
        category: str,
        store: str,
        items: str,
        initial_step_message: Any | None = None,
    ) -> None:
        authorized, reason = self._manual_processor.validate_interaction(interaction)
        if not authorized:
            await self._feedback.respond_interaction_ephemeral(interaction, reason)
            return

        deferred = False
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
            deferred = True

        try:
            payload = parse_receipt_manual_fields(
                date=date,
                category=category,
                store=store,
                items=items,
            )
            response = await self._manual_processor.submit(
                interaction=interaction,
                payload=payload,
            )

            if response.ok:
                await self._feedback.send_manual_receipt_public_summary(
                    interaction=interaction,
                    payload=payload,
                )
                await self._feedback.cleanup_manual_receipt_step_message(
                    initial_step_message=initial_step_message
                )
                return

            user_message = (
                response.error.user_message if response.error else "Processing failed"
            )
            await self._feedback.respond_interaction_ephemeral(
                interaction,
                f"❌ {user_message}",
                force_followup=deferred,
            )
        except (RoutingError, ManualReceiptDuplicateError) as exc:
            await self._feedback.respond_interaction_ephemeral(
                interaction,
                f"❌ {str(exc)}",
                force_followup=deferred,
            )

    def _build_manual_receipt_modal(
        self,
        *,
        selected_month_day: str | None = None,
        selected_category: str | None = None,
        initial_step_message: Any | None = None,
    ) -> discord.ui.Modal:
        return ManualReceiptModal(
            self,
            selected_month_day=selected_month_day,
            selected_category=selected_category,
            initial_step_message=initial_step_message,
        )

    @staticmethod
    def _is_manual_help_command(content: str) -> bool:
        return content.strip() == MANUAL_RECEIPT_HELP_TRIGGER

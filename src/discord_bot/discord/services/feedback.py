from __future__ import annotations

from typing import Any


class DiscordFeedbackService:
    async def fail_feedback(self, message: Any, reason: str) -> None:
        await message.add_reaction("❌")
        await message.reply(reason)

    async def clear_processing_reaction(self, message: Any) -> None:
        try:
            await message.clear_reaction("⏳")
        except Exception:
            return

    async def respond_interaction_ephemeral(
        self,
        interaction: Any,
        content: str,
        *,
        force_followup: bool = False,
    ) -> None:
        if force_followup or interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=True)
            return
        await interaction.response.send_message(content, ephemeral=True)

    async def send_manual_receipt_public_summary(
        self,
        *,
        interaction: Any,
        payload: dict[str, Any],
    ) -> None:
        items = payload.get("items", [])
        item_count = len(items)
        total_amount = sum(
            float(item.get("quantity", 0)) * float(item.get("price", 0))
            for item in items
        )
        summary = (
            "✅ Manual receipt submitted"
            f" — date: {payload.get('date', '-')};"
            f" category: {payload.get('category', '-')};"
            f" store: {payload.get('store', '-')};"
            f" items: {item_count};"
            f" total: {total_amount:.2f}"
        )
        await interaction.channel.send(summary)

    async def cleanup_manual_receipt_step_message(
        self, *, initial_step_message: Any | None
    ) -> None:
        if initial_step_message is None:
            return

        delete = getattr(initial_step_message, "delete", None)
        if callable(delete):
            try:
                await delete()
                return
            except Exception:
                pass

        edit = getattr(initial_step_message, "edit", None)
        if callable(edit):
            try:
                await edit(content="✅ Done.", view=None)
            except Exception:
                return

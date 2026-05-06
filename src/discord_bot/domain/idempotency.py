from __future__ import annotations


def build_idempotency_key(*, guild_id: str, channel_id: str, message_id: str) -> str:
    return f"discord:{guild_id}:{channel_id}:{message_id}"

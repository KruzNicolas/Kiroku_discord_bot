from __future__ import annotations

from dataclasses import dataclass

from discord_bot.domain.models import ChannelKind


@dataclass(frozen=True)
class ChannelPolicy:
    channel_name: str
    kind: ChannelKind
    endpoint_single: str
    endpoint_batch: str | None
    accepts_attachments: bool


POLICIES: dict[str, ChannelPolicy] = {
    "videos": ChannelPolicy(
        channel_name="videos",
        kind=ChannelKind.VIDEOS,
        endpoint_single="/api/v1/videos",
        endpoint_batch="/api/v1/videos/batch",
        accepts_attachments=False,
    ),
    "receipts": ChannelPolicy(
        channel_name="receipts",
        kind=ChannelKind.RECEIPTS,
        endpoint_single="/api/v1/receipts",
        endpoint_batch=None,
        accepts_attachments=True,
    ),
    "receipts-manual": ChannelPolicy(
        channel_name="receipts-manual",
        kind=ChannelKind.RECEIPTS_MANUAL,
        endpoint_single="/api/v1/receipts/manual",
        endpoint_batch=None,
        accepts_attachments=False,
    ),
    "japanese": ChannelPolicy(
        channel_name="japanese",
        kind=ChannelKind.JAPANESE,
        endpoint_single="/api/v1/study-assets/japanese",
        endpoint_batch=None,
        accepts_attachments=True,
    ),
}

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChannelKind(str, Enum):
    VIDEOS = "videos"
    RECEIPTS = "receipts"
    RECEIPTS_MANUAL = "receipts-manual"
    JAPANESE = "japanese"


@dataclass(frozen=True)
class NormalizedAttachment:
    filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class NormalizedMessage:
    guild_id: str
    channel_id: str
    channel_name: str
    user_id: str
    message_id: str
    content: str
    attachments: list[NormalizedAttachment] = field(default_factory=list)


@dataclass(frozen=True)
class ValidationResult:
    allowed: bool
    reason: str | None = None


@dataclass(frozen=True)
class RouteDecision:
    endpoint: str
    method: str
    content_type: str
    payload: dict[str, Any] | None = None
    multipart_files: dict[str, tuple[str, bytes, str]] | None = None
    multipart_data: dict[str, str] | None = None


@dataclass(frozen=True)
class KirokuRequestContext:
    guild_id: str
    channel_id: str
    message_id: str
    user_id: str
    idempotency_key: str


@dataclass(frozen=True)
class RetryDecision:
    should_retry: bool
    wait_seconds: float = 0.0


class ErrorType(str, Enum):
    VALIDATION = "validation"
    INTEGRATION = "integration"
    TRANSIENT = "transient"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProcessingError:
    status_code: int | None
    error_type: ErrorType
    user_message: str

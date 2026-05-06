from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class CorrelationContext:
    source: str
    guild_id: str
    channel_id: str
    message_id: str
    user_id: str
    endpoint: str
    status_code: int | None = None


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "context") and record.context is not None:
            payload["context"] = asdict(record.context)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = "discord_bot") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger

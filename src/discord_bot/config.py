from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import find_dotenv, load_dotenv


def _parse_csv_ids(raw: str) -> set[str]:
    return {item.strip() for item in raw.split(",") if item.strip()}


def _parse_bool(raw: str, *, default: bool = False) -> bool:
    value = raw.strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


_SNOWFLAKE_PATTERN = re.compile(r"^\d{17,20}$")
_MIN_TIMEOUT_SECONDS = 1.0
_MAX_TIMEOUT_SECONDS = 600.0
_MIN_RETRIES = 0
_MAX_RETRIES = 5


def _validate_snowflake(value: str, *, env_name: str) -> None:
    if not _SNOWFLAKE_PATTERN.match(value):
        raise ValueError(
            f"{env_name} must be a numeric Discord snowflake-like string (17-20 digits)."
        )


def _validate_snowflake_set(values: set[str], *, env_name: str) -> None:
    if not values:
        raise ValueError(f"{env_name} must contain at least one Discord ID.")
    invalid = sorted(value for value in values if not _SNOWFLAKE_PATTERN.match(value))
    if invalid:
        raise ValueError(
            f"{env_name} contains invalid Discord IDs: {', '.join(invalid)}. "
            "Expected numeric snowflake-like strings (17-20 digits)."
        )


def _validate_timeout(value: float, *, env_name: str) -> None:
    if value < _MIN_TIMEOUT_SECONDS or value > _MAX_TIMEOUT_SECONDS:
        raise ValueError(
            f"{env_name} must be between {_MIN_TIMEOUT_SECONDS:.0f} and "
            f"{_MAX_TIMEOUT_SECONDS:.0f} seconds. Got: {value}."
        )


def _validate_retries(value: int, *, env_name: str) -> None:
    if value < _MIN_RETRIES or value > _MAX_RETRIES:
        raise ValueError(
            f"{env_name} must be between {_MIN_RETRIES} and {_MAX_RETRIES}. Got: {value}."
        )


def _validate_api_base_url(value: str) -> None:
    if " " in value:
        raise ValueError("API_BASE_URL must not contain spaces.")

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            "API_BASE_URL must be a valid absolute URL with http or https scheme."
        )


@dataclass(frozen=True)
class BotConfig:
    discord_bot_token: str
    allowed_guild_ids: set[str]
    allowed_user_ids: set[str]
    api_base_url: str
    internal_api_token: str
    route_channel_id_videos: str
    route_channel_id_receipts_photos: str
    route_channel_id_receipts_manual: str
    route_channel_id_study_japanese: str
    request_timeout_videos_seconds: float = 120.0
    request_timeout_videos_batch_seconds: float = 120.0
    request_timeout_receipts_seconds: float = 300.0
    request_timeout_receipts_manual_seconds: float = 120.0
    request_timeout_study_japanese_seconds: float = 90.0
    request_timeout_default_seconds: float = 120.0
    max_attachment_size_bytes: int = 20 * 1024 * 1024
    max_retries: int = 3
    manual_receipt_dedupe_window_seconds: int = 60
    sync_global_commands: bool = False

    @classmethod
    def from_env(cls) -> "BotConfig":
        load_dotenv(dotenv_path=find_dotenv(usecwd=True), override=False)

        required = {
            "DISCORD_BOT_TOKEN": os.getenv("DISCORD_BOT_TOKEN", "").strip(),
            "DISCORD_ALLOWED_GUILD_IDS": os.getenv(
                "DISCORD_ALLOWED_GUILD_IDS", ""
            ).strip(),
            "DISCORD_ALLOWED_USER_IDS": os.getenv(
                "DISCORD_ALLOWED_USER_IDS", ""
            ).strip(),
            "API_BASE_URL": os.getenv("API_BASE_URL", "").strip(),
            "INTERNAL_API_TOKEN": os.getenv("INTERNAL_API_TOKEN", "").strip(),
            "DISCORD_CHANNEL_ID_VIDEOS": os.getenv(
                "DISCORD_CHANNEL_ID_VIDEOS", ""
            ).strip(),
            "DISCORD_CHANNEL_ID_RECEIPTS_PHOTOS": os.getenv(
                "DISCORD_CHANNEL_ID_RECEIPTS_PHOTOS", ""
            ).strip(),
            "DISCORD_CHANNEL_ID_RECEIPTS_MANUAL": os.getenv(
                "DISCORD_CHANNEL_ID_RECEIPTS_MANUAL", ""
            ).strip(),
            "DISCORD_CHANNEL_ID_STUDY_JAPANESE": os.getenv(
                "DISCORD_CHANNEL_ID_STUDY_JAPANESE", ""
            ).strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        timeout_videos_raw = os.getenv("REQUEST_TIMEOUT_VIDEOS_SECONDS", "120").strip()
        timeout_videos_batch_raw = os.getenv(
            "REQUEST_TIMEOUT_VIDEOS_BATCH_SECONDS", "120"
        ).strip()
        timeout_receipts_raw = os.getenv(
            "REQUEST_TIMEOUT_RECEIPTS_SECONDS", "300"
        ).strip()
        timeout_receipts_manual_raw = os.getenv(
            "REQUEST_TIMEOUT_RECEIPTS_MANUAL_SECONDS", "120"
        ).strip()
        timeout_study_japanese_raw = os.getenv(
            "REQUEST_TIMEOUT_STUDY_JAPANESE_SECONDS", "90"
        ).strip()
        timeout_default_raw = os.getenv(
            "REQUEST_TIMEOUT_DEFAULT_SECONDS", "120"
        ).strip()
        max_size_raw = os.getenv(
            "MAX_ATTACHMENT_SIZE_BYTES", str(20 * 1024 * 1024)
        ).strip()
        max_retries_raw = os.getenv("MAX_RETRIES", "3").strip()
        manual_receipt_dedupe_window_raw = os.getenv(
            "MANUAL_RECEIPT_DEDUPE_WINDOW_SECONDS", "60"
        ).strip()
        sync_global_commands_raw = os.getenv("DISCORD_SYNC_GLOBAL_COMMANDS", "")

        allowed_guild_ids = _parse_csv_ids(required["DISCORD_ALLOWED_GUILD_IDS"])
        allowed_user_ids = _parse_csv_ids(required["DISCORD_ALLOWED_USER_IDS"])
        api_base_url = required["API_BASE_URL"].rstrip("/")
        route_channel_id_videos = required["DISCORD_CHANNEL_ID_VIDEOS"]
        route_channel_id_receipts_photos = required[
            "DISCORD_CHANNEL_ID_RECEIPTS_PHOTOS"
        ]
        route_channel_id_receipts_manual = required[
            "DISCORD_CHANNEL_ID_RECEIPTS_MANUAL"
        ]
        route_channel_id_study_japanese = required["DISCORD_CHANNEL_ID_STUDY_JAPANESE"]

        timeout_videos = float(timeout_videos_raw)
        timeout_videos_batch = float(timeout_videos_batch_raw)
        timeout_receipts = float(timeout_receipts_raw)
        timeout_receipts_manual = float(timeout_receipts_manual_raw)
        timeout_study_japanese = float(timeout_study_japanese_raw)
        timeout_default = float(timeout_default_raw)
        max_attachment_size_bytes = int(max_size_raw)
        max_retries = int(max_retries_raw)
        manual_receipt_dedupe_window_seconds = int(manual_receipt_dedupe_window_raw)

        _validate_snowflake_set(allowed_guild_ids, env_name="DISCORD_ALLOWED_GUILD_IDS")
        _validate_snowflake_set(allowed_user_ids, env_name="DISCORD_ALLOWED_USER_IDS")
        _validate_snowflake(
            route_channel_id_videos, env_name="DISCORD_CHANNEL_ID_VIDEOS"
        )
        _validate_snowflake(
            route_channel_id_receipts_photos,
            env_name="DISCORD_CHANNEL_ID_RECEIPTS_PHOTOS",
        )
        _validate_snowflake(
            route_channel_id_receipts_manual,
            env_name="DISCORD_CHANNEL_ID_RECEIPTS_MANUAL",
        )
        _validate_snowflake(
            route_channel_id_study_japanese,
            env_name="DISCORD_CHANNEL_ID_STUDY_JAPANESE",
        )
        _validate_api_base_url(api_base_url)
        _validate_timeout(timeout_videos, env_name="REQUEST_TIMEOUT_VIDEOS_SECONDS")
        _validate_timeout(
            timeout_videos_batch, env_name="REQUEST_TIMEOUT_VIDEOS_BATCH_SECONDS"
        )
        _validate_timeout(timeout_receipts, env_name="REQUEST_TIMEOUT_RECEIPTS_SECONDS")
        _validate_timeout(
            timeout_receipts_manual,
            env_name="REQUEST_TIMEOUT_RECEIPTS_MANUAL_SECONDS",
        )
        _validate_timeout(
            timeout_study_japanese,
            env_name="REQUEST_TIMEOUT_STUDY_JAPANESE_SECONDS",
        )
        _validate_timeout(timeout_default, env_name="REQUEST_TIMEOUT_DEFAULT_SECONDS")
        _validate_retries(max_retries, env_name="MAX_RETRIES")
        _validate_timeout(
            float(manual_receipt_dedupe_window_seconds),
            env_name="MANUAL_RECEIPT_DEDUPE_WINDOW_SECONDS",
        )
        if max_attachment_size_bytes <= 0:
            raise ValueError("MAX_ATTACHMENT_SIZE_BYTES must be greater than 0.")

        return cls(
            discord_bot_token=required["DISCORD_BOT_TOKEN"],
            allowed_guild_ids=allowed_guild_ids,
            allowed_user_ids=allowed_user_ids,
            api_base_url=api_base_url,
            internal_api_token=required["INTERNAL_API_TOKEN"],
            route_channel_id_videos=route_channel_id_videos,
            route_channel_id_receipts_photos=route_channel_id_receipts_photos,
            route_channel_id_receipts_manual=route_channel_id_receipts_manual,
            route_channel_id_study_japanese=route_channel_id_study_japanese,
            request_timeout_videos_seconds=timeout_videos,
            request_timeout_videos_batch_seconds=timeout_videos_batch,
            request_timeout_receipts_seconds=timeout_receipts,
            request_timeout_receipts_manual_seconds=timeout_receipts_manual,
            request_timeout_study_japanese_seconds=timeout_study_japanese,
            request_timeout_default_seconds=timeout_default,
            max_attachment_size_bytes=max_attachment_size_bytes,
            max_retries=max_retries,
            manual_receipt_dedupe_window_seconds=manual_receipt_dedupe_window_seconds,
            sync_global_commands=_parse_bool(sync_global_commands_raw, default=False),
        )

    @property
    def route_channel_ids(self) -> dict[str, str]:
        return {
            "videos": self.route_channel_id_videos,
            "receipts": self.route_channel_id_receipts_photos,
            "receipts-manual": self.route_channel_id_receipts_manual,
            "japanese": self.route_channel_id_study_japanese,
        }

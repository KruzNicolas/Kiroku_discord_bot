from __future__ import annotations

import os
from pathlib import Path

import pytest

from discord_bot.config import BotConfig


def _set_valid_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token-from-env")
    monkeypatch.setenv("DISCORD_ALLOWED_GUILD_IDS", "123456789012345678")
    monkeypatch.setenv("DISCORD_ALLOWED_USER_IDS", "234567890123456789")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "internal-from-env")
    monkeypatch.setenv("DISCORD_CHANNEL_ID_VIDEOS", "123456789012345679")
    monkeypatch.setenv("DISCORD_CHANNEL_ID_RECEIPTS_PHOTOS", "123456789012345680")
    monkeypatch.setenv("DISCORD_CHANNEL_ID_RECEIPTS_MANUAL", "123456789012345681")
    monkeypatch.setenv("DISCORD_CHANNEL_ID_STUDY_JAPANESE", "123456789012345682")


def _clear_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    keys = [
        "DISCORD_BOT_TOKEN",
        "DISCORD_ALLOWED_GUILD_IDS",
        "DISCORD_ALLOWED_USER_IDS",
        "API_BASE_URL",
        "INTERNAL_API_TOKEN",
        "DISCORD_CHANNEL_ID_VIDEOS",
        "DISCORD_CHANNEL_ID_RECEIPTS_PHOTOS",
        "DISCORD_CHANNEL_ID_RECEIPTS_MANUAL",
        "DISCORD_CHANNEL_ID_STUDY_JAPANESE",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_from_env_loads_dotenv_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _clear_required_env(monkeypatch)

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "DISCORD_BOT_TOKEN=token-from-dotenv",
                "DISCORD_ALLOWED_GUILD_IDS=123456789012345678",
                "DISCORD_ALLOWED_USER_IDS=234567890123456789",
                "API_BASE_URL=https://api.example.com",
                "INTERNAL_API_TOKEN=internal-from-dotenv",
                "DISCORD_CHANNEL_ID_VIDEOS=123456789012345679",
                "DISCORD_CHANNEL_ID_RECEIPTS_PHOTOS=123456789012345680",
                "DISCORD_CHANNEL_ID_RECEIPTS_MANUAL=123456789012345681",
                "DISCORD_CHANNEL_ID_STUDY_JAPANESE=123456789012345682",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    config = BotConfig.from_env()

    assert config.discord_bot_token == "token-from-dotenv"
    assert config.internal_api_token == "internal-from-dotenv"
    assert config.route_channel_ids == {
        "videos": "123456789012345679",
        "receipts": "123456789012345680",
        "receipts-manual": "123456789012345681",
        "japanese": "123456789012345682",
    }


def test_from_env_does_not_override_existing_environment(
    monkeypatch: pytest.MonkeyPatch,
):
    _set_valid_required_env(monkeypatch)

    config = BotConfig.from_env()

    assert os.getenv("DISCORD_BOT_TOKEN") == "token-from-env"
    assert config.discord_bot_token == "token-from-env"


def test_from_env_uses_endpoint_timeout_defaults(monkeypatch: pytest.MonkeyPatch):
    _set_valid_required_env(monkeypatch)
    monkeypatch.delenv("REQUEST_TIMEOUT_VIDEOS_SECONDS", raising=False)
    monkeypatch.delenv("REQUEST_TIMEOUT_VIDEOS_BATCH_SECONDS", raising=False)
    monkeypatch.delenv("REQUEST_TIMEOUT_RECEIPTS_SECONDS", raising=False)
    monkeypatch.delenv("REQUEST_TIMEOUT_RECEIPTS_MANUAL_SECONDS", raising=False)
    monkeypatch.delenv("REQUEST_TIMEOUT_STUDY_JAPANESE_SECONDS", raising=False)
    monkeypatch.delenv("REQUEST_TIMEOUT_DEFAULT_SECONDS", raising=False)

    config = BotConfig.from_env()

    assert config.request_timeout_videos_seconds == 120.0
    assert config.request_timeout_videos_batch_seconds == 120.0
    assert config.request_timeout_receipts_seconds == 300.0
    assert config.request_timeout_receipts_manual_seconds == 120.0
    assert config.request_timeout_study_japanese_seconds == 90.0
    assert config.request_timeout_default_seconds == 120.0
    assert config.manual_receipt_dedupe_window_seconds == 60


def test_from_env_overrides_endpoint_timeout_values(monkeypatch: pytest.MonkeyPatch):
    _set_valid_required_env(monkeypatch)
    monkeypatch.setenv("REQUEST_TIMEOUT_VIDEOS_SECONDS", "1")
    monkeypatch.setenv("REQUEST_TIMEOUT_VIDEOS_BATCH_SECONDS", "2")
    monkeypatch.setenv("REQUEST_TIMEOUT_RECEIPTS_SECONDS", "3")
    monkeypatch.setenv("REQUEST_TIMEOUT_RECEIPTS_MANUAL_SECONDS", "4")
    monkeypatch.setenv("REQUEST_TIMEOUT_STUDY_JAPANESE_SECONDS", "5")
    monkeypatch.setenv("REQUEST_TIMEOUT_DEFAULT_SECONDS", "6")
    monkeypatch.setenv("MANUAL_RECEIPT_DEDUPE_WINDOW_SECONDS", "30")

    config = BotConfig.from_env()

    assert config.request_timeout_videos_seconds == 1.0
    assert config.request_timeout_videos_batch_seconds == 2.0
    assert config.request_timeout_receipts_seconds == 3.0
    assert config.request_timeout_receipts_manual_seconds == 4.0
    assert config.request_timeout_study_japanese_seconds == 5.0
    assert config.request_timeout_default_seconds == 6.0
    assert config.manual_receipt_dedupe_window_seconds == 30


def test_from_env_sync_global_commands_defaults_to_false(
    monkeypatch: pytest.MonkeyPatch,
):
    _set_valid_required_env(monkeypatch)
    monkeypatch.delenv("DISCORD_SYNC_GLOBAL_COMMANDS", raising=False)

    config = BotConfig.from_env()

    assert config.sync_global_commands is False


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE"])
def test_from_env_sync_global_commands_parses_truthy_values(
    monkeypatch: pytest.MonkeyPatch, value: str
):
    _set_valid_required_env(monkeypatch)
    monkeypatch.setenv("DISCORD_SYNC_GLOBAL_COMMANDS", value)

    config = BotConfig.from_env()

    assert config.sync_global_commands is True


def test_from_env_fails_with_invalid_discord_ids(monkeypatch: pytest.MonkeyPatch):
    _set_valid_required_env(monkeypatch)
    monkeypatch.setenv("DISCORD_ALLOWED_GUILD_IDS", "g1")

    with pytest.raises(ValueError, match="DISCORD_ALLOWED_GUILD_IDS"):
        BotConfig.from_env()


def test_from_env_fails_with_invalid_timeout_range(monkeypatch: pytest.MonkeyPatch):
    _set_valid_required_env(monkeypatch)
    monkeypatch.setenv("REQUEST_TIMEOUT_VIDEOS_SECONDS", "0")

    with pytest.raises(ValueError, match="REQUEST_TIMEOUT_VIDEOS_SECONDS"):
        BotConfig.from_env()


def test_from_env_fails_with_invalid_retries_range(monkeypatch: pytest.MonkeyPatch):
    _set_valid_required_env(monkeypatch)
    monkeypatch.setenv("MAX_RETRIES", "9")

    with pytest.raises(ValueError, match="MAX_RETRIES"):
        BotConfig.from_env()


def test_from_env_fails_with_invalid_api_base_url(monkeypatch: pytest.MonkeyPatch):
    _set_valid_required_env(monkeypatch)
    monkeypatch.setenv("API_BASE_URL", "notaurl")

    with pytest.raises(ValueError, match="API_BASE_URL"):
        BotConfig.from_env()

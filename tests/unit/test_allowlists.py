from discord_bot.domain.models import NormalizedMessage
from discord_bot.security.allowlists import AllowlistPolicy, validate_message


def _message(**overrides):
    base = {
        "guild_id": "g1",
        "channel_id": "c1",
        "channel_name": "videos",
        "user_id": "u1",
        "message_id": "m1",
        "content": "https://youtu.be/abc",
        "attachments": [],
    }
    base.update(overrides)
    return NormalizedMessage(**base)


def test_allowlists_accept_when_all_ids_match():
    policy = AllowlistPolicy(guild_ids={"g1"}, user_ids={"u1"})
    result = validate_message(policy, _message())
    assert result.allowed is True
    assert result.reason is None


def test_allowlists_reject_non_allowlisted_guild():
    policy = AllowlistPolicy(guild_ids={"g2"}, user_ids={"u1"})
    result = validate_message(policy, _message())
    assert result.allowed is False
    assert "Guild" in (result.reason or "")


def test_allowlists_ignore_channel_allowlisting():
    policy = AllowlistPolicy(guild_ids={"g1"}, user_ids={"u1"})
    result = validate_message(policy, _message())
    assert result.allowed is True
    assert result.reason is None


def test_allowlists_reject_non_allowlisted_user():
    policy = AllowlistPolicy(guild_ids={"g1"}, user_ids={"u2"})
    result = validate_message(policy, _message())
    assert result.allowed is False
    assert "User" in (result.reason or "")

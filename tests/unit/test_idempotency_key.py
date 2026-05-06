from discord_bot.domain.idempotency import build_idempotency_key


def test_idempotency_key_format_is_stable():
    key = build_idempotency_key(guild_id="g1", channel_id="c1", message_id="m1")
    assert key == "discord:g1:c1:m1"


def test_same_message_generates_same_key():
    key1 = build_idempotency_key(guild_id="g1", channel_id="c1", message_id="m1")
    key2 = build_idempotency_key(guild_id="g1", channel_id="c1", message_id="m1")
    assert key1 == key2


def test_different_messages_generate_different_keys():
    key1 = build_idempotency_key(guild_id="g1", channel_id="c1", message_id="m1")
    key2 = build_idempotency_key(guild_id="g1", channel_id="c1", message_id="m2")
    assert key1 != key2

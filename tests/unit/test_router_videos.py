import pytest

from discord_bot.domain.models import NormalizedMessage
from discord_bot.routing.channel_router import RoutingError, route_message


ROUTE_CHANNEL_IDS = {
    "videos": "c-videos",
    "receipts": "c-receipts-photos",
    "receipts-manual": "c-receipts-manual",
    "japanese": "c-study-japanese",
}


def _message(content: str):
    return NormalizedMessage(
        guild_id="g1",
        channel_id="c-videos",
        channel_name="totally-ignored-name",
        user_id="u1",
        message_id="m1",
        content=content,
        attachments=[],
    )


def test_single_url_routes_to_single_endpoint():
    decision = route_message(
        _message("check https://youtu.be/abc123"), ROUTE_CHANNEL_IDS
    )
    assert decision.endpoint == "/api/v1/videos"
    assert decision.payload == {"url": "https://youtu.be/abc123"}


def test_single_url_with_priority_routes_to_single_endpoint_with_manual_priority():
    decision = route_message(
        _message("check https://youtu.be/abc123 priority=HIGH"), ROUTE_CHANNEL_IDS
    )
    assert decision.endpoint == "/api/v1/videos"
    assert decision.payload == {
        "url": "https://youtu.be/abc123",
        "manual_priority": "high",
    }


def test_single_url_with_plain_priority_before_url_is_supported():
    decision = route_message(
        _message("HIGH https://youtu.be/abc123"), ROUTE_CHANNEL_IDS
    )
    assert decision.endpoint == "/api/v1/videos"
    assert decision.payload == {
        "url": "https://youtu.be/abc123",
        "manual_priority": "high",
    }


def test_single_url_with_plain_priority_after_url_is_supported():
    decision = route_message(
        _message("https://youtu.be/abc123 later"), ROUTE_CHANNEL_IDS
    )
    assert decision.endpoint == "/api/v1/videos"
    assert decision.payload == {
        "url": "https://youtu.be/abc123",
        "manual_priority": "later",
    }


def test_multiple_urls_route_to_batch_endpoint():
    decision = route_message(
        _message("https://youtu.be/a1 https://youtube.com/watch?v=b2"),
        ROUTE_CHANNEL_IDS,
    )
    assert decision.endpoint == "/api/v1/videos/batch"
    assert len(decision.payload["items"]) == 2


def test_multiple_urls_support_mixed_manual_priority_tokens():
    decision = route_message(
        _message(
            "priority=high https://youtu.be/a1 "
            "https://youtube.com/watch?v=b2 "
            "https://youtu.be/c3 p=later"
        ),
        ROUTE_CHANNEL_IDS,
    )
    assert decision.endpoint == "/api/v1/videos/batch"
    assert decision.payload == {
        "items": [
            {"url": "https://youtu.be/a1", "manual_priority": "high"},
            {"url": "https://youtube.com/watch?v=b2"},
            {"url": "https://youtu.be/c3", "manual_priority": "later"},
        ]
    }


def test_multiple_urls_support_mixed_plain_and_explicit_priority_tokens():
    decision = route_message(
        _message(
            "high https://youtu.be/a1 "
            "https://youtube.com/watch?v=b2 p=LOW "
            "medium https://youtu.be/c3"
        ),
        ROUTE_CHANNEL_IDS,
    )
    assert decision.endpoint == "/api/v1/videos/batch"
    assert decision.payload == {
        "items": [
            {"url": "https://youtu.be/a1", "manual_priority": "high"},
            {"url": "https://youtube.com/watch?v=b2", "manual_priority": "low"},
            {"url": "https://youtu.be/c3", "manual_priority": "medium"},
        ]
    }


def test_invalid_video_priority_token_raises_routing_error():
    with pytest.raises(RoutingError, match="Invalid video priority token"):
        route_message(
            _message("https://youtu.be/a1 priority=urgent"), ROUTE_CHANNEL_IDS
        )


def test_invalid_plain_video_priority_token_near_url_raises_routing_error():
    with pytest.raises(RoutingError, match="Invalid video priority token"):
        route_message(_message("https://youtu.be/a1 higer"), ROUTE_CHANNEL_IDS)


def test_invalid_videos_message_raises_error():
    with pytest.raises(RoutingError):
        route_message(_message("no links here"), ROUTE_CHANNEL_IDS)


def test_unsupported_channel_id_raises_error():
    message = NormalizedMessage(
        guild_id="g1",
        channel_id="c-unknown",
        channel_name="videos",
        user_id="u1",
        message_id="m1",
        content="https://youtu.be/abc123",
        attachments=[],
    )

    with pytest.raises(RoutingError, match="Unsupported channel id"):
        route_message(message, ROUTE_CHANNEL_IDS)

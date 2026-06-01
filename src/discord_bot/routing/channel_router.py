from __future__ import annotations

from datetime import date
import re

from discord_bot.domain.models import ChannelKind, NormalizedMessage, RouteDecision
from discord_bot.routing.policies import POLICIES

YOUTUBE_PATTERN = re.compile(
    r"(https?://(?:www\.)?(?:youtube\.com/(?:watch\?(?:.*&)?v=[\w-]+|shorts/[\w-]+)|youtu\.be/[\w-]+)(?:[^\s]*))",
    re.IGNORECASE,
)
PRIORITY_TOKEN_PATTERN = re.compile(r"^(?:priority|p)=(?P<value>[a-zA-Z]+)$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_DAY_PATTERN = re.compile(r"^\d{2}-\d{2}$")
ALLOWED_VIDEO_PRIORITIES = {"high", "medium", "low", "later"}
PLAIN_PRIORITY_HINT_PREFIXES = ("hi", "me", "lo", "la")
RECEIPT_MANUAL_ALLOWED_CATEGORIES = (
    "Groceries",
    "Pharmacy",
    "Transport",
    "Utilities",
    "Subscriptions",
    "Debt",
    "Leisure",
    "Others",
)


class RoutingError(ValueError):
    pass


def extract_youtube_urls(text: str) -> list[str]:
    return YOUTUBE_PATTERN.findall(text)


def _parse_priority_token(token: str) -> str | None:
    match = PRIORITY_TOKEN_PATTERN.match(token.strip())
    if not match:
        return None
    value = match.group("value").strip().lower()
    if value not in ALLOWED_VIDEO_PRIORITIES:
        raise RoutingError(
            "Invalid video priority token near URL. Use priority=high|medium|low|later"
        )
    return value


def _parse_plain_priority_token(token: str) -> str | None:
    value = token.strip().lower()
    if value in ALLOWED_VIDEO_PRIORITIES:
        return value
    return None


def _looks_like_priority_token(token: str | None) -> bool:
    if not token:
        return False
    stripped = token.strip().lower()
    if stripped.startswith("priority=") or stripped.startswith("p="):
        return True
    return stripped.isalpha() and any(
        stripped.startswith(prefix) for prefix in PLAIN_PRIORITY_HINT_PREFIXES
    )


def _parse_priority_token_near_url(token: str | None) -> str | None:
    if not token:
        return None
    explicit_priority = _parse_priority_token(token)
    if explicit_priority is not None:
        return explicit_priority
    return _parse_plain_priority_token(token)


def extract_youtube_items(text: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    tokens = text.split()
    if not tokens:
        return items

    for idx, token in enumerate(tokens):
        url_match = YOUTUBE_PATTERN.fullmatch(token.strip())
        if not url_match:
            continue

        url = url_match.group(1)
        parsed_item: dict[str, str] = {"url": url}

        previous = tokens[idx - 1].strip() if idx > 0 else None
        next_token = tokens[idx + 1].strip() if idx + 1 < len(tokens) else None

        previous_priority = _parse_priority_token_near_url(previous)
        next_priority = _parse_priority_token_near_url(next_token)

        if (
            previous
            and _looks_like_priority_token(previous)
            and previous_priority is None
        ):
            raise RoutingError(
                "Invalid video priority token near URL. "
                "Use high|medium|low|later or priority=high|medium|low|later"
            )
        if (
            next_token
            and _looks_like_priority_token(next_token)
            and next_priority is None
        ):
            raise RoutingError(
                "Invalid video priority token near URL. "
                "Use high|medium|low|later or priority=high|medium|low|later"
            )

        if previous_priority and next_priority and previous_priority != next_priority:
            raise RoutingError(
                "Conflicting video priority tokens near URL. "
                "Keep a single priority token per URL."
            )

        resolved_priority = previous_priority or next_priority
        if resolved_priority:
            parsed_item["manual_priority"] = resolved_priority

        items.append(parsed_item)

    return items


def build_receipt_manual_command_content(
    *, date: str, category: str, store: str, items: str
) -> str:
    escaped_store = store.replace('"', "'")
    escaped_items = items.replace('"', "'")
    return (
        f"/receipt_manual date={date} category={category} "
        f'store="{escaped_store}" items="{escaped_items}"'
    )


def parse_receipt_manual_fields(
    *, date: str, category: str, store: str, items: str
) -> dict:
    normalized_date = _normalize_receipt_date(date)
    normalized_category = category.strip()

    if not normalized_category:
        raise RoutingError("Category is required")

    if normalized_category not in RECEIPT_MANUAL_ALLOWED_CATEGORIES:
        allowed_categories = ", ".join(RECEIPT_MANUAL_ALLOWED_CATEGORIES)
        raise RoutingError(f"Category must be one of: {allowed_categories}")

    if not store.strip():
        raise RoutingError("Store is required")

    if not items.strip():
        raise RoutingError("Items are required")

    item_rows = []
    for raw_item in items.split(";"):
        if not raw_item.strip():
            continue

        parts = [part.strip() for part in raw_item.split("|")]
        if len(parts) != 3:
            raise RoutingError(
                "Items must use Product|qty|price;Product2|qty|price format"
            )

        name, quantity, price = parts
        if not name:
            raise RoutingError("Product name is required for each item")

        try:
            parsed_quantity = float(quantity)
            parsed_price = float(price)
        except ValueError as exc:
            raise RoutingError("Item qty and price must be numeric") from exc

        item_rows.append(
            {
                "product": name,
                "quantity": parsed_quantity,
                "price": parsed_price,
            }
        )

    if not item_rows:
        raise RoutingError("At least one item is required")

    return {
        "date": normalized_date,
        "category": normalized_category,
        "store": store.strip(),
        "items": item_rows,
    }


def _normalize_receipt_date(raw_date: str) -> str:
    stripped = raw_date.strip()

    if DATE_PATTERN.match(stripped):
        try:
            date.fromisoformat(stripped)
        except ValueError as exc:
            raise RoutingError("Date must be a valid calendar date") from exc
        return stripped

    if MONTH_DAY_PATTERN.match(stripped):
        current_year = date.today().year
        normalized = f"{current_year}-{stripped}"
        try:
            date.fromisoformat(normalized)
        except ValueError as exc:
            raise RoutingError("Date must be a valid calendar date") from exc
        return normalized

    raise RoutingError("Date must use YYYY-MM-DD or MM-DD format")


def parse_receipt_manual_payload(content: str) -> dict:
    # Minimal deterministic parser:
    # /receipt_manual date=YYYY-MM-DD category=Others store="X" items="A|1|2000;B|2|3000"
    if not content.startswith("/receipt_manual "):
        raise RoutingError("Manual receipt command must start with /receipt_manual")

    parts = content[len("/receipt_manual ") :]
    fields = dict(
        re.findall(r"(date|category|store|items)=\"?([^\"]+?)\"?(?=\s\w+=|$)", parts)
    )
    required = {"date", "category", "store", "items"}
    if not required.issubset(fields):
        missing = required - set(fields)
        raise RoutingError(
            f"Missing manual receipt fields: {', '.join(sorted(missing))}"
        )

    item_rows = []
    for raw_item in fields["items"].split(";"):
        name, quantity, price = [s.strip() for s in raw_item.split("|")]
        item_rows.append(
            {"product": name, "quantity": float(quantity), "price": float(price)}
        )

    return {
        "date": fields["date"],
        "category": fields["category"],
        "store": fields["store"],
        "items": item_rows,
    }


def _resolve_policy_key(channel_id: str, route_channel_ids: dict[str, str]) -> str:
    policy_key_by_channel_id = {
        configured_id: policy_key
        for policy_key, configured_id in route_channel_ids.items()
        if configured_id
    }
    policy_key = policy_key_by_channel_id.get(channel_id)
    if policy_key is None:
        raise RoutingError(f"Unsupported channel id: {channel_id}")
    return policy_key


def route_message(
    message: NormalizedMessage, route_channel_ids: dict[str, str]
) -> RouteDecision:
    policy_key = _resolve_policy_key(message.channel_id, route_channel_ids)
    policy = POLICIES.get(policy_key)
    if policy is None:
        raise RoutingError(f"Unsupported channel policy: {policy_key}")

    if policy.kind == ChannelKind.VIDEOS:
        video_items = extract_youtube_items(message.content)
        if not video_items:
            raise RoutingError("Videos channel requires at least one valid YouTube URL")
        if len(video_items) == 1:
            return RouteDecision(
                endpoint=policy.endpoint_single,
                method="POST",
                content_type="application/json",
                payload=video_items[0],
            )
        return RouteDecision(
            endpoint=policy.endpoint_batch or policy.endpoint_single,
            method="POST",
            content_type="application/json",
            payload={"items": video_items},
        )

    if policy.kind == ChannelKind.RECEIPTS:
        if not message.attachments:
            raise RoutingError("Receipts channel requires an image attachment")
        attachment = message.attachments[0]
        return RouteDecision(
            endpoint=policy.endpoint_single,
            method="POST",
            content_type="multipart/form-data",
            multipart_files={
                "receipt_image": (
                    attachment.filename,
                    attachment.data,
                    attachment.content_type,
                ),
            },
            multipart_data={"store_hint": message.content.strip()}
            if message.content.strip()
            else {},
        )

    if policy.kind == ChannelKind.RECEIPTS_MANUAL:
        return RouteDecision(
            endpoint=policy.endpoint_single,
            method="POST",
            content_type="application/json",
            payload=parse_receipt_manual_payload(message.content),
        )

    if policy.kind == ChannelKind.JAPANESE:
        if not message.attachments:
            raise RoutingError("Japanese channel requires an image attachment")
        attachment = message.attachments[0]
        return RouteDecision(
            endpoint=policy.endpoint_single,
            method="POST",
            content_type="multipart/form-data",
            multipart_files={
                "image": (
                    attachment.filename,
                    attachment.data,
                    attachment.content_type,
                ),
            },
            multipart_data={"note": message.content.strip()}
            if message.content.strip()
            else {},
        )

    raise RoutingError(f"Unsupported channel policy kind: {policy.kind}")


def route_manual_receipt_payload(
    *, channel_id: str, route_channel_ids: dict[str, str], payload: dict
) -> RouteDecision:
    policy_key = _resolve_policy_key(channel_id, route_channel_ids)
    policy = POLICIES.get(policy_key)
    if policy is None:
        raise RoutingError(f"Unsupported channel policy: {policy_key}")

    if policy.kind != ChannelKind.RECEIPTS_MANUAL:
        raise RoutingError(
            "Manual receipt modal must be used in receipts-manual channel"
        )

    return RouteDecision(
        endpoint=policy.endpoint_single,
        method="POST",
        content_type="application/json",
        payload=payload,
    )

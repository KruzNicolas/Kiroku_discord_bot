from __future__ import annotations

from dataclasses import dataclass

from discord_bot.domain.models import NormalizedMessage, ValidationResult


@dataclass(frozen=True)
class AllowlistPolicy:
    guild_ids: set[str]
    user_ids: set[str]


def validate_message(
    policy: AllowlistPolicy, message: NormalizedMessage
) -> ValidationResult:
    if message.guild_id not in policy.guild_ids:
        return ValidationResult(False, "Guild is not allowlisted")

    if message.user_id not in policy.user_ids:
        return ValidationResult(False, "User is not allowlisted")

    return ValidationResult(True)

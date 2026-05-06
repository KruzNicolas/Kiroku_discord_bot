from __future__ import annotations

import random

from discord_bot.domain.models import RetryDecision

RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}


def evaluate_retry(
    *,
    attempt: int,
    max_attempts: int,
    status_code: int | None,
    retry_after: float | None,
    timed_out: bool,
    transient_error: bool = False,
) -> RetryDecision:
    if attempt >= max_attempts:
        return RetryDecision(False)

    if timed_out or transient_error:
        base = 2 ** (attempt - 1)
        return RetryDecision(True, _with_jitter(base))

    if status_code in NON_RETRYABLE_STATUS_CODES:
        return RetryDecision(False)

    if status_code in RETRYABLE_STATUS_CODES:
        if status_code == 429 and retry_after is not None:
            return RetryDecision(True, retry_after)
        base = 2 ** (attempt - 1)
        return RetryDecision(True, _with_jitter(base))

    return RetryDecision(False)


def _with_jitter(base_seconds: float) -> float:
    return base_seconds + random.uniform(0, 0.25 * base_seconds)

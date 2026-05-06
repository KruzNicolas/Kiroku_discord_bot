from __future__ import annotations

from collections import Counter


class MetricsRegistry:
    def __init__(self) -> None:
        self._counter = Counter()

    def inc_request(self, endpoint: str, status: str) -> None:
        self._counter[("bot_requests_total", endpoint, status)] += 1

    def inc_retry(self, endpoint: str, reason: str) -> None:
        self._counter[("bot_retries_total", endpoint, reason)] += 1

    def inc_replay(self, endpoint: str) -> None:
        self._counter[("bot_idempotency_replays_total", endpoint)] += 1

    def inc_failure(self, endpoint: str, error_type: str) -> None:
        self._counter[("bot_failures_total", endpoint, error_type)] += 1

    def snapshot(self) -> dict[tuple[str, ...], int]:
        return dict(self._counter)

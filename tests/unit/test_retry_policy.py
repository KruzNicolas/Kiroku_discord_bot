from discord_bot.transport.retry_policy import evaluate_retry


def test_retry_matrix_retryable_statuses():
    for status in (429, 502, 503, 504):
        decision = evaluate_retry(
            attempt=1,
            max_attempts=3,
            status_code=status,
            retry_after=1.0 if status == 429 else None,
            timed_out=False,
            transient_error=False,
        )
        assert decision.should_retry is True


def test_retry_matrix_non_retryable_statuses():
    for status in (400, 401, 403, 404, 422):
        decision = evaluate_retry(
            attempt=1,
            max_attempts=3,
            status_code=status,
            retry_after=None,
            timed_out=False,
            transient_error=False,
        )
        assert decision.should_retry is False


def test_timeout_retries_until_max_attempts():
    first = evaluate_retry(
        attempt=1,
        max_attempts=3,
        status_code=None,
        retry_after=None,
        timed_out=True,
        transient_error=False,
    )
    third = evaluate_retry(
        attempt=3,
        max_attempts=3,
        status_code=None,
        retry_after=None,
        timed_out=True,
        transient_error=False,
    )
    assert first.should_retry is True
    assert third.should_retry is False


def test_transient_network_error_retries_until_max_attempts():
    first = evaluate_retry(
        attempt=1,
        max_attempts=3,
        status_code=None,
        retry_after=None,
        timed_out=False,
        transient_error=True,
    )
    third = evaluate_retry(
        attempt=3,
        max_attempts=3,
        status_code=None,
        retry_after=None,
        timed_out=False,
        transient_error=True,
    )
    assert first.should_retry is True
    assert third.should_retry is False

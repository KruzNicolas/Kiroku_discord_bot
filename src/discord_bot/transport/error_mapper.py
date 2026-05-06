from __future__ import annotations

from discord_bot.domain.models import ErrorType, ProcessingError


def map_http_error(status_code: int) -> ProcessingError:
    if status_code == 400:
        return ProcessingError(
            400, ErrorType.VALIDATION, "Invalid input. Please verify message format."
        )
    if status_code == 401:
        return ProcessingError(
            401,
            ErrorType.INTEGRATION,
            "Integration authentication failed. Contact administrator.",
        )
    if status_code in {429, 502, 503}:
        return ProcessingError(
            status_code,
            ErrorType.TRANSIENT,
            "Temporary upstream issue. Please retry shortly.",
        )
    return ProcessingError(
        status_code, ErrorType.UNKNOWN, "Processing failed due to an unexpected error."
    )

from __future__ import annotations

from typing import Any


class AgentPostError(Exception):
    """Base class for all stable SDK exceptions."""


class ConfigurationError(AgentPostError):
    """Client configuration is invalid before any HTTP request is attempted."""


class TransportError(AgentPostError):
    """The HTTP exchange did not complete and server acceptance is unknown."""

    def __init__(self, message: str, *, idempotency_key: str | None = None) -> None:
        super().__init__(message)
        self.idempotency_key = idempotency_key


class ResponseError(AgentPostError):
    """An HTTP response or success payload could not be processed."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None,
        code: str,
        request_id: str | None = None,
        details: Any = None,
        idempotency_key: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        self.details = {} if details is None else details
        self.idempotency_key = idempotency_key


class AuthenticationError(ResponseError):
    pass


class AuthorizationError(ResponseError):
    pass


class NotFoundError(ResponseError):
    pass


class ConflictError(ResponseError):
    pass


class ValidationError(ResponseError):
    pass


class RateLimitError(ResponseError):
    pass


ApiError = ResponseError
ForbiddenError = AuthorizationError


class ProtocolError(ResponseError):
    """The server returned a malformed success or error envelope."""


_STATUS_ERRORS: dict[int, type[ResponseError]] = {
    400: ValidationError,
    401: AuthenticationError,
    403: AuthorizationError,
    404: NotFoundError,
    409: ConflictError,
    413: ValidationError,
    422: ValidationError,
    429: RateLimitError,
}


def error_for_status(status_code: int) -> type[ResponseError]:
    return _STATUS_ERRORS.get(status_code, ResponseError)

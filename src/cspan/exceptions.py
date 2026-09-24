"""Exception hierarchy for the cspan package.

::

    CSpanError                     (base — catch this to catch everything)
    ├── ValidationError            invalid input, raised before any request
    └── APIError                   the API returned an error response
        ├── AuthenticationError    missing/invalid API key (HTTP 401/403)
        ├── NotFoundError          resource does not exist (HTTP 404)
        └── RateLimitError         quota/throttle exceeded (HTTP 429)
"""

from __future__ import annotations


class CSpanError(Exception):
    """Base class for every error raised by this package."""


class ValidationError(CSpanError, ValueError):
    """Raised for invalid arguments, before any network call is made.

    Subclasses :class:`ValueError` so existing ``except ValueError`` handlers
    keep working.
    """


class APIError(CSpanError):
    """Raised when the C-SPAN API returns an error response.

    :ivar status_code: HTTP status code, if available.
    :ivar response: the underlying :class:`requests.Response`, if available.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response: object = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class AuthenticationError(APIError):
    """Missing or rejected API key (HTTP 401/403, or no key configured)."""


class NotFoundError(APIError):
    """The requested person or program does not exist (HTTP 404)."""


class RateLimitError(APIError):
    """API rate limit or quota exceeded (HTTP 429).

    :ivar retry_after: seconds to wait before retrying, parsed from the
        ``Retry-After`` header when present.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        status_code: int | None = None,
        response: object = None,
    ) -> None:
        super().__init__(message, status_code=status_code, response=response)
        self.retry_after = retry_after

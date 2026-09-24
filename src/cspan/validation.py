"""Fast-fail argument validation.

Each helper raises :class:`cspan.exceptions.ValidationError` *before* a request
is sent, so obvious mistakes (a malformed date, a sort missing its direction, a
negative page) fail immediately instead of wasting an API round-trip. Validation
is intentionally light: it checks shapes the API documents, not business rules
the server owns.
"""

from __future__ import annotations

import datetime as _dt

from .exceptions import ValidationError
from .formats import SUPPORTED_FORMATS

_SORT_DIRECTIONS = ("asc", "desc")


def require_query(value: str | None, *, name: str = "query") -> str:
    """Ensure a required search term is a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name!r} is required and must be a non-empty string.")
    return value


def require_id(value: object, *, name: str) -> str:
    """Ensure a path id (personId / videoId) is present and non-empty."""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{name!r} is required.")
    return str(value)


def validate_date(value: str | None, *, name: str) -> str | None:
    """Ensure a date is a real calendar date in ``yyyy-mm-dd`` form."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{name!r} must be a string in yyyy-mm-dd format.")
    try:
        _dt.datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValidationError(
            f"{name!r} must be a valid date in yyyy-mm-dd format, got {value!r}."
        ) from None
    return value


def validate_positive_int(value: object, *, name: str) -> object:
    """Ensure an integer-valued parameter is a positive whole number."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError(f"{name!r} must be a positive integer, got {value!r}.")
    return value


def validate_sort(value: str | None, *, name: str = "sort") -> str | None:
    """Ensure each sort term includes a direction (``asc``/``desc``).

    Per the API docs: e.g. ``"date desc"``. Multiple comma-separated terms are
    allowed; each must end in a valid direction.
    """
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name!r} must be a non-empty string like 'date desc'.")
    for term in value.split(","):
        parts = term.split()
        if len(parts) < 2 or parts[-1].lower() not in _SORT_DIRECTIONS:
            raise ValidationError(
                f"{name} term {term.strip()!r} must include a direction "
                f"({' or '.join(_SORT_DIRECTIONS)}), e.g. 'date desc'."
            )
    return value


def validate_format(value: str | None) -> str | None:
    """Ensure an output format is one of the supported names."""
    if value is None:
        return None
    if value not in SUPPORTED_FORMATS:
        raise ValidationError(
            f"Unknown format {value!r}. Choose one of {', '.join(SUPPORTED_FORMATS)}."
        )
    return value

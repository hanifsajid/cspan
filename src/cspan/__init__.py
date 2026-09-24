"""cspan — a Python client for the C-SPAN Archives API.

The API lives at ``https://api.c-spanarchives.org/2.0``. Access is only through
an API key (email ``api@c-spanarchives.org``); the key may be passed directly or
read from the ``CSPAN_API_KEY`` environment variable.

Quick start
-----------
>>> from cspan import CSpanClient
>>> client = CSpanClient()                       # reads CSPAN_API_KEY
>>> client.people(last="Pelosi")                 # JSON (default)
>>> client.bills("budget", format="csv")         # CSV string
>>> for row in client.iter_records(client.mentions, query="ai"):
...     ...                                       # auto-paginates

Results default to JSON; choose another format once on the client
(``output_format=``) or per call (``format=``): ``"json"``, ``"records"``,
``"csv"``, ``"dataframe"``.
"""

from ._version import __version__
from .client import BASE_URL, ENV_API_KEY, CSpanClient
from .exceptions import (
    APIError,
    AuthenticationError,
    CSpanError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from .formats import (
    SAVE_FORMATS,
    SUPPORTED_FORMATS,
    to_csv,
    to_dataframe,
    to_jsonl,
    to_records,
)

__all__ = [
    # client
    "CSpanClient",
    "BASE_URL",
    "ENV_API_KEY",
    # exceptions
    "CSpanError",
    "APIError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "ValidationError",
    # formats
    "SUPPORTED_FORMATS",
    "SAVE_FORMATS",
    "to_records",
    "to_csv",
    "to_jsonl",
    "to_dataframe",
    # meta
    "__version__",
]

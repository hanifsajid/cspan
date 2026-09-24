"""A modern Python client for the C-SPAN Archives REST API.

The API is served from ``https://api.c-spanarchives.org/2.0`` (AWS API Gateway).
Access is **only** through an API key, which you request by emailing
``api@c-spanarchives.org``. The key is sent on every request in the
``x-api-key`` header; without a valid key the API returns ``403 Forbidden``.

Endpoints covered (the full documented API, v2025-06-13):

==============================  =========================================
``bills(query)``                ``GET /bills``
``mentions(query, ...)``        ``GET /mentions``
``people(...)``                 ``GET /people``
``person(person_id)``           ``GET /people/{personId}``
``programs_search(query, ...)`` ``GET /programs/search``
``program(video_id)``           ``GET /programs/{videoId}``
==============================  =========================================
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Iterator
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter

try:  # urllib3 is a hard dependency of requests; import defensively all the same
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover
    from requests.packages.urllib3.util.retry import Retry  # type: ignore

from pathlib import Path

from . import validation as _v
from .exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from .formats import (
    CURSOR_KEYS,
    SAVE_FORMATS,
    SUPPORTED_FORMATS,
    WRITERS,
    convert,
    to_records,
)

BASE_URL = "https://api.c-spanarchives.org/2.0"
ENV_API_KEY = "CSPAN_API_KEY"

#: Keys we look for when auto-detecting the pagination cursor in a response.
_CURSOR_KEYS = CURSOR_KEYS

logger = logging.getLogger("cspan")


def _extract_cursor(data: Any) -> str | None:
    """Best-effort: find a continuation cursor in a response payload."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in _CURSOR_KEYS and isinstance(value, str) and value:
                return value
    return None


def _congress_dates(congress: int) -> tuple[str, str]:
    """Return the ``(start, end)`` ``yyyy-mm-dd`` window for a Congress number.

    Modern Congresses convene on January 3 of an odd year and run two years
    (20th Amendment). E.g. the 117th -> ``("2021-01-03", "2023-01-03")``.
    """
    start_year = 1789 + 2 * (congress - 1)
    return f"{start_year}-01-03", f"{start_year + 2}-01-03"


def _bill_query_variants(title: str | None, number: str | int | None) -> list[str]:
    """Build the spoken-phrase search variants for a bill (title + number forms).

    Different phrasings surface different transcript segments, so we search a
    small union. Each variant is a quoted phrase for exact matching.
    """
    variants: list[str] = []
    if title and title.strip():
        variants.append(f'"{title.strip()}"')
    num = str(number).strip() if number is not None else ""
    if num:
        variants.append(f'"{num}"')
        # Split a leading type prefix (HR, S, S.Res, ...) from the digits and
        # emit the common spoken forms: "HR 5376" and "H.R. 5376".
        m = re.match(r"^\s*([A-Za-z.\s]+?)\s*([0-9]+)\s*$", num)
        if m:
            prefix = re.sub(r"[.\s]", "", m.group(1)).upper()
            digits = m.group(2)
            variants.append(f'"{prefix} {digits}"')
            variants.append(f'"{".".join(prefix)}. {digits}"')
    # De-duplicate, preserve order.
    return list(dict.fromkeys(variants))


class CSpanClient:
    """Client for the C-SPAN Archives API. Requires an API key.

    The key may be passed directly or read from the ``CSPAN_API_KEY`` environment
    variable. Choose an output format once (``output_format``) or per call
    (``format=``): ``"json"`` (default), ``"records"``, ``"csv"``, ``"dataframe"``.

    The client retries transient failures (HTTP 429 and 5xx) with exponential
    backoff, honoring the ``Retry-After`` header.

    Example
    -------
    >>> from cspan import CSpanClient
    >>> client = CSpanClient()                       # reads CSPAN_API_KEY
    >>> client.mentions("artificial intelligence", mindate="2024-01-01")
    >>> client.people(last="Pelosi", format="csv")
    >>> for row in client.iter_records(client.bills, query="budget"):
    ...     ...                                       # auto-follows the cursor
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        output_format: str = "json",
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        session: requests.Session | None = None,
    ) -> None:
        api_key = api_key or os.environ.get(ENV_API_KEY)
        if not api_key or not api_key.strip():
            raise AuthenticationError(
                "An API key is required. Pass it to CSpanClient(...) or set the "
                f"{ENV_API_KEY} environment variable. Email api@c-spanarchives.org "
                "to request a key."
            )
        if output_format not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unknown output_format {output_format!r}. "
                f"Choose one of {', '.join(SUPPORTED_FORMATS)}."
            )

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.output_format = output_format

        provided_session = session is not None
        self.session = session or requests.Session()
        self.session.headers.update(
            {"x-api-key": api_key, "Accept": "application/json"}
        )
        if not provided_session:
            self._install_retries(max_retries, backoff_factor)

    def _install_retries(self, max_retries: int, backoff_factor: float) -> None:
        retry = Retry(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            status=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    # -- core request ------------------------------------------------------

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        format: str | None = None,
    ) -> Any:
        """GET ``path`` and return the response in the chosen format.

        Drops ``None`` params, maps error statuses to typed exceptions, and
        converts the JSON body to ``format`` (falling back to ``output_format``).
        """
        fmt = _v.validate_format(format) or self.output_format
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        url = f"{self.base_url}{path}"

        logger.debug("GET %s params=%s", url, clean)
        try:
            resp = self.session.get(url, params=clean, timeout=self.timeout)
        except requests.RequestException as exc:  # pragma: no cover - network
            raise APIError(f"Request to {url} failed: {exc}") from exc

        self._raise_for_status(resp, url)

        try:
            data = resp.json()
        except ValueError:
            return resp.text
        return convert(data, fmt)

    @staticmethod
    def _raise_for_status(resp: requests.Response, url: str) -> None:
        code = resp.status_code
        if code < 400:
            return
        body = resp.text[:200]
        if code in (401, 403):
            raise AuthenticationError(
                f"Access denied (HTTP {code}). Check that your API key is valid "
                "and active.",
                status_code=code,
                response=resp,
            )
        if code == 404:
            raise NotFoundError(
                f"Not found (HTTP 404) for {url}.", status_code=404, response=resp
            )
        if code == 429:
            retry_after = resp.headers.get("Retry-After")
            raise RateLimitError(
                "Rate limit or quota exceeded (HTTP 429).",
                retry_after=float(retry_after) if retry_after else None,
                status_code=429,
                response=resp,
            )
        raise APIError(
            f"HTTP {code} from {url}: {body}", status_code=code, response=resp
        )

    # -- endpoints ---------------------------------------------------------

    def bills(
        self, query: str, *, cursor: str | None = None, format: str | None = None
    ) -> Any:
        """``GET /bills`` — search Congressional bill information.

        :param query: word or phrase to search for (required).
        :param cursor: continuation cursor from a previous call, for pagination.
        :param format: output format for this call (overrides ``output_format``).
        """
        _v.require_query(query)
        return self._get("/bills", {"query": query, "cursor": cursor}, format=format)

    def mentions(
        self,
        query: str,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        personid: int | str | None = None,
        date: str | None = None,
        maxdate: str | None = None,
        mindate: str | None = None,
        page: int | None = None,
        videotype: str | None = None,
        format: str | None = None,
    ) -> Any:
        """``GET /mentions`` — search C-SPAN programming for spoken words/phrases.

        :param query: word or phrase to search for (required).
        :param limit: number of results to return (default 20).
        :param cursor: continuation cursor for pagination.
        :param personid: only results spoken by this person ID (see :meth:`people`).
        :param date: only results spoken on this date (``yyyy-mm-dd``).
        :param maxdate: only results on or before this date (``yyyy-mm-dd``).
        :param mindate: only results on or after this date (``yyyy-mm-dd``).
        :param page: page number of results (default 1).
        :param videotype: only results of this video type (e.g. ``Speech``, ``Debate``).
        :param format: output format for this call (overrides ``output_format``).
        """
        _v.require_query(query)
        _v.validate_positive_int(limit, name="limit")
        _v.validate_positive_int(page, name="page")
        _v.validate_date(date, name="date")
        _v.validate_date(maxdate, name="maxdate")
        _v.validate_date(mindate, name="mindate")
        return self._get(
            "/mentions",
            {
                "query": query,
                "limit": limit,
                "cursor": cursor,
                "personid": personid,
                "date": date,
                "maxdate": maxdate,
                "mindate": mindate,
                "page": page,
                "videotype": videotype,
            },
            format=format,
        )

    def people(
        self,
        query: str | None = None,
        *,
        first: str | None = None,
        last: str | None = None,
        cursor: str | None = None,
        format: str | None = None,
    ) -> Any:
        """``GET /people`` — search the C-SPAN database for people.

        :param query: name or title to match (optional).
        :param first: first name to match (optional).
        :param last: last name to match (optional).
        :param cursor: continuation cursor for pagination.
        :param format: output format for this call (overrides ``output_format``).
        """
        return self._get(
            "/people",
            {"query": query, "first": first, "last": last, "cursor": cursor},
            format=format,
        )

    def person(self, person_id: int | str, *, format: str | None = None) -> Any:
        """``GET /people/{personId}`` — fetch one person by internal or public ID."""
        pid = _v.require_id(person_id, name="person_id")
        return self._get(f"/people/{quote(pid, safe='')}", format=format)

    def programs_search(
        self,
        query: str,
        *,
        cursor: str | None = None,
        sort: str | None = None,
        format: str | None = None,
    ) -> Any:
        """``GET /programs/search`` — program search interface.

        :param query: Lucene query string. Valid fields include ``abstract``,
            ``category``, ``date``, ``format``, ``isbn``, ``location``, ``person``,
            ``personid``, ``series``, ``sponsor``, ``subject``, ``tag``, ``text``.
            (Note: that ``format`` is a *query field* inside ``query``; the
            ``format`` keyword below selects this call's **output** format.)
        :param cursor: continuation cursor for pagination.
        :param sort: ``popular`` or ``date`` with a direction, e.g. ``"date desc"``.
        :param format: output format for this call (overrides ``output_format``).
        """
        _v.require_query(query)
        _v.validate_sort(sort)
        return self._get(
            "/programs/search",
            {"query": query, "cursor": cursor, "sort": sort},
            format=format,
        )

    def program(self, video_id: int | str, *, format: str | None = None) -> Any:
        """``GET /programs/{videoId}`` — fetch one program by internal or public ID."""
        vid = _v.require_id(video_id, name="video_id")
        return self._get(f"/programs/{quote(vid, safe='')}", format=format)

    # -- pagination --------------------------------------------------------

    def iter_records(
        self,
        endpoint,
        *,
        max_items: int | None = None,
        **kwargs,
    ) -> Iterator[dict]:
        """Yield result rows across pages, auto-following the ``cursor``.

        ``endpoint`` is one of the cursor-based search methods (:meth:`bills`,
        :meth:`mentions`, :meth:`people`, :meth:`programs_search`). The output
        format is forced to JSON internally so the cursor can be read; each row
        is yielded as a ``dict``.

        :param max_items: stop after yielding this many rows (default: all).

        Example
        -------
        >>> for row in client.iter_records(client.bills, query="budget", max_items=200):
        ...     ...
        """
        cursor = kwargs.pop("cursor", None)
        kwargs.pop("format", None)  # pagination always reads raw JSON
        fetched = 0
        seen_cursors: set[str] = set()
        while True:
            page = endpoint(cursor=cursor, format="json", **kwargs)
            rows = to_records(page)
            for row in rows:
                yield row
                fetched += 1
                if max_items is not None and fetched >= max_items:
                    return
            next_cursor = _extract_cursor(page)
            # Stop on: no rows, no cursor, or a cursor we've already followed
            # (the API returns a cursor on every page, so a repeat means the end).
            if not rows or not next_cursor or next_cursor in seen_cursors:
                return
            seen_cursors.add(next_cursor)
            cursor = next_cursor

    # -- high-level queries ------------------------------------------------

    def _is_senator(self, personid: Any, _cache: dict[Any, str]) -> tuple[bool, dict]:
        """Look up a speaker once and decide whether they are a senator.

        Returns ``(is_senator, person_row)``. Results are memoized in ``_cache``
        (personid -> title) so each speaker costs at most one extra request.
        """
        if personid in _cache:
            title = _cache[personid]
            row: dict = {}
        else:
            try:
                rows = to_records(self.person(personid, format="json"))
            except (NotFoundError, APIError):
                rows = []
            row = rows[0] if rows else {}
            title = str(row.get("title", ""))
            _cache[personid] = title
        return ("senator" in title.lower(), row)

    def speeches_on_bill(
        self,
        *,
        title: str | None = None,
        number: str | int | None = None,
        congress: int | None = None,
        videotypes: tuple[str, ...] = ("Speech", "Debate"),
        mindate: str | None = None,
        maxdate: str | None = None,
        max_items: int | None = None,
    ) -> dict[str, Any]:
        """Find every senator who spoke about a bill, grouped with their speeches.

        Because the API has **no structured bill-to-speech link**, this searches
        the spoken-word transcript (:meth:`mentions`) for the bill's title and
        number, keeps only floor ``videotypes`` (default ``Speech``/``Debate``),
        then keeps speakers whose person ``title`` contains ``"Senator"``.

        Provide a ``title`` and/or ``number`` (more variants searched = better
        recall) and a ``congress`` (used to scope the date window unless
        ``mindate``/``maxdate`` are given explicitly).

        ``max_items`` caps the rows fetched for *each* title/number variant and
        video type combination (a quota guard), not the total.

        :returns: ``{"bill": {...}, "videotypes": [...], "senators": [
            {"personid", "name", "title", "speeches": [<mention rows>]}, ...]}``,
            senators sorted by speech count (descending), then name.

        Example
        -------
        >>> client.speeches_on_bill(
        ...     title="Inflation Reduction Act", number="H.R. 5376", congress=117
        ... )
        """
        if not (title or number):
            raise ValidationError("Provide a bill 'title' and/or 'number' to search.")
        if congress is not None:
            _v.validate_positive_int(congress, name="congress")
        _v.validate_date(mindate, name="mindate")
        _v.validate_date(maxdate, name="maxdate")
        if congress is not None and mindate is None and maxdate is None:
            mindate, maxdate = _congress_dates(congress)

        variants = _bill_query_variants(title, number)

        # Collect matching floor segments, de-duplicated across the query/type
        # cross-product by the mention id.
        segments: dict[Any, dict] = {}
        for query in variants:
            for vtype in videotypes:
                for row in self.iter_records(
                    self.mentions,
                    query=query,
                    videotype=vtype,
                    mindate=mindate,
                    maxdate=maxdate,
                    max_items=max_items,
                ):
                    segments.setdefault(row.get("id"), row)

        # Group senators -> speeches (one person lookup per unique speaker).
        title_cache: dict[Any, str] = {}
        senators: dict[Any, dict] = {}
        for seg in segments.values():
            pid = seg.get("personid")
            if not pid:
                # Some transcript segments carry no speaker id; nothing to look up.
                continue
            is_senator, person = self._is_senator(pid, title_cache)
            if not is_senator:
                continue
            entry = senators.setdefault(
                pid,
                {
                    "personid": pid,
                    "name": person.get("name") or seg.get("person", ""),
                    "title": title_cache.get(pid, ""),
                    "speeches": [],
                },
            )
            entry["speeches"].append(seg)

        ordered = sorted(
            senators.values(), key=lambda s: (-len(s["speeches"]), str(s["name"]))
        )
        return {
            "bill": {"title": title, "number": number, "congress": congress},
            "videotypes": list(videotypes),
            "senators": ordered,
        }

    # -- saving to disk ----------------------------------------------------

    def save(
        self,
        endpoint,
        dest,
        *,
        format: str = "csv",
        paginate: bool = True,
        max_items: int | None = None,
        filename: str | None = None,
        **params,
    ) -> str:
        """Fetch from ``endpoint`` and write the results to a file. Returns the path.

        :param endpoint: a search method (:meth:`bills`, :meth:`mentions`,
            :meth:`people`, :meth:`programs_search`) or its name as a string.
        :param dest: a file path, or a directory (an existing directory, or a
            path ending in a separator) in which a file named
            ``<endpoint>.<ext>`` is created.
        :param format: ``csv``, ``json``, ``jsonl``, ``xlsx``, or ``parquet``.
            ``xlsx``/``parquet`` require pandas (and openpyxl / pyarrow).
        :param paginate: if ``True`` (default), follow the cursor and write
            **all** result rows; if ``False``, write only the first page.
        :param max_items: cap the number of rows when ``paginate`` is ``True``.
        :param filename: override the auto-generated filename (used with a
            directory ``dest``).
        :param params: query parameters forwarded to the endpoint (e.g.
            ``query=...``, ``sort=...``).

        Example
        -------
        >>> client.save(client.bills, "out/", query="budget", format="csv")
        'out/bills.csv'
        """
        fmt = format.lower()
        if fmt not in WRITERS:
            raise ValidationError(
                f"Unknown save format {format!r}. Choose one of "
                f"{', '.join(SAVE_FORMATS)}."
            )
        if isinstance(endpoint, str):
            endpoint = getattr(self, endpoint)
        name = getattr(endpoint, "__name__", "cspan")

        if paginate:
            payload: Any = list(
                self.iter_records(endpoint, max_items=max_items, **params)
            )
        else:
            payload = endpoint(format="json", **params)

        path = Path(dest)
        # Treat dest as a directory if it clearly is one: an existing directory,
        # a trailing separator, an explicit filename, or no file extension.
        treat_as_dir = (
            filename is not None
            or path.is_dir()
            or str(dest).endswith(("/", "\\"))
            or path.suffix == ""
        )
        if treat_as_dir:
            path = path / (filename or f"{name}.{fmt}")
        path.parent.mkdir(parents=True, exist_ok=True)

        WRITERS[fmt](payload, path)
        return str(path)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self.session.close()

    def __enter__(self) -> CSpanClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<CSpanClient base_url={self.base_url!r} format={self.output_format!r}>"

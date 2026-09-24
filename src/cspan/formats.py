"""Client-side output formatting.

The C-SPAN API only returns JSON. These helpers convert a decoded JSON response
into other shapes the caller might want:

* ``"json"``      -> the decoded JSON, unchanged (a dict or list).
* ``"records"``   -> a flat ``list[dict]`` of result rows.
* ``"csv"``       -> a CSV string.
* ``"dataframe"`` -> a :class:`pandas.DataFrame` (requires ``pandas``).

Because the exact response shape varies by endpoint, :func:`to_records` uses a
small heuristic to locate the list of result rows.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

#: Output formats accepted by the client and :func:`convert`.
SUPPORTED_FORMATS = ("json", "records", "csv", "dataframe")

#: Response keys that carry pagination metadata rather than result data. When a
#: search matches nothing the API omits the result key entirely and returns only
#: these, e.g. ``{"cursor": "VQAAeXUBKgA"}``.
CURSOR_KEYS = ("cursor", "nextcursor", "next_cursor", "continuation")


def to_records(data: Any) -> list[dict]:
    """Best-effort extraction of result rows as a ``list[dict]``.

    * A list is treated as the rows directly.
    * A dict is searched for its first list-of-dicts value (the result set).
    * A dict holding nothing but pagination metadata is an empty result set.
    * Otherwise the dict itself is returned as a single row (e.g. the flat
      payload of ``/programs/{videoId}``).
    """
    if isinstance(data, list):
        return [r if isinstance(r, dict) else {"value": r} for r in data]
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list) and (not value or isinstance(value[0], dict)):
                return value
        if data and all(key.lower() in CURSOR_KEYS for key in data):
            return []
        return [data]
    return [{"value": data}]


def _cell(value: Any) -> Any:
    """Render a value for a CSV cell; nested structures become JSON text."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def to_csv(data: Any) -> str:
    """Convert a JSON response to a CSV string (header + one row per record)."""
    records = to_records(data)
    if not records:
        return ""
    fieldnames: list[str] = []
    for row in records:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in records:
        writer.writerow({k: _cell(row.get(k)) for k in fieldnames})
    return buf.getvalue()


def to_jsonl(data: Any) -> str:
    """Convert a JSON response to JSON Lines (one JSON record per line)."""
    records = to_records(data)
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)


def to_dataframe(data: Any):
    """Convert a JSON response to a pandas ``DataFrame`` (requires ``pandas``)."""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "The 'dataframe' format requires pandas. Install it with "
            "`pip install pandas` (or `pip install cspan[pandas]`)."
        ) from exc
    return pd.json_normalize(to_records(data))


def convert(data: Any, fmt: str) -> Any:
    """Convert ``data`` to ``fmt``. Raises :class:`ValueError` for an unknown format."""
    if fmt == "json":
        return data
    if fmt == "records":
        return to_records(data)
    if fmt == "csv":
        return to_csv(data)
    if fmt == "dataframe":
        return to_dataframe(data)
    raise ValueError(
        f"Unknown format {fmt!r}. Choose one of {', '.join(SUPPORTED_FORMATS)}."
    )


def _write_text(text: str, path) -> None:
    path.write_text(text, encoding="utf-8")


#: Maps a save format to a writer ``(payload, path) -> None``. This is the single
#: source of truth for which file formats :meth:`cspan.CSpanClient.save` accepts;
#: ``xlsx``/``parquet`` require pandas (and an engine: openpyxl / pyarrow).
WRITERS = {
    "csv": lambda payload, path: _write_text(to_csv(payload), path),
    "json": lambda payload, path: _write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), path
    ),
    "jsonl": lambda payload, path: _write_text(to_jsonl(payload), path),
    "xlsx": lambda payload, path: to_dataframe(payload).to_excel(path, index=False),
    "parquet": lambda payload, path: to_dataframe(payload).to_parquet(
        path, index=False
    ),
}

#: File formats accepted by :meth:`cspan.CSpanClient.save`, derived from :data:`WRITERS`.
SAVE_FORMATS = tuple(WRITERS)

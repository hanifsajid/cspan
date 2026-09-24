"""Tests for the format converters."""

from __future__ import annotations

import csv
import io

from cspan import to_csv, to_records


def test_records_from_list():
    data = [{"id": 1}, {"id": 2}]
    assert to_records(data) == data


def test_records_from_envelope():
    data = {"count": 1, "results": [{"id": 1, "t": "x"}]}
    assert to_records(data) == [{"id": 1, "t": "x"}]


def test_records_from_single_dict():
    data = {"id": 9, "name": "Obama"}
    assert to_records(data) == [data]


def test_records_from_scalar_list():
    assert to_records([1, 2]) == [{"value": 1}, {"value": 2}]


def test_records_from_cursor_only_envelope_is_empty():
    # A search that matches nothing returns just the cursor, with no result key.
    # That is an empty result set, not a one-row record.
    assert to_records({"cursor": "VQAAeXUBKgA"}) == []


def test_csv_from_cursor_only_envelope_is_empty():
    assert to_csv({"cursor": "VQAAeXUBKgA"}) == ""


def test_csv_unions_keys_and_serializes_nested():
    data = [{"id": 1, "tags": ["a", "b"]}, {"id": 2, "name": "x"}]
    out = to_csv(data)
    rows = list(csv.DictReader(io.StringIO(out)))
    assert rows[0]["id"] == "1"
    assert rows[0]["tags"] == '["a", "b"]'      # nested -> JSON text
    assert rows[1]["name"] == "x"
    assert rows[0]["name"] == ""                 # missing key -> empty


def test_csv_empty():
    assert to_csv([]) == ""

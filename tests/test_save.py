"""Tests for CSpanClient.save (download to disk)."""

from __future__ import annotations

import csv
import io
import json

import pytest

from conftest import FakeResponse, FakeSession
from cspan import CSpanClient, ValidationError


def _client_with(*pages) -> CSpanClient:
    session = FakeSession().queue(*pages)
    return CSpanClient("k", session=session)


PAGE = {"cursor": "C", "bills": [{"id": 1, "t": "a"}, {"id": 2, "t": "b"}]}
PAGE2 = {"bills": [{"id": 3, "t": "c"}]}  # no cursor -> end


def test_save_csv_to_file(tmp_path):
    c = _client_with(FakeResponse(payload=PAGE), FakeResponse(payload=PAGE2))
    out = c.save(c.bills, tmp_path / "data.csv", query="x", format="csv")
    assert out.endswith("data.csv")
    rows = list(csv.DictReader(io.StringIO((tmp_path / "data.csv").read_text())))
    assert [r["id"] for r in rows] == ["1", "2", "3"]   # paginated all pages


def test_save_to_directory_auto_names(tmp_path):
    c = _client_with(FakeResponse(payload=PAGE2))   # single page, no cursor
    out = c.save(c.bills, tmp_path, query="x", format="csv")
    assert out.endswith("bills.csv")          # auto-named after the endpoint
    assert (tmp_path / "bills.csv").exists()


def test_save_to_nonexistent_directory_without_suffix(tmp_path):
    # A path with no file extension is treated as a directory, even if it does
    # not exist yet (it is created). Regression: previously clobbered as a file.
    c = _client_with(FakeResponse(payload=PAGE2))
    target = tmp_path / "newdir"          # no suffix, does not exist
    out = c.save(c.bills, target, query="x", format="csv")
    assert out.endswith("bills.csv")
    assert (target / "bills.csv").exists()


def test_save_path_with_suffix_is_a_file(tmp_path):
    c = _client_with(FakeResponse(payload=PAGE2))
    out = c.save(c.bills, tmp_path / "report.csv", query="x")
    assert out.endswith("report.csv")     # suffix -> file, not a directory


def test_save_endpoint_by_name(tmp_path):
    c = _client_with(FakeResponse(payload=PAGE2))
    out = c.save("bills", tmp_path, query="x", format="jsonl")
    assert out.endswith("bills.jsonl")


def test_save_json_single_page(tmp_path):
    c = _client_with(FakeResponse(payload=PAGE))
    c.save(c.bills, tmp_path / "raw.json", query="x", format="json", paginate=False)
    data = json.loads((tmp_path / "raw.json").read_text())
    assert data == PAGE          # raw response preserved


def test_save_jsonl(tmp_path):
    c = _client_with(FakeResponse(payload=PAGE2))
    c.save(c.bills, tmp_path / "x.jsonl", query="x", format="jsonl")
    lines = (tmp_path / "x.jsonl").read_text().splitlines()
    assert json.loads(lines[0]) == {"id": 3, "t": "c"}


def test_save_max_items(tmp_path):
    c = _client_with(FakeResponse(payload=PAGE), FakeResponse(payload=PAGE2))
    c.save(c.bills, tmp_path / "d.csv", query="x", max_items=1)
    rows = list(csv.DictReader(io.StringIO((tmp_path / "d.csv").read_text())))
    assert len(rows) == 1


def test_save_unknown_format_rejected(client, tmp_path):
    with pytest.raises(ValidationError):
        client.save(client.bills, tmp_path / "x.xml", query="x", format="xml")


def test_save_creates_missing_dirs(tmp_path):
    c = _client_with(FakeResponse(payload=PAGE2))
    out = c.save(c.bills, tmp_path / "nested" / "deep" / "x.csv", query="x")
    assert (tmp_path / "nested" / "deep" / "x.csv").exists()
    assert out.endswith("x.csv")

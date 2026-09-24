"""Tests for fast-fail argument validation."""

from __future__ import annotations

import pytest

from cspan import ValidationError


def test_empty_query_rejected(client):
    for bad in ("", "   "):
        with pytest.raises(ValidationError):
            client.bills(bad)


@pytest.mark.parametrize("bad", ["2024-13-01", "2024/01/01", "not-a-date", "20240101"])
def test_bad_date_rejected(client, bad):
    with pytest.raises(ValidationError):
        client.mentions("ai", date=bad)


def test_valid_date_accepted(client, session):
    client.mentions("ai", mindate="2024-02-29")  # real leap day
    assert session.last[1]["mindate"] == "2024-02-29"


@pytest.mark.parametrize("bad", [0, -1, 1.5, True])
def test_non_positive_int_rejected(client, bad):
    with pytest.raises(ValidationError):
        client.mentions("ai", limit=bad)


@pytest.mark.parametrize("bad", ["date", "popular up", "", "date,"])
def test_sort_without_direction_rejected(client, bad):
    with pytest.raises(ValidationError):
        client.programs_search("text:x", sort=bad)


@pytest.mark.parametrize("good", ["date desc", "popular asc", "date desc,popular asc"])
def test_sort_with_direction_accepted(client, session, good):
    client.programs_search("text:x", sort=good)
    assert session.last[1]["sort"] == good


def test_missing_path_id_rejected(client):
    with pytest.raises(ValidationError):
        client.person("")
    with pytest.raises(ValidationError):
        client.program(None)


def test_unknown_format_rejected(client):
    with pytest.raises(ValidationError):
        client.bills("x", format="xml")

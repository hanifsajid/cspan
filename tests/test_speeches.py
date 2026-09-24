"""Tests for CSpanClient.speeches_on_bill and its helpers (all offline)."""

from __future__ import annotations

import pytest

from conftest import FakeResponse, FakeSession
from cspan import CSpanClient, ValidationError
from cspan.client import _bill_query_variants, _congress_dates


def _client_with(*pages) -> CSpanClient:
    return CSpanClient("k", session=FakeSession().queue(*pages))


# -- pure helpers ----------------------------------------------------------


def test_congress_dates_117th():
    assert _congress_dates(117) == ("2021-01-03", "2023-01-03")


def test_bill_query_variants_dedup_and_forms():
    v = _bill_query_variants("Inflation Reduction Act", "H.R. 5376")
    assert '"Inflation Reduction Act"' in v
    assert '"HR 5376"' in v          # compact spoken form
    assert '"H.R. 5376"' in v        # dotted spoken form
    assert len(v) == len(set(v))     # no duplicates


def test_bill_query_variants_title_only():
    assert _bill_query_variants("Some Act", None) == ['"Some Act"']


# -- speeches_on_bill ------------------------------------------------------


def test_requires_title_or_number():
    with pytest.raises(ValidationError):
        _client_with().speeches_on_bill(congress=117)


def test_groups_senators_and_filters_non_senators():
    # One mentions page (no cursor -> end), then a person lookup per speaker.
    mentions_page = FakeResponse(payload={"mentions": [
        {"id": "1", "personid": 100, "person": "Jane Doe", "text": "...",
         "programTitle": "Senate Debate", "videoTypeId": 18},
        {"id": "2", "personid": 200, "person": "TV Host", "text": "...",
         "programTitle": "Washington Journal", "videoTypeId": 18},
        {"id": "3", "personid": 100, "person": "Jane Doe", "text": "more",
         "programTitle": "Senate Debate", "videoTypeId": 18},
    ]})
    senator = FakeResponse(payload={"people": [
        {"id": 100, "name": "Jane Doe", "title": "U.S. Senator"}]})
    host = FakeResponse(payload={"people": [
        {"id": 200, "name": "TV Host", "title": "Host, Correspondent"}]})

    c = _client_with(mentions_page, senator, host)
    res = c.speeches_on_bill(title="Test Act", congress=117, videotypes=("Debate",))

    assert [s["name"] for s in res["senators"]] == ["Jane Doe"]   # host dropped
    jane = res["senators"][0]
    assert jane["title"] == "U.S. Senator"
    assert len(jane["speeches"]) == 2          # both of Jane's segments grouped


def test_empty_mentions_page_yields_no_senators():
    # A query that matches nothing returns only a cursor. That must not be
    # mistaken for a result row (which used to crash on the missing personid).
    c = _client_with(FakeResponse(payload={"cursor": "VQAAeXUBKgA"}))
    res = c.speeches_on_bill(title="Test Act", congress=117, videotypes=("Debate",))
    assert res["senators"] == []


def test_segments_without_personid_are_skipped():
    mentions_page = FakeResponse(payload={"mentions": [
        {"id": "1", "person": "Unattributed speaker", "videoTypeId": 18},
        {"id": "2", "personid": 100, "person": "Jane", "videoTypeId": 18},
    ]})
    senator = FakeResponse(payload={"people": [{"id": 100, "title": "U.S. Senator"}]})

    c = _client_with(mentions_page, senator)
    res = c.speeches_on_bill(title="Test Act", congress=117, videotypes=("Debate",))

    assert [len(s["speeches"]) for s in res["senators"]] == [1]


def test_speaker_lookup_is_cached_per_personid():
    # Two segments by the same speaker must cost exactly one /people/{id} call.
    mentions_page = FakeResponse(payload={"mentions": [
        {"id": "1", "personid": 100, "person": "Jane", "videoTypeId": 18},
        {"id": "2", "personid": 100, "person": "Jane", "videoTypeId": 18},
    ]})
    senator = FakeResponse(payload={"people": [{"id": 100, "title": "U.S. Senator"}]})
    session = FakeSession().queue(mentions_page, senator)
    c = CSpanClient("k", session=session)

    c.speeches_on_bill(title="Test Act", congress=117, videotypes=("Debate",))

    person_calls = [u for u, _ in session.calls if "/people/100" in u]
    assert len(person_calls) == 1              # not two

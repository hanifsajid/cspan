"""Tests for request building, auth, exceptions, formats, and pagination."""

from __future__ import annotations

import pytest

from conftest import FakeResponse, FakeSession
from cspan import (
    APIError,
    AuthenticationError,
    CSpanClient,
    NotFoundError,
    RateLimitError,
)

# -- construction & auth ---------------------------------------------------

def test_requires_api_key(monkeypatch):
    monkeypatch.delenv("CSPAN_API_KEY", raising=False)
    with pytest.raises(AuthenticationError):
        CSpanClient()


def test_api_key_from_env(monkeypatch):
    monkeypatch.setenv("CSPAN_API_KEY", "ENV-KEY")
    c = CSpanClient(session=FakeSession())
    assert c.session.headers["x-api-key"] == "ENV-KEY"


def test_explicit_key_sets_header(client, session):
    assert session.headers["x-api-key"] == "TEST-KEY"
    assert session.headers["Accept"] == "application/json"


def test_bad_output_format_rejected():
    with pytest.raises(ValueError):
        CSpanClient("k", output_format="xml", session=FakeSession())


# -- request building (exact wire compliance) ------------------------------

def test_bills_params(client, session):
    client.bills("guns", cursor="C1")
    url, params = session.last
    assert url.endswith("/bills")
    assert params == {"query": "guns", "cursor": "C1"}


def test_mentions_all_params(client, session):
    client.mentions(
        "ai", limit=50, cursor="C2", personid=123, date="2024-01-01",
        maxdate="2024-12-31", mindate="2024-01-01", page=2, videotype="Speech",
    )
    _, params = session.last
    assert params == {
        "query": "ai", "limit": 50, "cursor": "C2", "personid": 123,
        "date": "2024-01-01", "maxdate": "2024-12-31", "mindate": "2024-01-01",
        "page": 2, "videotype": "Speech",
    }


def test_none_params_dropped(client, session):
    client.people(last="Smith")
    _, params = session.last
    assert params == {"last": "Smith"}


def test_path_ids_encoded(client, session):
    client.person("a b/c")
    url, params = session.last
    assert url.endswith("/people/a%20b%2Fc")
    assert params == {}
    client.program("550613-1")
    assert session.last[0].endswith("/programs/550613-1")


def test_format_does_not_leak_to_wire(client, session):
    client.bills("x", format="csv")
    _, params = session.last
    assert "format" not in params


# -- output formats --------------------------------------------------------

ENVELOPE = {"count": 2, "results": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]}


def test_format_json_default(session):
    c = CSpanClient("k", session=session.queue(FakeResponse(payload=ENVELOPE)))
    assert c.bills("x") == ENVELOPE


def test_format_records(session):
    c = CSpanClient("k", session=session.queue(FakeResponse(payload=ENVELOPE)))
    assert c.bills("x", format="records") == ENVELOPE["results"]


def test_format_csv(session):
    c = CSpanClient("k", session=session.queue(FakeResponse(payload=ENVELOPE)))
    out = c.bills("x", format="csv")
    assert out.splitlines()[0] == "id,name"
    assert "1,A" in out


def test_client_level_default_format(session):
    c = CSpanClient("k", output_format="records",
                    session=session.queue(FakeResponse(payload=ENVELOPE)))
    assert c.bills("x") == ENVELOPE["results"]


# -- error mapping ---------------------------------------------------------

@pytest.mark.parametrize("code,exc", [
    (401, AuthenticationError),
    (403, AuthenticationError),
    (404, NotFoundError),
    (429, RateLimitError),
    (500, APIError),
])
def test_status_maps_to_exception(session, code, exc):
    c = CSpanClient("k", session=session.queue(FakeResponse(status_code=code)))
    with pytest.raises(exc) as info:
        c.bills("x")
    assert info.value.status_code == code


def test_rate_limit_retry_after(session):
    resp = FakeResponse(status_code=429, headers={"Retry-After": "7"})
    c = CSpanClient("k", session=session.queue(resp))
    with pytest.raises(RateLimitError) as info:
        c.bills("x")
    assert info.value.retry_after == 7.0


# -- pagination ------------------------------------------------------------

def test_iter_records_follows_cursor(session):
    page1 = FakeResponse(payload={"cursor": "NEXT", "results": [{"id": 1}, {"id": 2}]})
    page2 = FakeResponse(payload={"results": [{"id": 3}]})  # no cursor -> stop
    c = CSpanClient("k", session=session.queue(page1, page2))
    rows = list(c.iter_records(c.bills, query="x"))
    assert [r["id"] for r in rows] == [1, 2, 3]
    # second call carried the cursor forward
    assert session.calls[1][1]["cursor"] == "NEXT"


def test_iter_records_stops_on_repeated_cursor(session):
    # The real API returns a cursor on every page; a repeated cursor means the
    # end. Without a guard this would loop forever.
    session.queue(*[FakeResponse(payload={"cursor": "LOOP", "results": [{"id": 1}]})
                    for _ in range(10)])
    c = CSpanClient("k", session=session)
    rows = list(c.iter_records(c.bills, query="x"))
    # first page yields, second page repeats cursor -> stop
    assert rows == [{"id": 1}, {"id": 1}]
    assert len(session.calls) == 2


def test_iter_records_max_items(session):
    page1 = FakeResponse(payload={"cursor": "NEXT", "results": [{"id": 1}, {"id": 2}]})
    c = CSpanClient("k", session=session.queue(page1))
    rows = list(c.iter_records(c.bills, query="x", max_items=1))
    assert rows == [{"id": 1}]


# -- lifecycle -------------------------------------------------------------

def test_context_manager_closes(session):
    with CSpanClient("k", session=session) as c:
        assert isinstance(c, CSpanClient)
    assert session.closed

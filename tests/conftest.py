"""Shared test fixtures: an offline fake ``requests.Session``."""

from __future__ import annotations

import json as _json
from typing import Any

import pytest

from cspan import CSpanClient


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"results": []}
        self.headers = headers or {}
        self._text = text

    @property
    def text(self) -> str:
        if self._text is not None:
            return self._text
        return _json.dumps(self._payload)

    def json(self) -> Any:
        if self._text is not None:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    """Records GET calls and returns queued responses."""

    def __init__(self) -> None:
        self.headers: dict = {}
        self.calls: list[tuple[str, dict]] = []
        self._queue: list[FakeResponse] = []
        self.closed = False

    def queue(self, *responses: FakeResponse) -> FakeSession:
        self._queue.extend(responses)
        return self

    def get(self, url, params=None, timeout=None) -> FakeResponse:
        self.calls.append((url, dict(params or {})))
        if self._queue:
            return self._queue.pop(0)
        return FakeResponse()

    def mount(self, *_args, **_kwargs):  # pragma: no cover - not used with injection
        pass

    def close(self) -> None:
        self.closed = True

    @property
    def last(self) -> tuple[str, dict]:
        return self.calls[-1]


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def client(session: FakeSession) -> CSpanClient:
    return CSpanClient("TEST-KEY", session=session)

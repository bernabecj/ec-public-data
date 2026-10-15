from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from ecuadata import http
from ecuadata.config import config

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Every test gets an empty cache in tmp_path, online mode and no retry or throttle delays."""
    monkeypatch.setattr(config, "cache_dir", tmp_path / "cache")
    monkeypatch.setattr(config, "cache_ttl", "7d")
    monkeypatch.setattr(config, "offline", False)
    monkeypatch.setattr(http, "BACKOFF", 0)
    monkeypatch.setattr(http, "MIN_INTERVAL", 0)
    yield config


@pytest.fixture
def mock_http(monkeypatch):
    """Route every request through ``handler(request) -> httpx.Response``; record requests."""

    def install(handler: Callable[[httpx.Request], httpx.Response]) -> list[httpx.Request]:
        seen: list[httpx.Request] = []

        def recording(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        transport = httpx.MockTransport(recording)
        monkeypatch.setattr(http, "make_client", lambda: httpx.Client(transport=transport))
        return seen

    return install


@pytest.fixture
def no_network(mock_http):
    """Fail the test if anything tries to use the network."""

    def handler(request):
        raise AssertionError(f"Unexpected HTTP request to {request.url}")

    return mock_http(handler)

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

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


# --------------------------------------------------------------------------------------------
# Recorded fixtures and a tiny fixture-backed server
# --------------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def fixtures() -> Path:
    """Root of the recorded fixtures, ``tests/fixtures``."""
    return FIXTURES


def fixture_bytes(relative: str) -> bytes:
    return (FIXTURES / relative).read_bytes()


def fixture_json(relative: str):
    return json.loads((FIXTURES / relative).read_text(encoding="utf-8"))


@pytest.fixture
def serve_fixtures(mock_http):
    """Serve recorded files by URL.

    ``routes`` maps a substring of the request URL (path + query) to a fixture path relative
    to ``tests/fixtures``, raw bytes, or a callable ``request -> httpx.Response``. Unmatched
    requests get a 404. Returns the list of requests seen.
    """

    def install(routes: dict[str, object]) -> list[httpx.Request]:
        def handler(request: httpx.Request) -> httpx.Response:
            target = request.url.raw_path.decode()
            for needle, source in routes.items():
                if needle in target:
                    if callable(source):
                        return source(request)
                    content = fixture_bytes(source) if isinstance(source, str) else source
                    is_json = "wp-json" in target or target.endswith(".json")
                    headers = {"content-type": "application/json"} if is_json else {}
                    return httpx.Response(200, content=content, headers=headers)
            return httpx.Response(404, content=b"not found")

        return mock_http(handler)

    return install


def grid_from_bundle(bundle: dict, columns: list[str], value=1.0, rows=None) -> dict:
    """Build a BCEData grid document from a bundle's row list (for units not yet recorded)."""
    out = []
    for row in rows if rows is not None else bundle["rows"]:
        values = {} if row["tipo"] == "Cabeceras" else dict.fromkeys(columns, value)
        out.append({**row, "values": values})
    return {"columns": columns, "rows": out}


@pytest.fixture(scope="session")
def helpers():
    """Plain helper functions, reachable from tests without importing conftest."""
    return SimpleNamespace(
        fixture_bytes=fixture_bytes, fixture_json=fixture_json, grid_from_bundle=grid_from_bundle
    )

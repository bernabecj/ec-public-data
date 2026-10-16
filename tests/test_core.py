from datetime import timedelta

import httpx
import pytest

from ecuadata import cache, http
from ecuadata.exceptions import SourceUnavailableError


def test_cache_roundtrip_and_expiry():
    cache.store("bce", "a.xlsx", b"data", "https://example.org/a.xlsx")
    assert cache.load("bce", "a.xlsx").content == b"data"
    assert cache.load("bce", "a.xlsx", max_age=timedelta(0)) is None


def test_http_retries_server_errors(mock_http):
    responses = iter([httpx.Response(503), httpx.Response(200, content=b"ok")])
    mock_http(lambda request: next(responses))
    assert http.get("https://example.org/x").content == b"ok"


def test_http_does_not_retry_connect_errors(mock_http):
    def refuse(request):
        raise httpx.ConnectTimeout("timed out", request=request)

    seen = mock_http(refuse)
    with pytest.raises(SourceUnavailableError, match="bloqueando"):
        http.get("https://example.org/x")
    assert len(seen) == 1


def test_http_throttles_consecutive_requests(mock_http, monkeypatch):
    sleeps = []
    monkeypatch.setattr(http, "MIN_INTERVAL", 2.0)
    monkeypatch.setattr(http.time, "sleep", sleeps.append)
    mock_http(lambda request: httpx.Response(200))
    http.get("https://example.org/a")
    http.get("https://example.org/b")
    assert sleeps and 0 < sleeps[-1] <= 2.0


def test_cache_files_lists_json_data_files_but_not_sidecars():
    cache.store("bce", "a.xlsx", b"data", "u")
    cache.store("bce", "tree.json", b"[]", "u")
    assert sorted(cache.files("bce")) == ["a.xlsx", "tree.json"]

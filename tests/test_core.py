from datetime import timedelta

import httpx

from ecuadata import cache, http


def test_cache_roundtrip_and_expiry():
    cache.store("bce", "a.xlsx", b"data", "https://example.org/a.xlsx")
    assert cache.load("bce", "a.xlsx").content == b"data"
    assert cache.load("bce", "a.xlsx", max_age=timedelta(0)) is None


def test_http_retries_server_errors(mock_http):
    responses = iter([httpx.Response(503), httpx.Response(200, content=b"ok")])
    mock_http(lambda request: next(responses))
    assert http.get("https://example.org/x").content == b"ok"

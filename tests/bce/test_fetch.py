from datetime import date

import httpx
import pandas as pd
import pytest

from ecuadata import cache
from ecuadata.bce import fetch
from ecuadata.config import config
from ecuadata.exceptions import OfflineError

XLSX = b"PK\x03\x04 fake workbook"
TODAY = date(2026, 10, 13)  # last finished quarter: 2026Q3


def serve(published):
    """Serve the given file names; 404 everything else."""

    def handler(request):
        name = request.url.path.rsplit("/", 1)[-1]
        return (
            httpx.Response(200, content=published[name])
            if name in published
            else (httpx.Response(404))
        )

    return handler


def test_url_for():
    assert fetch.url_for("tou", "2025Q2").endswith("/trimestrales/tou_132_202502.xlsx")
    assert fetch.filename_for("tou", "2026Q1") == "tou_135_202601.xlsx"


def test_latest_walks_back_to_first_published(mock_http):
    mock_http(serve({"tou_134_202504.xlsx": XLSX}))
    assert fetch.fetch("tou", today=TODAY).quarter == pd.Period("2025Q4", freq="Q")


def test_cached_release_skips_network(no_network):
    cache.store("bce", "tou_134_202504.xlsx", XLSX, "u")
    assert fetch.fetch("tou", today=TODAY).content == XLSX


def test_offline_without_cache(no_network, monkeypatch):
    monkeypatch.setattr(config, "offline", True)
    with pytest.raises(OfflineError):
        fetch.fetch("tou", today=TODAY)

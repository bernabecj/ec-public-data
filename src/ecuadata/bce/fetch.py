"""Locate and download Banco Central del Ecuador quarterly national accounts workbooks.

BCE publishes each quarterly release as a set of XLSX files with predictable names::

    .../cuentasnacionales/trimestrales/tou_132_202502.xlsx
                                       ^   ^   ^
                                       |   |   year + quarter (2025 Q2)
                                       |   bulletin number
                                       table ("tou" = supply and use, i.e. GDP by expenditure)

The bulletin number goes up by one every quarter, so it can be computed from the quarter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from ecuadata import cache, http
from ecuadata._parsing import parse_quarter
from ecuadata.config import config
from ecuadata.exceptions import OfflineError, SourceUnavailableError

PROVIDER = "bce"
BASE_URL = (
    "https://contenido.bce.fin.ec/documentos/informacioneconomica/cuentasnacionales/trimestrales/"
)

# Bulletin 132 is the 2025 Q2 release; every later quarter adds one.
_ANCHOR_BULLETIN = 132
_ANCHOR_QUARTER = pd.Period("2025Q2", freq="Q")

# How many quarters back from the last finished quarter to look for the latest release.
LOOKBACK = 6

_XLSX_MAGIC = b"PK\x03\x04"


@dataclass(frozen=True)
class Release:
    """One downloaded workbook."""

    table: str
    quarter: pd.Period
    url: str
    content: bytes
    retrieved_at: datetime


def to_quarter(value: str | pd.Period | date) -> pd.Period:
    """Accept ``"2025Q2"``, ``"2025-II"``, a Period or a date."""
    if isinstance(value, str) and re.fullmatch(r"\d{4}Q[1-4]", value.strip().upper()):
        return pd.Period(value.strip().upper(), freq="Q")
    return parse_quarter(value)


def bulletin_for(quarter: str | pd.Period) -> int:
    """Bulletin number of the release covering ``quarter``.

    >>> bulletin_for("2025Q2")
    132
    """
    return _ANCHOR_BULLETIN + (to_quarter(quarter) - _ANCHOR_QUARTER).n


def filename_for(table: str, quarter: str | pd.Period) -> str:
    q = to_quarter(quarter)
    return f"{table}_{bulletin_for(q)}_{q.year}{q.quarter:02d}.xlsx"


def url_for(table: str, quarter: str | pd.Period) -> str:
    return BASE_URL + filename_for(table, quarter)


def _cached_quarters(table: str) -> list[pd.Period]:
    """Quarters of ``table`` present in the cache, newest first."""
    pattern = re.compile(rf"^{re.escape(table)}_\d+_(\d{{4}})(\d{{2}})\.xlsx$")
    quarters = []
    for name in cache.files(PROVIDER):
        match = pattern.match(name)
        if match:
            quarters.append(pd.Period(year=int(match[1]), quarter=int(match[2]), freq="Q"))
    return sorted(quarters, reverse=True)


def _from_cache(table: str, quarter: pd.Period, max_age=None) -> Release | None:
    cached = cache.load(PROVIDER, filename_for(table, quarter), max_age=max_age)
    if cached is None:
        return None
    return Release(table, quarter, cached.url, cached.content, cached.retrieved_at)


def _download(table: str, quarter: pd.Period) -> Release | None:
    """Download one release. Returns None if BCE has not published it."""
    url = url_for(table, quarter)
    response = http.get(url)
    if response.status_code != 200 or not response.content.startswith(_XLSX_MAGIC):
        return None
    stored = cache.store(PROVIDER, filename_for(table, quarter), response.content, url)
    return Release(table, quarter, url, stored.content, stored.retrieved_at)


def fetch(
    table: str = "tou",
    release: str | pd.Period | None = None,
    refresh: bool = False,
    today: date | None = None,
) -> Release:
    """Return the workbook for ``table``, from the cache when possible.

    Args:
        table: File prefix, e.g. ``"tou"``.
        release: Quarter of a specific release (``"2025Q2"``). None means the latest one.
        refresh: Ignore the cache and download again.
        today: Reference date for finding the latest release (for tests).

    Raises:
        OfflineError: offline mode is on and nothing suitable is cached.
        SourceUnavailableError: BCE is unreachable, or no release was found.
    """
    if release is not None:
        return _fetch_release(table, to_quarter(release), refresh)
    return _fetch_latest(table, refresh, today or date.today())


def _fetch_release(table: str, quarter: pd.Period, refresh: bool) -> Release:
    # A published release does not change, so a cached copy never expires.
    if not refresh and (cached := _from_cache(table, quarter)):
        return cached
    if config.offline:
        raise OfflineError(f"Release {quarter} of BCE table {table!r} is not in the cache.")
    downloaded = _download(table, quarter)
    if downloaded is None:
        raise SourceUnavailableError(
            f"BCE has not published release {quarter} of table {table!r} "
            f"(looked for {url_for(table, quarter)})."
        )
    return downloaded


def _fetch_latest(table: str, refresh: bool, today: date) -> Release:
    cached_quarters = _cached_quarters(table)
    if config.offline:
        if cached_quarters:
            return _from_cache(table, cached_quarters[0])
        raise OfflineError(f"No release of BCE table {table!r} is in the cache.")
    if not refresh and cached_quarters:
        fresh = _from_cache(table, cached_quarters[0], max_age=config.cache_ttl)
        if fresh:
            return fresh

    last_finished = pd.Period(today, freq="Q") - 1
    candidates = [last_finished - i for i in range(LOOKBACK)]
    for quarter in candidates:
        downloaded = _download(table, quarter)
        if downloaded:
            return downloaded
    raise SourceUnavailableError(
        f"No release of BCE table {table!r} found between {candidates[-1]} and "
        f"{candidates[0]} (e.g. {url_for(table, candidates[0])}). The bulletin numbering "
        "may have changed."
    )

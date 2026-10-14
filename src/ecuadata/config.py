"""Library-wide settings.

>>> import ecuadata as ec
>>> ec.config.cache_ttl = "12h"
>>> ec.config.offline = True
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import platformdirs

_DURATION = re.compile(r"^\s*(\d+)\s*([smhdw])\s*$")
_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


def parse_duration(value: timedelta | str | int | float) -> timedelta:
    """Turn ``"7d"``, ``"12h"``, ``"30m"``, a number of seconds or a timedelta into a timedelta."""
    if isinstance(value, timedelta):
        return value
    if isinstance(value, (int, float)):
        return timedelta(seconds=value)
    match = _DURATION.match(value)
    if not match:
        raise ValueError(f"Invalid duration {value!r}; use e.g. '7d', '12h', '30m'.")
    amount, unit = match.groups()
    return timedelta(**{_UNITS[unit]: int(amount)})


class Config:
    """Mutable settings shared by every provider.

    Attributes:
        cache_dir: Where downloaded files are stored. Defaults to the OS user cache directory.
        cache_ttl: How long a cached file is used before it is downloaded again.
        offline: If True, never touch the network; read only from the cache.
        timeout: HTTP timeout in seconds.
    """

    def __init__(self) -> None:
        self.cache_dir = Path(platformdirs.user_cache_dir("ecuadata", appauthor=False))
        self.cache_ttl = timedelta(days=7)
        self.offline = False
        self.timeout = 60.0

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    @cache_dir.setter
    def cache_dir(self, value: str | Path) -> None:
        self._cache_dir = Path(value)

    @property
    def cache_ttl(self) -> timedelta:
        return self._cache_ttl

    @cache_ttl.setter
    def cache_ttl(self, value: timedelta | str | int | float) -> None:
        self._cache_ttl = parse_duration(value)

    def __repr__(self) -> str:
        return (
            f"Config(cache_dir={str(self.cache_dir)!r}, cache_ttl={self.cache_ttl!r}, "
            f"offline={self.offline!r}, timeout={self.timeout!r})"
        )


config = Config()

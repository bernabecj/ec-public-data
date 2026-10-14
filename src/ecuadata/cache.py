"""On-disk cache of raw downloaded files.

Files live at ``<cache_dir>/<provider>/<filename>``, each with a ``<filename>.json`` sidecar
recording where and when it was downloaded. Only raw files are cached: parsing is cheap, and
keeping the original bytes means a parser fix never requires a new download.

>>> import ecuadata as ec
>>> ec.cache.clear("bce")  # one provider
>>> ec.cache.clear()       # everything
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ecuadata.config import config


@dataclass(frozen=True)
class CachedFile:
    content: bytes
    url: str
    retrieved_at: datetime

    def age(self) -> timedelta:
        return datetime.now(timezone.utc) - self.retrieved_at


def _path(provider: str, filename: str) -> Path:
    return config.cache_dir / provider / filename


def _meta_path(path: Path) -> Path:
    return path.with_name(path.name + ".json")


def store(provider: str, filename: str, content: bytes, url: str) -> CachedFile:
    """Save ``content`` under ``provider/filename`` and return it as a CachedFile."""
    path = _path(provider, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc)
    path.write_bytes(content)
    meta = {"url": url, "retrieved_at": retrieved_at.isoformat()}
    _meta_path(path).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return CachedFile(content, url, retrieved_at)


def load(provider: str, filename: str, max_age: timedelta | None = None) -> CachedFile | None:
    """Return the cached file, or None if it is missing, unreadable or ``max_age`` old or older."""
    path = _path(provider, filename)
    try:
        meta = json.loads(_meta_path(path).read_text(encoding="utf-8"))
        cached = CachedFile(
            content=path.read_bytes(),
            url=meta["url"],
            retrieved_at=datetime.fromisoformat(meta["retrieved_at"]),
        )
    except (OSError, ValueError, KeyError):
        return None
    if max_age is not None and cached.age() >= max_age:
        return None
    return cached


def files(provider: str) -> list[str]:
    """Names of the files cached for ``provider``, newest first."""
    folder = config.cache_dir / provider
    if not folder.is_dir():
        return []
    found = [p for p in folder.iterdir() if p.is_file() and p.suffix != ".json"]
    return [p.name for p in sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)]


def clear(provider: str | None = None) -> None:
    """Delete the cache for one provider, or the whole cache when ``provider`` is None."""
    target = config.cache_dir if provider is None else config.cache_dir / provider
    shutil.rmtree(target, ignore_errors=True)

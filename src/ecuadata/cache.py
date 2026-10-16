"""Caché en disco de los archivos descargados.

Los archivos se guardan en ``<cache_dir>/<fuente>/<archivo>``, cada uno con un archivo
``<archivo>.json`` al lado que registra de dónde y cuándo se descargó. Solo se guardan los
archivos originales: procesarlos es barato, y conservar los bytes originales permite corregir
un parser sin volver a descargar nada.

>>> import ecuadata as ec
>>> ec.cache.clear("bce")  # una fuente
>>> ec.cache.clear()       # todo
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
    """Guarda ``content`` como ``provider/filename`` y lo devuelve como CachedFile."""
    path = _path(provider, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc)
    path.write_bytes(content)
    meta = {"url": url, "retrieved_at": retrieved_at.isoformat()}
    _meta_path(path).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return CachedFile(content, url, retrieved_at)


def load(provider: str, filename: str, max_age: timedelta | None = None) -> CachedFile | None:
    """Devuelve el archivo del caché; None si no existe, no se puede leer o ya tiene ``max_age``."""
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
    """Nombres de los archivos en caché de ``provider``, del más reciente al más antiguo."""
    folder = config.cache_dir / provider
    if not folder.is_dir():
        return []
    found = [p for p in folder.iterdir() if p.is_file() and not _is_sidecar(p)]
    return [p.name for p in sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)]


def _is_sidecar(path: Path) -> bool:
    """``x.xlsx.json`` is the sidecar of ``x.xlsx``; a data file ``x.json`` is not a sidecar."""
    return path.suffix == ".json" and path.with_suffix("").is_file()


def clear(provider: str | None = None) -> None:
    """Borra el caché de una fuente, o todo el caché si ``provider`` es None."""
    target = config.cache_dir if provider is None else config.cache_dir / provider
    shutil.rmtree(target, ignore_errors=True)

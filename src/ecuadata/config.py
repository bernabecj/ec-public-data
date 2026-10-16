"""Configuración global de la librería.

>>> import ecuadata as ec
>>> ec.config.cache_ttl = "12h"      # cuánto tiempo reutilizar una descarga
>>> ec.config.offline = True         # no tocar la red; leer solo del caché
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import platformdirs

_DURATION = re.compile(r"^\s*(\d+)\s*([smhdw])\s*$")
_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


def parse_duration(value: timedelta | str | int | float) -> timedelta:
    """Convierte ``"7d"``, ``"12h"``, ``"30m"``, segundos (número) o un timedelta en timedelta."""
    if isinstance(value, timedelta):
        return value
    if isinstance(value, (int, float)):
        return timedelta(seconds=value)
    match = _DURATION.match(value)
    if not match:
        raise ValueError(f"Duración inválida {value!r}; use por ejemplo '7d', '12h' o '30m'.")
    amount, unit = match.groups()
    return timedelta(**{_UNITS[unit]: int(amount)})


class Config:
    """Configuración compartida por todas las fuentes. Se puede modificar en tiempo de ejecución.

    Attributes:
        cache_dir: Carpeta donde se guardan los archivos descargados. Por defecto, la carpeta
            de caché del usuario en el sistema operativo.
        cache_ttl: Cuánto tiempo se reutiliza un archivo del caché antes de volver a descargarlo.
        offline: Si es True, nunca se usa la red; solo se lee del caché.
        timeout: Tiempo máximo de espera HTTP, en segundos.
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

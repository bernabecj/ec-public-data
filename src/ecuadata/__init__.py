"""Datos públicos del Ecuador como DataFrames de pandas.

>>> import ecuadata as ec
>>> pib = ec.bce.pib_trimestral()
>>> ipc = ec.inec.ipc(start="2020-01")
>>> ec.list_sources()
>>> ec.search("inflacion")
"""

from ecuadata import bce, cache, inec
from ecuadata._catalog import list_sources, search
from ecuadata.config import config
from ecuadata.exceptions import (
    EcuadataError,
    OfflineError,
    ParseError,
    SourceUnavailableError,
)

__version__ = "0.1.0.dev0"

__all__ = [
    "EcuadataError",
    "OfflineError",
    "ParseError",
    "SourceUnavailableError",
    "__version__",
    "bce",
    "cache",
    "config",
    "inec",
    "list_sources",
    "search",
]

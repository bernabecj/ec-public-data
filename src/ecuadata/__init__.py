"""Ecuadorian public data as pandas DataFrames.

>>> import ecuadata as ec
>>> gdp = ec.bce.series("pib_trimestral")
"""

from ecuadata import bce, cache
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
]

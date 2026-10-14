"""Helpers for the quirks shared by Ecuadorian government files."""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, datetime

import pandas as pd

MISSING = {"", "-", "--", "n.d.", "nd", "n.d", "s.d.", "na", "n/a", "...", "…"}

_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}
# Trailing footnote markers: "(1)", "(p)" provisional, "(sd)" semi-definitive, "(prov)", "*".
_FOOTNOTE = re.compile(r"(\s*\(\d{1,2}\)|\s*\((?:p|sd|prov)\)|\s*\*+)+$", re.IGNORECASE)


def to_number(value: object) -> float:
    """Convert a cell to float, handling decimal commas, separators and placeholders.

    >>> to_number("1.234,5")
    1234.5
    >>> to_number("n.d.")
    nan
    """
    if value is None:
        return math.nan
    if isinstance(value, bool):
        raise TypeError(f"Unexpected boolean cell value {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    text = _FOOTNOTE.sub("", str(value).strip()).replace("\xa0", "").replace(" ", "")
    if text.lower() in MISSING:
        return math.nan
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    if "," in text and "." in text:
        # Whichever separator comes last is the decimal one.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    number = float(text)
    return -number if negative else number


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def snake_case(label: str) -> str:
    """Normalize a Spanish column label.

    >>> snake_case("Formación Bruta de Capital Fijo (FBKF)")
    'formacion_bruta_de_capital_fijo_fbkf'
    """
    text = strip_accents(_FOOTNOTE.sub("", str(label).strip())).lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


_QUARTER_PATTERNS = [
    # 2025.I, 2025-II, 2025 III, 2025/IV, 2025.T1, 2025-Q1, 2025T1, 2025Q1, 2025.1
    re.compile(r"^(?P<year>\d{4})\s*[.\-/ ]?\s*(?:T|Q)?(?P<q>IV|I{1,3}|[1-4])$"),
    # I-2025, II.2025, T1 2025, Q1-2025, I trimestre 2025, Trim. II 2025
    re.compile(
        r"^(?:TRIM(?:ESTRE)?\.?\s*)?(?:T|Q)?(?P<q>IV|I{1,3}|[1-4])\s*(?:TRIM(?:ESTRE)?)?"
        r"\s*(?:DEL?)?\s*[.\-/ ]?\s*(?P<year>\d{4})$"
    ),
]


def parse_quarter(value: object) -> pd.Period:
    """Parse a quarter label used by Ecuadorian publishers into a quarterly Period.

    >>> parse_quarter("2025.II")
    Period('2025Q2', 'Q-DEC')
    """
    if isinstance(value, pd.Period):
        return value.asfreq("Q")
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return pd.Period(value, freq="Q")
    text = strip_accents(_FOOTNOTE.sub("", str(value).strip())).upper()
    for pattern in _QUARTER_PATTERNS:
        match = pattern.match(text)
        if match:
            q = match["q"]
            quarter = _ROMAN.get(q) or int(q)
            return pd.Period(year=int(match["year"]), quarter=quarter, freq="Q")
    raise ValueError(f"Not a recognizable quarter label: {value!r}")

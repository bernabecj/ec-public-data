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
        raise TypeError(f"Valor booleano inesperado en la celda: {value!r}")
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
    raise ValueError(f"No se reconoce como etiqueta de trimestre: {value!r}")


# Spanish month names and their three-letter abbreviations as used by BCE and INEC.
SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}  # fmt: skip
_MONTH_ABBREVIATIONS = {name[:3]: number for name, number in SPANISH_MONTHS.items()}
_MONTH_ABBREVIATIONS["sep"] = 9


def month_number(name: str) -> int:
    """``"Ene"``, ``"enero"``, ``"sept"`` ... -> 1, 1, 9."""
    key = strip_accents(name.strip().lower().rstrip("."))
    if key in SPANISH_MONTHS:
        return SPANISH_MONTHS[key]
    if key[:3] in _MONTH_ABBREVIATIONS:
        return _MONTH_ABBREVIATIONS[key[:3]]
    raise ValueError(f"No es un nombre de mes en español: {name!r}")


_MONTH_PATTERNS = [
    # Ene 2006, enero 2026, Enero de 2026, ene-2026
    re.compile(r"^(?P<month>[A-Za-z\u00C0-\u00FF]{3,10})\.?\s*(?:de\s+)?[-/ ]?\s*(?P<year>\d{4})$"),
    # 2026-01, 2026/01, 2026M01, 2026.01, 202601
    re.compile(r"^(?P<year>\d{4})\s*[-/.M]?\s*(?P<mnum>\d{2})$"),
]


def parse_month(value: object) -> pd.Period:
    """Parse a month label used by Ecuadorian publishers into a monthly Period.

    >>> parse_month("Ene 2006")
    Period('2006-01', 'M')
    >>> parse_month("2026-08")
    Period('2026-08', 'M')
    """
    if isinstance(value, pd.Period):
        return value.asfreq("M")
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return pd.Period(value, freq="M")
    text = str(value).strip()
    for pattern in _MONTH_PATTERNS:
        match = pattern.match(text)
        if match:
            groups = match.groupdict()
            month = int(groups["mnum"]) if groups.get("mnum") else month_number(groups["month"])
            if not 1 <= month <= 12:
                break
            return pd.Period(year=int(groups["year"]), month=month, freq="M")
    raise ValueError(f"No se reconoce como etiqueta de mes: {value!r}")


# "Ene 2015 (05 al 11)", "Oct 2026 (26 al 01 nov)", "Dic 2015 (28 al 03 ene 2016)"
_WEEK_PATTERN = re.compile(
    r"^(?P<month>[A-Za-z\u00C0-\u00FF]{3,10})\.?\s+(?P<year>\d{4})\s*\(\s*(?P<day>\d{1,2})"
    r"(?:\s+(?P<start_month>[A-Za-z\u00C0-\u00FF]{3,10}))?\s+al\s+.*\)$"
)


def parse_week(value: object) -> pd.Period:
    """Parse a BCE weekly label into a Monday-to-Sunday weekly Period.

    >>> parse_week("Ene 2015 (05 al 11)")
    Period('2015-01-05/2015-01-11', 'W-SUN')
    """
    match = _WEEK_PATTERN.match(str(value).strip())
    if not match:
        raise ValueError(f"No se reconoce como etiqueta de semana: {value!r}")
    month = month_number(match["start_month"] or match["month"])
    start = date(int(match["year"]), month, int(match["day"]))
    return pd.Period(start, freq="W-SUN")


def parse_year(value: object) -> pd.Period:
    """``2025``, ``"2025"``, ``2025.0`` -> yearly Period."""
    if isinstance(value, pd.Period):
        return value.asfreq("Y")
    text = str(value).strip()
    if re.fullmatch(r"\d{4}(\.0)?", text):
        return pd.Period(year=int(float(text)), freq="Y")
    raise ValueError(f"No se reconoce como etiqueta de año: {value!r}")

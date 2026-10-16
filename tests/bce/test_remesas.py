"""Remittances workbook parser and fetch, against the recorded BCE workbook."""

from __future__ import annotations

import math

import httpx
import pandas as pd
import pytest

from ecuadata import cache
from ecuadata.bce import _remesas as remesas
from ecuadata.config import config
from ecuadata.exceptions import OfflineError, ParseError, SourceUnavailableError

WORKBOOK = "bce/remesas/Flujo_de_remesas_de_trabajadores.xlsx"


@pytest.fixture(scope="module")
def content(fixtures):
    return (fixtures / WORKBOOK).read_bytes()


# -- sheet names -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "sheet"),
    [
        (("received", "Q", None, False), "RR_t"),
        (("received", "A", None, False), "RR_a"),
        (("sent", "Q", None, False), "RE_t"),
        (("received", "Q", "country", False), "RRpais_t"),
        (("received", "A", "country", True), "RRpaisg_a"),
        (("sent", "A", "country", True), "REpaisg_a"),
    ],
)
def test_sheet_name(args, sheet):
    assert remesas.sheet_name(*args) == sheet


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("inbound", "Q", None, False), "Flujo desconocido"),
        (("received", "M", None, False), "Frecuencia desconocida"),
        (("received", "Q", "city", False), "Desglose desconocido"),
        (("received", "Q", None, True), "by='country'"),
    ],
)
def test_sheet_name_validation(args, message):
    with pytest.raises(ValueError, match=message):
        remesas.sheet_name(*args)


# -- totals ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("flow", "frequency", "first", "last", "n", "first_count"),
    [
        ("received", "Q", "1993Q1", "2026Q2", 134, "2007Q1"),
        ("received", "A", "1993", "2025", 33, "2007"),
        ("sent", "Q", "2005Q1", "2026Q2", 86, "2010Q1"),
        ("sent", "A", "2005", "2025", 21, "2010"),
    ],
)
def test_parse_totals(content, flow, frequency, first, last, n, first_count):
    frame = remesas.parse_totals(
        content, remesas.sheet_name(flow, frequency, None, False), frequency
    )
    freq = "Q-DEC" if frequency == "Q" else "Y-DEC"
    assert frame.index.freqstr == freq and frame.index.name == "period"
    assert frame.index[0] == pd.Period(first, freq=freq)
    assert frame.index[-1] == pd.Period(last, freq=freq)
    assert len(frame) == n
    assert list(frame.columns) == ["monto_usd", "numero_giros"]
    assert set(frame.dtypes.astype(str)) == {"float64"}
    assert frame["monto_usd"].notna().all()
    assert str(frame["numero_giros"].first_valid_index()) == first_count
    assert frame.attrs["original_columns"]["numero_giros"].startswith("Número de giros")


def test_parse_totals_known_values(content):
    frame = remesas.parse_totals(content, "RR_t", "Q")
    assert frame.loc["1993Q1", "monto_usd"] == pytest.approx(50_230_800)
    assert frame.loc["2026Q2", "monto_usd"] == pytest.approx(2_041_259_661.78)
    assert frame.loc["2026Q2", "numero_giros"] == 5_851_244
    annual = remesas.parse_totals(content, "RR_a", "A")
    # Annual totals equal the sum of the four quarters.
    assert annual.loc["2025", "monto_usd"] == pytest.approx(
        frame.loc["2025Q1":"2025Q4", "monto_usd"].sum(), rel=1e-9
    )


# -- by country ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("flow", "frequency", "count", "first", "last"),
    [
        ("received", "Q", False, "2007Q1", "2026Q2"),
        ("received", "A", True, "2007", "2025"),
        ("sent", "Q", False, "2009Q4", "2026Q2"),
        ("sent", "A", True, "2010", "2025"),
    ],
)
def test_parse_by_country(content, flow, frequency, count, first, last):
    sheet = remesas.sheet_name(flow, frequency, "country", count)
    frame = remesas.parse_by_country(content, sheet, frequency)
    freq = "Q-DEC" if frequency == "Q" else "Y-DEC"
    assert frame.index.freqstr == freq
    assert frame.index[0] == pd.Period(first, freq=freq)
    assert frame.index[-1] == pd.Period(last, freq=freq)
    assert "total" in frame.columns and "espana" in frame.columns
    assert frame.attrs["country_codes"]["espana"] == "724"
    assert frame.attrs["country_codes"]["total"] is None
    assert frame.attrs["original_columns"]["espana"] == "España"
    # Countries add up to BCE's own total in every period.
    diff = (frame.drop(columns="total").sum(axis=1) - frame["total"]).abs().max()
    assert diff < 1e-6 * frame["total"].abs().max()


def test_parse_by_country_merges_rows_split_by_capitalisation(content):
    frame = remesas.parse_by_country(content, "RRpais_t", "Q")
    assert frame.attrs["merged_duplicate_rows"] == ["San Vicente y las Granadinas"]
    assert frame.columns.tolist().count("san_vicente_y_las_granadinas") == 1
    merged = frame["san_vicente_y_las_granadinas"]
    assert merged.notna().sum() == 66  # 4 values from one row + 62 from the other, no overlap
    assert merged.sum() == pytest.approx(
        frame["total"].sum()
        - frame.drop(columns=["total", "san_vicente_y_las_granadinas"]).sum().sum()
    )


def test_combine():
    nan = float("nan")
    assert remesas._combine(1.0, 2.0) == 3.0
    assert remesas._combine(nan, 2.0) == 2.0
    assert remesas._combine(1.0, nan) == 1.0
    assert math.isnan(remesas._combine(nan, nan))


# -- layout drift ----------------------------------------------------------------------------


def test_parse_errors(content):
    with pytest.raises(ParseError, match="no es un libro XLSX legible"):
        remesas.parse_totals(b"nope", "RR_t", "Q")
    with pytest.raises(ParseError, match="No existe la hoja 'XX'"):
        remesas.parse_totals(content, "XX", "Q")
    with pytest.raises(ParseError, match="No se encontró el encabezado 'año'"):
        remesas.parse_totals(content, "RR_t", "A")  # quarterly sheet read as annual
    with pytest.raises(ParseError, match="No se encontró el encabezado 'código'"):
        remesas.parse_by_country(content, "RR_t", "Q")


# -- fetch -----------------------------------------------------------------------------------


def test_fetch_downloads_validates_and_caches(serve_fixtures):
    seen = serve_fixtures({"Flujo_de_remesas_de_trabajadores.xlsx": WORKBOOK})
    first = remesas.fetch()
    second = remesas.fetch()
    assert first.url == remesas.URL
    assert first.content.startswith(b"PK\x03\x04")
    assert second.content == first.content
    assert len(seen) == 1
    assert cache.files("bce") == [remesas.FILENAME]
    remesas.fetch(refresh=True)
    assert len(seen) == 2


def test_fetch_rejects_html_and_404(mock_http):
    mock_http(lambda request: httpx.Response(200, content=b"<html>moved</html>"))
    with pytest.raises(SourceUnavailableError, match="HTTP 200"):
        remesas.fetch()
    mock_http(lambda request: httpx.Response(404))
    with pytest.raises(SourceUnavailableError, match="HTTP 404"):
        remesas.fetch()


def test_fetch_offline(no_network, monkeypatch):
    monkeypatch.setattr(config, "offline", True)
    with pytest.raises(OfflineError):
        remesas.fetch()
    cache.store("bce", remesas.FILENAME, b"PK\x03\x04x", remesas.URL)
    assert remesas.fetch().content == b"PK\x03\x04x"

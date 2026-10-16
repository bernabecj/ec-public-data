"""BCE quarterly national accounts parser, against the recorded 2026Q1 and 2026Q2 workbooks."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from ecuadata.bce import parse
from ecuadata.exceptions import ParseError

RELEASES = {
    "2026Q1": "bce/pib_trimestral/tou_135_202601.xlsx",
    "2026Q2": "bce/pib_trimestral/tou_136_202602.xlsx",
}
CORE_COLUMNS = [
    "pib",
    "consumo_hogares",
    "consumo_gobierno",
    "fbkf",
    "exportaciones",
    "importaciones",
]


@pytest.fixture(scope="module")
def workbooks(fixtures):
    return {release: (fixtures / path).read_bytes() for release, path in RELEASES.items()}


@pytest.mark.parametrize(("measure", "seasonally_adjusted"), list(parse.MEASURES))
def test_every_measure_parses_with_the_common_schema(workbooks, measure, seasonally_adjusted):
    frame = parse.parse_pib_trimestral(workbooks["2026Q2"], measure, seasonally_adjusted)
    assert isinstance(frame.index, pd.PeriodIndex)
    assert frame.index.freqstr == "Q-DEC"
    assert frame.index.name == "quarter"
    assert frame.index[0] == pd.Period("2000Q1", freq="Q")
    assert frame.index[-1] == pd.Period("2026Q2", freq="Q")
    assert frame.index.is_unique and frame.index.is_monotonic_increasing
    assert set(frame.dtypes.astype(str)) == {"float64"}
    assert set(CORE_COLUMNS) <= set(frame.columns)
    assert frame.attrs["measure"] == measure
    assert frame.attrs["seasonally_adjusted"] is seasonally_adjusted
    assert frame.attrs["sheet"] == parse.MEASURES[(measure, seasonally_adjusted)].sheet
    assert set(frame.attrs["original_columns"]) == set(frame.columns)


def test_current_price_tables_have_the_extra_aggregates(workbooks):
    frame = parse.parse_pib_trimestral(workbooks["2026Q2"], "current_prices", False)
    assert list(frame.columns) == [
        "pib",
        "importaciones",
        "oferta_final",
        "demanda_interna",
        "consumo_hogares",
        "consumo_gobierno",
        "fbkf",
        "variacion_existencias",
        "exportaciones",
        "utilizacion_final",
    ]
    # Supply equals use, as in any national accounts table.
    assert (frame["oferta_final"] - frame["utilizacion_final"]).abs().max() < 1e-3
    assert (
        frame.attrs["original_columns"]["consumo_hogares"] == "Gasto de Consumo final  Hogares (*)"
    )


def test_known_values(workbooks):
    frame = parse.parse_pib_trimestral(workbooks["2026Q2"], "current_prices", False)
    assert frame.loc["2000Q1", "pib"] == pytest.approx(3431205.89, abs=0.01)
    assert frame.loc["2026Q2", "pib"] == pytest.approx(33396116.63, abs=0.01)
    growth = parse.parse_pib_trimestral(workbooks["2026Q2"], "growth_yoy")
    assert growth.loc["2026Q2", "pib"] == pytest.approx(2.1459, abs=1e-4)
    assert growth.loc["2000Q1":"2000Q4", "pib"].isna().all()  # no previous year to compare


def test_older_release_ends_one_quarter_earlier(workbooks):
    frame = parse.parse_pib_trimestral(workbooks["2026Q1"])
    assert frame.index[-1] == pd.Period("2026Q1", freq="Q")
    assert len(frame) == 105


def test_measure_for_errors():
    with pytest.raises(ValueError, match="Medida desconocida"):
        parse.measure_for("gdp", True)
    with pytest.raises(ValueError, match="solo con ajuste estacional"):
        parse.measure_for("growth_yoy", False)


def test_column_name_mapping():
    assert parse.column_name("Importaciones de bienes y servicios (FOB)") == "importaciones"
    assert parse.column_name("Gasto de Consumo final  Hogares (*)") == "consumo_hogares"
    assert parse.column_name("Algo nuevo (p)") == "algo_nuevo"  # unknown labels never fail


# -- Layout drift ----------------------------------------------------------------------------


def rows(header=("Variables", "PIB", "FBKF"), data=(("2000.I", 1.0, 2.0), ("2000.II", 3.0, 4.0))):
    return [[None] * 3, list(header), ["Trimestres", None, None], [None] * 3, *map(list, data)]


def test_frame_from_rows_happy_path():
    frame = parse._frame_from_rows(rows(), "sheet")
    assert list(frame.columns) == ["pib", "fbkf"]
    assert frame.loc["2000Q2", "fbkf"] == 4.0


def test_frame_from_rows_stops_at_footnotes():
    frame = parse._frame_from_rows([*rows(), ["Nota: (*) algo", None, None]], "sheet")
    assert len(frame) == 2


def test_frame_from_rows_handles_placeholders_and_short_rows():
    frame = parse._frame_from_rows(rows(data=(("2000.I", "n.d.", 2.0), ("2000.II", 3.0))), "sheet")
    assert math.isnan(frame.loc["2000Q1", "pib"])
    assert math.isnan(frame.loc["2000Q2", "fbkf"])


@pytest.mark.parametrize(
    ("bad_rows", "message"),
    [
        (rows(header=("Variable", "PIB")), "fila de encabezado"),
        (rows(header=("Variables",)), "no tiene nombres de variables"),
        (rows(header=("Variables", "FBKF", "Exportaciones")), "le falta"),
        (rows(data=()), "no tiene filas trimestrales"),
        (rows(data=(("2000.I", 1, 2), ("2000.I", 1, 2))), "mismo trimestre dos veces"),
        (rows(data=(("2000.II", 1, 2), ("2000.I", 1, 2))), "orden cronológico"),
        (rows(header=("Variables", "PIB", "PIB")), "variables repetidos"),
        (rows(data=(("2000.I", "abc", 2.0),)), "Celda inesperada"),
    ],
)
def test_frame_from_rows_reports_layout_changes(bad_rows, message):
    with pytest.raises(ParseError, match=message):
        parse._frame_from_rows(bad_rows, "sheet")


def test_parse_sheet_rejects_non_workbook_and_missing_sheet(workbooks):
    with pytest.raises(ParseError, match="no es un libro XLSX legible"):
        parse.parse_sheet(b"not a workbook", "Dem_Cad_ajus")
    with pytest.raises(ParseError, match="No existe la hoja 'Nope'"):
        parse.parse_sheet(workbooks["2026Q2"], "Nope")

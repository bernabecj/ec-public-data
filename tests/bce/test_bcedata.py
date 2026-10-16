"""BCEData REST client and grid parser, against the recorded API documents."""

from __future__ import annotations

import json
import math
from datetime import timedelta

import httpx
import pandas as pd
import pytest

from ecuadata import cache
from ecuadata.bce import bcedata
from ecuadata.config import config
from ecuadata.exceptions import OfflineError, ParseError, SourceUnavailableError

API = "bce/bcedata/"

# (id_grupo, frecuencia, expected freqstr, first period, last period, n_series)
RECORDED_GRIDS = [
    (63, "Mensual", "M", "2006-01", "2026-08", 14),
    (35, "Mensual", "M", "2000-01", "2026-08", 11),
    (50, "Mensual", "M", "2015-08", "2021-04", 52),
    (51, "Mensual", "M", "2021-05", "2026-10", 26),
    (68, "Mensual", "M", "2007-12", "2026-05", 27),
    (2, "Trimestral", "Q-DEC", "2016Q1", "2026Q2", 145),
    (90, "Anual", "Y-DEC", "1966", "2025", 7),
    (49, "Semanal", "W-SUN", "2015-01-05", "2026-10-26", 1),
]


# -- parse_grid ------------------------------------------------------------------------------


@pytest.mark.parametrize(("gid", "freq", "freqstr", "first", "last", "n"), RECORDED_GRIDS)
def test_parse_grid_recorded_tables(helpers, gid, freq, freqstr, first, last, n):
    frame = bcedata.parse_grid(helpers.fixture_json(f"{API}grid_{gid}.json"), freq)
    assert isinstance(frame.index, pd.PeriodIndex)
    assert frame.index.freqstr == freqstr
    assert frame.index.name == "period"
    assert frame.index.is_unique and frame.index.is_monotonic_increasing
    assert frame.index[0] == pd.Period(first, freq=freqstr)
    assert frame.index[-1] == pd.Period(last, freq=freqstr)
    assert frame.shape[1] == n
    assert set(frame.dtypes.astype(str)) == {"float64"}
    assert set(frame.attrs["original_columns"]) == set(frame.columns)
    assert set(frame.attrs["tokens"]) == set(frame.columns)


def test_parse_grid_known_values(helpers):
    ipc = bcedata.parse_grid(helpers.fixture_json(f"{API}grid_63.json"), "Mensual")
    assert ipc.loc["2006-01", "indice_general_ipc"] == pytest.approx(60.3199, abs=1e-4)
    assert ipc.loc["2026-08", "indice_general_ipc"] == pytest.approx(100.8380, abs=1e-4)
    assert math.isnan(ipc.loc["2006-01", "seguros_y_servicios_financieros"])


def test_parse_grid_names_rows_by_hierarchy_path(helpers):
    labour = bcedata.parse_grid(helpers.fixture_json(f"{API}grid_68.json"), "Mensual")
    assert {"nacional_desempleo", "urbano_desempleo", "rural_desempleo"} <= set(labour.columns)
    assert labour.attrs["sections"]["urbano_desempleo"] == "urbano"
    assert labour.attrs["original_columns"]["urbano_desempleo"] == "DESEMPLEO"

    bop = bcedata.parse_grid(helpers.fixture_json(f"{API}grid_2.json"), "Trimestral")
    assert "cuenta_corriente_bienes_y_servicios_bienes_exportaciones" in bop.columns
    assert "cuenta_corriente_bienes_y_servicios_servicios_exportaciones" in bop.columns
    assert bop.attrs["sections"]["cuenta_corriente"] is None


def test_parse_grid_keeps_first_of_overlapping_weeks(helpers):
    weekly = bcedata.parse_grid(helpers.fixture_json(f"{API}grid_49.json"), "Semanal")
    assert weekly.attrs["dropped_duplicate_periods"] == ["Jun 2024 (01 al 07)"]
    assert weekly.loc[pd.Period("2024-05-27", freq="W-SUN"), "basica"] == pytest.approx(0.2)


def grid(columns, rows):
    return {"columns": columns, "rows": rows}


def series(label, values, nivel=1, **extra):
    return {
        "tipo": "Series",
        "label": label,
        "nivel": nivel,
        "token": "t",
        "values": values,
        **extra,
    }


def test_parse_grid_errors():
    with pytest.raises(ParseError, match="Frecuencia de BCEData desconocida"):
        bcedata.parse_grid(grid(["Ene 2020"], []), "Diaria")
    with pytest.raises(ParseError, match="no tiene 'columns' o 'rows'"):
        bcedata.parse_grid({"rows": []}, "Mensual")
    with pytest.raises(ParseError, match="no tiene períodos"):
        bcedata.parse_grid(grid([], []), "Mensual")
    with pytest.raises(ParseError, match="Etiqueta de período Mensual no reconocida"):
        bcedata.parse_grid(grid(["2020-I"], [series("a", {"2020-I": 1})]), "Mensual")
    with pytest.raises(ParseError, match="no contiene filas de tipo 'Series'"):
        bcedata.parse_grid(grid(["Ene 2020"], [{"tipo": "Cabeceras", "label": "x"}]), "Mensual")
    with pytest.raises(ParseError, match="Serie repetida"):
        rows = [series("PIB", {"Ene 2020": 1}), series("PIB", {"Ene 2020": 2})]
        bcedata.parse_grid(grid(["Ene 2020"], rows), "Mensual")
    with pytest.raises(ParseError, match="Valor no numérico"):
        bcedata.parse_grid(grid(["Ene 2020"], [series("a", {"Ene 2020": "abc"})]), "Mensual")
    with pytest.raises(ParseError, match="valores de tipo list"):
        bcedata.parse_grid(grid(["Ene 2020"], [series("a", [1])]), "Mensual")


def test_parse_grid_missing_and_placeholder_values_become_nan():
    frame = bcedata.parse_grid(
        grid(["Ene 2020", "Feb 2020"], [series("a", {"Ene 2020": "-"})]), "Mensual"
    )
    assert frame["a"].isna().all()


def test_parse_grid_sorts_periods():
    frame = bcedata.parse_grid(
        grid(["Feb 2020", "Ene 2020"], [series("a", {"Feb 2020": 2, "Ene 2020": 1})]), "Mensual"
    )
    assert frame["a"].tolist() == [1.0, 2.0]


# -- slice_periods ---------------------------------------------------------------------------


def test_slice_periods(helpers):
    frame = bcedata.parse_grid(helpers.fixture_json(f"{API}grid_63.json"), "Mensual")
    assert bcedata.slice_periods(frame, None, None) is frame
    sliced = bcedata.slice_periods(frame, "2025-01", "2025-06")
    assert sliced.index[0] == pd.Period("2025-01", freq="M")
    assert sliced.index[-1] == pd.Period("2025-06", freq="M")
    assert len(sliced) == 6
    assert bcedata.slice_periods(frame, "2026-08", None).shape[0] == 1
    assert bcedata.slice_periods(frame, None, "2006-01").shape[0] == 1
    assert bcedata.slice_periods(frame, "2030-01", None).empty


# -- get_json: cache, offline, errors --------------------------------------------------------


def test_get_json_downloads_then_uses_cache(serve_fixtures):
    seen = serve_fixtures({"/bundle/63": f"{API}bundle_63.json"})
    first = bcedata.get_json("bundle/63")
    second = bcedata.get_json("bundle/63")
    assert first.data["context"]["id_grupo"] == 63
    assert second.data == first.data
    assert len(seen) == 1
    assert cache.files("bce") == ["bcedata_bundle_63.json"]


def test_get_json_refresh_and_ttl(serve_fixtures, monkeypatch):
    seen = serve_fixtures({"/bundle/63": f"{API}bundle_63.json"})
    bcedata.get_json("bundle/63")
    bcedata.get_json("bundle/63", refresh=True)
    assert len(seen) == 2
    monkeypatch.setattr(config, "cache_ttl", timedelta(0))
    bcedata.get_json("bundle/63")
    assert len(seen) == 3


def test_get_json_offline(no_network, monkeypatch):
    monkeypatch.setattr(config, "offline", True)
    with pytest.raises(OfflineError):
        bcedata.get_json("tree")
    cache.store("bce", "bcedata_tree.json", b"[]", "u")
    assert bcedata.get_json("tree").data == []


def test_get_json_reports_api_errors(mock_http):
    mock_http(lambda request: httpx.Response(400, json={"code": "x", "message": "falta unidad"}))
    with pytest.raises(SourceUnavailableError, match=r"HTTP 400.*falta unidad"):
        bcedata.get_json("grid", {"id_grupo": 35})


def test_get_json_rejects_non_json(mock_http):
    mock_http(lambda request: httpx.Response(200, content=b"<html>maintenance</html>"))
    with pytest.raises(ParseError, match="no devolvió JSON"):
        bcedata.get_json("tree")


def test_get_json_query_string_and_cache_name(serve_fixtures):
    seen = serve_fixtures({"/grid?": f"{API}grid_35.json"})
    params = {"id_grupo": 35, "frecuencia": "Mensual", "unidad": "Millones de USD", "desde": None}
    response = bcedata.get_json("grid", params)
    assert str(seen[0].url).endswith("grid?id_grupo=35&frecuencia=Mensual&unidad=Millones+de+USD")
    assert response.url == str(seen[0].url)
    assert cache.files("bce") == [
        "bcedata_grid_id_grupo_35_frecuencia_Mensual_unidad_Millones_de_USD.json"
    ]


def test_tree_and_bundle_shape_checks(mock_http):
    mock_http(lambda request: httpx.Response(200, json={"not": "a list"}))
    with pytest.raises(ParseError, match="no devolvió una lista"):
        bcedata.tree()
    with pytest.raises(ParseError, match="forma inesperada"):
        bcedata.bundle(63)


def test_tree_lists_tables(serve_fixtures):
    serve_fixtures({"/tree": f"{API}tree.json"})
    nodes = bcedata.tree()
    tables = {n["id_grupo"]: n["desc_clasificador"] for n in nodes if n["id_grupo"] is not None}
    assert tables[63].endswith("Índice de Precios al Consumidor")
    assert set(bcedata.TABLES.values()) <= set(tables)


# -- table() ---------------------------------------------------------------------------------


def test_table_uses_bundle_defaults_and_full_range(serve_fixtures):
    seen = serve_fixtures({"/bundle/63": f"{API}bundle_63.json", "/grid?": f"{API}grid_63.json"})
    frame = bcedata.table(63)
    grid_url = str(seen[-1].url)
    assert "id_grupo=63" in grid_url and "frecuencia=Mensual" in grid_url
    assert (
        "unidad=Indice" in grid_url and "desde=2005-02" in grid_url and "hasta=2026-08" in grid_url
    )
    assert frame.attrs["cod_grupo"] == "4.2.1"
    assert frame.attrs["frequency"] == "Mensual"
    assert frame.attrs["units"] == "Indice"
    assert frame.attrs["units_note"].startswith("Índice, julio 2025-junio 2026=100")
    assert frame.attrs["url"] == grid_url
    assert frame.attrs["portal_url"] == bcedata.PORTAL_URL
    assert "retrieved_at" in frame.attrs


def test_table_passes_explicit_range(serve_fixtures):
    seen = serve_fixtures({"/bundle/63": f"{API}bundle_63.json", "/grid?": f"{API}grid_63.json"})
    bcedata.table(63, unidad="Porcentaje", start="2020-01", end=pd.Period("2020-12", freq="M"))
    assert "unidad=Porcentaje&desde=2020-01&hasta=2020-12" in str(seen[-1].url)


def test_table_validates_frequency_and_unit(serve_fixtures):
    serve_fixtures({"/bundle/63": f"{API}bundle_63.json"})
    with pytest.raises(ValueError, match="no se publica con frecuencia 'Anual'"):
        bcedata.table(63, frecuencia="Anual")
    with pytest.raises(ValueError, match="no tiene la unidad 'USD'"):
        bcedata.table(63, unidad="USD")


def test_table_without_frequencies_is_a_parse_error(mock_http):
    bundle = json.dumps({"context": {}, "frecuencias": [], "unidades": {}}).encode()
    mock_http(lambda request: httpx.Response(200, content=bundle))
    with pytest.raises(ParseError, match="no ofrece ninguna frecuencia"):
        bcedata.table(63)

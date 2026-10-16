"""INEC consumer price index served through BCEData table 4.2.1."""

from __future__ import annotations

import httpx
import pandas as pd
import pytest

from ecuadata.bce import bcedata
from ecuadata.exceptions import ParseError
from ecuadata.inec import _ipc as ipc

API = "bce/bcedata/"
DIVISIONS = [
    "alimentos_bebidas_no_alcoholicas",
    "bebidas_alcoholicas_tabaco",
    "prendas_vestir_calzado",
    "vivienda_servicios_basicos",
    "muebles_articulos_hogar",
    "salud",
    "transporte",
    "informacion_comunicacion",
    "recreacion_cultura",
    "educacion",
    "restaurantes_alojamiento",
    "seguros_servicios_financieros",
    "bienes_servicios_diversos",
]


@pytest.fixture
def api(serve_fixtures, helpers):
    bundle = helpers.fixture_json(f"{API}bundle_63.json")

    def percent_grid(request):
        """Unit 'Porcentaje' is not recorded yet: build it from the bundle's sectioned rows."""
        columns = ["Jul 2026", "Ago 2026"]
        grid = helpers.grid_from_bundle(bundle, columns, value=0.5, rows=bundle["rows"][14:])
        return httpx.Response(200, json=grid)

    return serve_fixtures(
        {
            "/bundle/63": f"{API}bundle_63.json",
            "unidad=Indice": f"{API}grid_63.json",
            "unidad=Porcentaje": percent_grid,
        }
    )


def test_index_schema_and_values(api):
    frame = ipc.ipc()
    assert list(frame.columns) == ["general", *DIVISIONS]
    assert frame.index.freqstr == "M" and frame.index.name == "period"
    assert frame.index[0] == pd.Period("2006-01", freq="M")
    assert frame.index[-1] == pd.Period("2026-08", freq="M")
    assert set(frame.dtypes.astype(str)) == {"float64"}
    assert frame.loc["2026-08", "general"] == pytest.approx(100.838, abs=1e-3)
    assert frame.loc["2006-01", "transporte"] == pytest.approx(65.94, abs=1e-2)


def test_index_attrs(api):
    frame = ipc.ipc()
    assert frame.attrs["source"] == "INEC"
    assert frame.attrs["via"].startswith("BCEData del BCE")
    assert frame.attrs["dataset"] == "ipc"
    assert frame.attrs["measure"] == "index"
    assert frame.attrs["base"].startswith("Índice, julio 2025-junio 2026=100")
    assert "unidad=Indice" in frame.attrs["url"]
    assert frame.attrs["portal_url"] == bcedata.PORTAL_URL
    assert frame.attrs["original_columns"]["general"] == "Índice General - IPC"
    assert frame.attrs["original_columns"]["educacion"] == "Servicios educativos"


def test_start_end_are_applied_locally(api):
    frame = ipc.ipc(start="2024-01", end="2024-12")
    assert len(frame) == 12
    assert frame.index[0] == pd.Period("2024-01", freq="M")
    assert len(api) == 2  # bundle + one grid; slicing did not trigger another request
    ipc.ipc(start="2025-01")
    assert len(api) == 2  # second slice served from the cache


@pytest.mark.parametrize(
    ("measure", "section"),
    [
        ("monthly_change", "Variación Mensual"),
        ("annual_change", "Variación Anual"),
        ("ytd_change", "Variación Acumulada"),
    ],
)
def test_percentage_measures(api, measure, section):
    frame = ipc.ipc(measure=measure)
    assert list(frame.columns) == ["general", *DIVISIONS]
    assert (frame == 0.5).all().all()
    assert frame.attrs["measure"] == measure
    assert frame.attrs["units"].startswith("porcentaje")
    assert "unidad=Porcentaje" in frame.attrs["url"]


def test_unknown_measure():
    with pytest.raises(ValueError, match="Medida desconocida"):
        ipc.ipc("yoy")


def test_select_requires_general_index(helpers):
    grid = {
        "columns": ["Ene 2026"],
        "rows": [{"tipo": "Series", "label": "Transporte", "nivel": 1, "values": {"Ene 2026": 1}}],
    }
    table = bcedata.parse_grid(grid, "Mensual")
    with pytest.raises(ParseError, match="índice general"):
        ipc._select(table, None)


def test_select_keeps_unknown_divisions_with_snake_case_names():
    grid = {
        "columns": ["Ene 2026"],
        "rows": [
            {
                "tipo": "Series",
                "label": "Índice General - IPC",
                "nivel": 1,
                "values": {"Ene 2026": 1},
            },
            {
                "tipo": "Series",
                "label": "Nueva división (p)",
                "nivel": 1,
                "values": {"Ene 2026": 2},
            },
        ],
    }
    frame = ipc._select(bcedata.parse_grid(grid, "Mensual"), None)
    assert list(frame.columns) == ["general", "nueva_division"]

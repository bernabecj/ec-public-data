"""Interest rates assembled from BCEData tables 1.10.1, 1.10.2 and 1.10.2a."""

from __future__ import annotations

import httpx
import pandas as pd
import pytest

from ecuadata.bce import _tasas as tasas
from ecuadata.exceptions import ParseError

API = "bce/bcedata/"


def reference_grid(request: httpx.Request) -> httpx.Response:
    """Monthly grid of table 49 (not recorded yet; shaped after the bundle's rows)."""
    columns = ["Sep 2026", "Oct 2026"]
    rows = [{"tipo": "Cabeceras", "label": "Vigencia Mensual", "nivel": 1, "values": []}]
    for label, value in [
        ("Pasiva", 4.99),
        ("Activa", 7.03),
        ("Legal", 7.03),
        ("Máxima convencional", 7.72),
    ]:
        rows.append(
            {
                "tipo": "Series",
                "label": label,
                "nivel": 2,
                "token": "t",
                "values": dict.fromkeys(columns, value),
            }
        )
    return httpx.Response(200, json={"columns": columns, "rows": rows})


@pytest.fixture
def api(serve_fixtures):
    return serve_fixtures(
        {
            "/bundle/49": f"{API}bundle_49.json",
            "/bundle/50": f"{API}bundle_50.json",
            "/bundle/51": f"{API}bundle_51.json",
            "id_grupo=49&frecuencia=Mensual": reference_grid,
            "id_grupo=50": f"{API}grid_50.json",
            "id_grupo=51": f"{API}grid_51.json",
        }
    )


def test_reference_rates(api):
    frame = tasas.tasas_interes()
    assert list(frame.columns) == ["pasiva", "activa", "legal", "maxima_convencional"]
    assert frame.index.freqstr == "M"
    assert frame.loc["2026-10", "activa"] == 7.03
    assert frame.attrs["source"] == "BCE"
    assert frame.attrs["dataset"] == "tasas_interes"
    assert frame.attrs["kind"] == "reference"
    assert frame.attrs["units"] == "porcentaje anual"
    assert frame.attrs["tables"] == ["1.10.1"]
    assert frame.attrs["original_columns"]["maxima_convencional"] == "Máxima convencional"
    assert "frecuencia=Mensual" in frame.attrs["url"]


def test_reference_requires_activa_and_pasiva(serve_fixtures):
    def grid(request):
        return httpx.Response(
            200,
            json={
                "columns": ["Sep 2026"],
                "rows": [
                    {"tipo": "Series", "label": "Básica", "nivel": 1, "values": {"Sep 2026": 0.2}}
                ],
            },
        )

    serve_fixtures({"/bundle/49": f"{API}bundle_49.json", "id_grupo=49": grid})
    with pytest.raises(ParseError, match=r"le falta \['activa', 'pasiva'\]"):
        tasas.tasas_interes()


def test_segments_are_stitched_across_the_2021_break(api):
    frame = tasas.tasas_interes("segments")
    assert frame.index.freqstr == "M"
    assert frame.index[0] == pd.Period("2015-08", freq="M")
    assert frame.index[-1] == pd.Period("2026-10", freq="M")
    assert frame.index.is_unique and frame.index.is_monotonic_increasing
    assert len(frame) == 69 + 66
    # Section prefixes are gone; reference and maximum rates sit side by side.
    assert {
        "productivo_corporativo",
        "maxima_productivo_corporativo",
        "consumo",
        "maxima_consumo",
    } <= set(frame.columns)
    assert frame.loc["2021-04", "productivo_corporativo"] == 8.35  # last month of the old table
    assert frame.loc["2026-10", "maxima_productivo_corporativo"] == 7.89
    # Segments that existed only in one table are NaN in the other period.
    assert frame.loc["2026-10", "consumo_ordinario"] != frame.loc["2026-10", "consumo_ordinario"]
    assert frame.loc["2021-04", "consumo"] != frame.loc["2021-04", "consumo"]
    assert frame.attrs["tables"] == ["1.10.2", "1.10.2a"]
    assert len(frame.attrs["urls"]) == 2
    assert frame.attrs["original_columns"]["maxima_consumo"] == "Máxima Consumo"


def test_segments_slice(api):
    frame = tasas.tasas_interes("segments", start="2021-03", end="2021-06")
    assert [str(p) for p in frame.index] == ["2021-03", "2021-04", "2021-05", "2021-06"]


def test_unknown_kind():
    with pytest.raises(ValueError, match="Tipo desconocido"):
        tasas.tasas_interes("weekly")


def test_segment_prefix_regex():
    sub = tasas._SEGMENT_PREFIX.sub
    assert sub("", "segmento_productivo_productivo_corporativo") == "productivo_corporativo"
    assert (
        sub("", "segmento_productivo_maxima_productivo_corporativo")
        == "maxima_productivo_corporativo"
    )
    assert sub("", "segmento_vivienda_vivienda_de_interes_publico") == "vivienda_de_interes_publico"
    assert sub("", "segmento_microcredito_microcredito_minorista") == "microcredito_minorista"
    assert sub("", "consumo") == "consumo"

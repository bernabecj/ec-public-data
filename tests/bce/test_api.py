"""End to end: public BCE functions -> fetch -> cache -> parse, over a fixture-backed server."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

import ecuadata as ec
from ecuadata import cache
from ecuadata.bce import fetch
from ecuadata.config import config
from ecuadata.exceptions import OfflineError, SourceUnavailableError

TOU = "bce/pib_trimestral/"
REMESAS = "bce/remesas/Flujo_de_remesas_de_trabajadores.xlsx"


@pytest.fixture
def bce_server(serve_fixtures):
    return serve_fixtures(
        {
            "tou_136_202602.xlsx": f"{TOU}tou_136_202602.xlsx",
            "tou_135_202601.xlsx": f"{TOU}tou_135_202601.xlsx",
            "Flujo_de_remesas_de_trabajadores.xlsx": REMESAS,
        }
    )


def test_pib_trimestral_latest_walks_back_from_today(bce_server, monkeypatch):
    monkeypatch.setattr(
        fetch, "date", type("D", (), {"today": staticmethod(lambda: date(2026, 10, 16))})
    )
    frame = ec.bce.pib_trimestral()
    names = [str(r.url).rsplit("/", 1)[-1] for r in bce_server]
    assert names == ["tou_137_202603.xlsx", "tou_136_202602.xlsx"]  # 2026Q3 not yet published
    assert frame.index[-1] == pd.Period("2026Q2", freq="Q")
    assert frame.attrs["source"] == "BCE"
    assert frame.attrs["dataset"] == "pib_trimestral"
    assert frame.attrs["release"] == "2026Q2"
    assert frame.attrs["bulletin"] == 136
    assert frame.attrs["url"] == fetch.url_for("tou", "2026Q2")
    assert frame.attrs["units"] == "miles de USD, precios encadenados de 2018"
    assert frame.attrs["sheet"] == "Dem_Cad_ajus"
    assert "retrieved_at" in frame.attrs


def test_pib_trimestral_specific_release_and_measure(bce_server):
    frame = ec.bce.pib_trimestral(measure="growth_yoy", release="2026Q1")
    assert frame.index[-1] == pd.Period("2026Q1", freq="Q")
    assert frame.attrs["release"] == "2026Q1" and frame.attrs["bulletin"] == 135
    assert frame.attrs["units"].startswith("porcentaje")


def test_pib_trimestral_uses_cache_and_offline_mode(bce_server, monkeypatch):
    ec.bce.pib_trimestral(release="2026Q2")
    ec.bce.pib_trimestral(release="2026Q2", measure="current_prices", seasonally_adjusted=False)
    assert len(bce_server) == 1  # same workbook, two tables
    monkeypatch.setattr(config, "offline", True)
    frame = ec.bce.pib_trimestral(release="2026Q2", measure="volume_index")
    assert frame.attrs["sheet"] == "Dem_Ivol_ajus"
    with pytest.raises(OfflineError):
        ec.bce.pib_trimestral(release="2025Q4")


def test_pib_trimestral_validates_before_downloading(bce_server):
    with pytest.raises(ValueError, match="Medida desconocida"):
        ec.bce.pib_trimestral(measure="gdp")
    with pytest.raises(ValueError, match="solo con ajuste estacional"):
        ec.bce.pib_trimestral(measure="growth_qoq", seasonally_adjusted=False)
    assert bce_server == []


def test_pib_trimestral_unpublished_release(bce_server):
    with pytest.raises(SourceUnavailableError, match="no ha publicado la entrega 2027Q1"):
        ec.bce.pib_trimestral(release="2027Q1")


def test_remesas_end_to_end(bce_server, monkeypatch):
    frame = ec.bce.remesas()
    assert list(frame.columns) == ["monto_usd", "numero_giros"]
    assert frame.index[-1] == pd.Period("2026Q2", freq="Q")
    assert frame.attrs["source"] == "BCE" and frame.attrs["dataset"] == "remesas"
    assert frame.attrs["flow"] == "received" and frame.attrs["frequency"] == "Q"
    assert frame.attrs["sheet"] == "RR_t"
    assert frame.attrs["url"].endswith("Flujo_de_remesas_de_trabajadores.xlsx")

    by_country = ec.bce.remesas(flow="sent", frequency="A", by="country", count=True)
    assert by_country.attrs["units"] == "número de giros"
    assert by_country.attrs["sheet"] == "REpaisg_a"
    assert "colombia" in by_country.columns
    assert len(bce_server) == 1  # one workbook serves every table

    monkeypatch.setattr(config, "offline", True)
    assert ec.bce.remesas("sent", "A").attrs["sheet"] == "RE_a"


def test_remesas_validates_before_downloading(bce_server):
    with pytest.raises(ValueError):
        ec.bce.remesas(by="city")
    assert bce_server == []


def test_cached_quarters_ignores_json_data_files():
    cache.store("bce", "tou_136_202602.xlsx", b"PK\x03\x04", "u")
    cache.store("bce", "bcedata_tree.json", b"[]", "u")
    assert fetch._cached_quarters("tou") == [pd.Period("2026Q2", freq="Q")]

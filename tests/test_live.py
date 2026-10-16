"""Live tests: hit the real BCE and INEC sources. Opt in with ``pytest -m live``.

They download into the isolated per-test cache, with the library's normal throttling, and
check the schema each public function promises. A failure here most likely means a publisher
changed a file or an API; record fresh fixtures with ``scripts/record_fixtures.py`` and fix
the parser.
"""

from __future__ import annotations

import pandas as pd
import pytest

import ecuadata as ec
from ecuadata import http
from ecuadata.bce import bcedata

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def polite(monkeypatch):
    """Restore the real throttle and back-off that the offline suite disables."""
    monkeypatch.setattr(http, "MIN_INTERVAL", 2.0)
    monkeypatch.setattr(http, "BACKOFF", 5.0)


def check_series_frame(frame: pd.DataFrame, freq: str, required: set[str], min_rows: int) -> None:
    assert isinstance(frame.index, pd.PeriodIndex)
    assert frame.index.freqstr.startswith(freq)
    assert frame.index.is_unique and frame.index.is_monotonic_increasing
    assert len(frame) >= min_rows
    assert required <= set(frame.columns)
    assert set(frame.dtypes.astype(str)) == {"float64"}
    for key in ("source", "dataset", "url", "retrieved_at", "units", "original_columns"):
        assert key in frame.attrs, key
    # The latest period should not be absurdly old: publishers lag a few months at most.
    latest = frame.index[-1].to_timestamp(how="end")
    assert latest >= pd.Timestamp.now() - pd.DateOffset(months=18), latest


def test_pib_trimestral_live():
    frame = ec.bce.pib_trimestral()
    check_series_frame(frame, "Q", {"pib", "consumo_hogares", "fbkf", "exportaciones"}, 100)
    assert frame.index[0] == pd.Period("2000Q1", freq="Q")
    growth = ec.bce.pib_trimestral(measure="growth_yoy")  # from the cached workbook
    assert growth["pib"].dropna().abs().max() < 50


def test_remesas_live():
    frame = ec.bce.remesas()
    check_series_frame(frame, "Q", {"monto_usd", "numero_giros"}, 130)
    assert frame.index[0] == pd.Period("1993Q1", freq="Q")
    by_country = ec.bce.remesas(by="country", frequency="A")
    assert {"estados_unidos_de_america", "espana", "total"} <= set(by_country.columns)
    diff = (by_country.drop(columns="total").sum(axis=1) - by_country["total"]).abs().max()
    assert diff < 1e-6 * by_country["total"].abs().max()


def test_tasas_interes_live():
    reference = ec.bce.tasas_interes()
    check_series_frame(reference, "M", {"activa", "pasiva"}, 100)
    assert reference["activa"].dropna().between(0, 30).all()
    segments = ec.bce.tasas_interes("segments", start="2024-01")
    check_series_frame(
        segments, "M", {"productivo_corporativo", "maxima_productivo_corporativo"}, 12
    )


def test_ipc_live():
    index = ec.inec.ipc()
    check_series_frame(index, "M", {"general", "transporte", "salud"}, 240)
    assert index.attrs["source"] == "INEC"
    assert index.index[0] == pd.Period("2006-01", freq="M")
    annual = ec.inec.ipc(measure="annual_change", start="2024-01")
    check_series_frame(annual, "M", {"general"}, 12)
    assert annual["general"].dropna().abs().max() < 30


def test_bcedata_index_still_has_the_tables_we_use():
    nodes = {n["id_grupo"] for n in bcedata.tree() if n["id_grupo"] is not None}
    assert set(bcedata.TABLES.values()) <= nodes

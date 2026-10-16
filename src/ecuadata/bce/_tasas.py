"""Interest rates published by the Banco Central del Ecuador, read from BCEData.

Two kinds of tables:

* **Reference rates** (table 1.10.1): the rates in force each period: básica, pasiva
  referencial, activa referencial, legal and máxima convencional. Published monthly since
  2015 (weekly for the básica).
* **Rates by credit segment** (tables 1.10.2 and 1.10.2a): for every segment of the loan
  portfolio (productivo corporativo, consumo, microcrédito minorista, vivienda de interés
  público ...), the effective reference rate and the legal maximum rate. The segmentation
  changed in May 2021, so BCE keeps two tables; they are stitched into one monthly frame.
"""

from __future__ import annotations

import re

import pandas as pd

from ecuadata.bce import bcedata
from ecuadata.exceptions import ParseError

SOURCE = "BCE"
KINDS = {
    "reference": "Tasas referenciales vigentes: pasiva, activa, legal y máxima convencional",
    "segments": "Tasas activas efectivas referenciales y máximas por segmento de crédito",
}
REFERENCE_TABLE = bcedata.TABLES["tasas_referenciales"]
SEGMENT_TABLES = (
    bcedata.TABLES["tasas_segmentos_2015_2021"],
    bcedata.TABLES["tasas_segmentos"],
)
REQUIRED_REFERENCE = ("activa", "pasiva")
_SEGMENT_PREFIX = re.compile(r"^segmento_[a-z_]+?_(?=(maxima_)?[a-z])")


def tasas_interes(
    kind: str = "reference",
    start: str | pd.Period | None = None,
    end: str | pd.Period | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    """Tasas de interés del Ecuador, mensuales, en porcentaje anual.

    Args:
        kind: ``"reference"`` (por defecto) para las tasas referenciales vigentes
            (``pasiva``, ``activa``, ``legal``, ``maxima_convencional``), o ``"segments"``
            para la tasa activa efectiva referencial y la tasa máxima de cada segmento de
            crédito (``productivo_corporativo``, ``maxima_productivo_corporativo``,
            ``consumo``, ``microcredito_minorista`` ...). Los segmentos que dejaron de existir
            quedan en ``NaN`` desde que se discontinuaron.
        start: Primer mes a devolver, p. ej. ``"2020-01"``.
        end: Último mes a devolver, p. ej. ``"2025-12"``.
        refresh: Volver a descargar aunque haya una copia vigente en el caché.

    Returns:
        DataFrame con ``PeriodIndex`` mensual llamado ``period`` y columnas float en
        porcentaje. ``df.attrs`` contiene ``source``, ``dataset``, ``kind``, ``units``, ``url``
        (o ``urls`` cuando se unen los dos cuadros por segmento), ``retrieved_at`` y
        ``original_columns``.

    Raises:
        ValueError: ``kind`` desconocido.
        SourceUnavailableError / OfflineError / ParseError.

    Example:
        >>> tasas = ec.bce.tasas_interes()
        >>> tasas.loc["2025-01":, ["activa", "pasiva"]]
        >>> seg = ec.bce.tasas_interes("segments", start="2024-01")
        >>> seg[["consumo", "maxima_consumo"]]
    """
    if kind not in KINDS:
        raise ValueError(f"Tipo desconocido {kind!r}. Elija uno de: {', '.join(KINDS)}.")
    frame = _reference(refresh) if kind == "reference" else _segments(refresh)
    frame = bcedata.slice_periods(frame, start, end)
    frame.attrs.update(
        {
            "source": SOURCE,
            "dataset": "tasas_interes",
            "kind": kind,
            "description": KINDS[kind],
            "units": "porcentaje anual",
            "portal_url": bcedata.PORTAL_URL,
        }
    )
    return frame


def _reference(refresh: bool) -> pd.DataFrame:
    table = bcedata.table(REFERENCE_TABLE, frecuencia="Mensual", refresh=refresh)
    # Rows may sit under "Vigencia Mensual"/"Vigencia Semanal" headers; drop that prefix.
    renamed = {c: re.sub(r"^vigencia_(mensual|semanal)_", "", c) for c in table.columns}
    frame = table.rename(columns=renamed)
    missing = [c for c in REQUIRED_REFERENCE if c not in frame.columns]
    if missing:
        raise ParseError(
            f"Al cuadro de tasas referenciales de BCEData le falta {missing}; las columnas "
            f"fueron {list(frame.columns)}. Por favor abra un issue."
        )
    frame.attrs = {
        "original_columns": {renamed[c]: table.attrs["original_columns"][c] for c in table.columns},
        "url": table.attrs["url"],
        "retrieved_at": table.attrs["retrieved_at"],
        "tables": [table.attrs["cod_grupo"]],
    }
    return frame


def _segments(refresh: bool) -> pd.DataFrame:
    parts = [bcedata.table(t, frecuencia="Mensual", refresh=refresh) for t in SEGMENT_TABLES]
    frames, original, urls, codes = [], {}, [], []
    for table in parts:
        renamed = {c: _SEGMENT_PREFIX.sub("", c) for c in table.columns}
        if len(set(renamed.values())) != len(renamed):
            # Two segments share a label: keep the section prefix rather than merge them.
            renamed = {c: c for c in table.columns}
        frames.append(table.rename(columns=renamed))
        original.update({renamed[c]: table.attrs["original_columns"][c] for c in table.columns})
        urls.append(table.attrs["url"])
        codes.append(table.attrs["cod_grupo"])
    frame = pd.concat(frames, axis=0, sort=False)
    if not frame.index.is_unique:
        # The two tables are meant to be consecutive; prefer the newer table on overlap.
        frame = frame[~frame.index.duplicated(keep="last")]
    frame = frame.sort_index()
    frame.attrs = {
        "original_columns": original,
        "urls": urls,
        "url": urls[-1],
        "retrieved_at": max(t.attrs["retrieved_at"] for t in parts),
        "tables": codes,
    }
    return frame

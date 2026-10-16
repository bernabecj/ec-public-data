"""Client for BCEData, the Banco Central del Ecuador statistics portal.

BCEData (https://contenido.bce.fin.ec/bcedata/) is a WordPress plugin with a public REST API.
Reads need no authentication::

    GET /wp-json/bcedata/v1/tree                 index of tables ("cuadros")
    GET /wp-json/bcedata/v1/bundle/<id_grupo>    one table: frequencies, units, date range, rows
    GET /wp-json/bcedata/v1/grid?id_grupo=&frecuencia=&unidad=&desde=YYYY-MM&hasta=YYYY-MM
                                                 the numbers: columns are periods, rows are series

A grid looks like::

    {"columns": ["Ene 2006", "Feb 2006", ...],
     "rows": [{"tipo": "Cabeceras", "label": "NACIONAL", "nivel": 1, "values": []},
              {"tipo": "Series", "label": "DESEMPLEO", "nivel": 2, "token": "...",
               "values": {"Ene 2006": 7.9, ...}}, ...]}

``Cabeceras`` rows are section headers; the ``Series`` rows below them belong to that section.
Period labels depend on the frequency: ``"Ene 2006"`` (Mensual), ``"2016-I"`` (Trimestral),
``1966`` (Anual), ``"Ene 2015 (05 al 11)"`` (Semanal).

The raw JSON responses are cached like any other download, so a parser change never needs a
new request, and ``config.offline`` works.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import pandas as pd

from ecuadata import cache, http
from ecuadata._parsing import (
    parse_month,
    parse_quarter,
    parse_week,
    parse_year,
    snake_case,
    to_number,
)
from ecuadata.config import config
from ecuadata.exceptions import OfflineError, ParseError, SourceUnavailableError

PROVIDER = "bce"
BASE_URL = "https://contenido.bce.fin.ec/wp-json/bcedata/v1"
PORTAL_URL = "https://contenido.bce.fin.ec/bcedata/"

FREQUENCIES = {
    "Semanal": ("W-SUN", parse_week),
    "Mensual": ("M", parse_month),
    "Trimestral": ("Q", parse_quarter),
    "Anual": ("Y", parse_year),
}

# Tables used by the public functions, by id_grupo. The tree has ~80 more.
TABLES = {
    "ipc": 63,  # 4.2.1 Índice de Precios al Consumidor (INEC data)
    "tasas_referenciales": 49,  # 1.10.1 Tasas de interés referenciales vigentes
    "tasas_segmentos_2015_2021": 50,  # 1.10.2 Tasas activas efectivas y máximas, Aug 2015-Apr 2021
    "tasas_segmentos": 51,  # 1.10.2a Tasas activas efectivas y máximas, May 2021 onwards
    "balanza_pagos": 2,  # 3.2.1 Balanza de pagos normalizada
    "mercado_laboral": 68,  # 4.2.5 Indicadores del mercado laboral (INEC ENEMDU data)
    "pib_gasto_anual": 90,  # 4.3.1 PIB: enfoque del gasto
}


@dataclass(frozen=True)
class Response:
    """A JSON document from the API, with provenance."""

    data: Any
    url: str
    retrieved_at: datetime


# --------------------------------------------------------------------------------------------
# Fetch
# --------------------------------------------------------------------------------------------


def _safe_filename(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")


def get_json(path: str, params: dict[str, Any] | None = None, refresh: bool = False) -> Response:
    """GET ``path`` en el API, usando el caché cuando la copia es más nueva que ``cache_ttl``.

    Raises:
        OfflineError: modo sin conexión activo y el documento no está en el caché.
        SourceUnavailableError: el API no responde o devolvió un error.
        ParseError: la respuesta no es JSON.
    """
    query = urlencode({k: v for k, v in (params or {}).items() if v is not None})
    url = f"{BASE_URL}/{path.strip('/')}" + (f"?{query}" if query else "")
    filename = "bcedata_" + _safe_filename(path + ("_" + query if query else "")) + ".json"

    if config.offline:
        cached = cache.load(PROVIDER, filename)
        if cached is None:
            raise OfflineError(f"El documento de BCEData {url} no está en el caché.")
        return Response(_decode(cached.content, url), cached.url, cached.retrieved_at)

    if not refresh:
        cached = cache.load(PROVIDER, filename, max_age=config.cache_ttl)
        if cached is not None:
            return Response(_decode(cached.content, url), cached.url, cached.retrieved_at)

    response = http.get(url)
    if response.status_code != 200:
        detail = _error_detail(response.content)
        raise SourceUnavailableError(
            f"BCEData respondió HTTP {response.status_code} para {url}"
            + (f": {detail}" if detail else "")
            + ". Puede que el API haya cambiado; por favor abra un issue."
        )
    data = _decode(response.content, url)
    stored = cache.store(PROVIDER, filename, response.content, url)
    return Response(data, url, stored.retrieved_at)


def _error_detail(content: bytes) -> str:
    try:
        body = json.loads(content)
    except ValueError:
        return ""
    return str(body.get("message") or body.get("error") or "") if isinstance(body, dict) else ""


def _decode(content: bytes, url: str) -> Any:
    try:
        return json.loads(content)
    except ValueError as exc:
        raise ParseError(f"BCEData no devolvió JSON para {url}: {exc}") from exc


def tree(refresh: bool = False) -> list[dict[str, Any]]:
    """El índice de cuadros, como lista plana de nodos (``id_grupo`` es None en los títulos)."""
    data = get_json("tree", refresh=refresh).data
    if not isinstance(data, list):
        raise ParseError("BCEData /tree no devolvió una lista.")
    return data


def bundle(id_grupo: int, refresh: bool = False) -> dict[str, Any]:
    """Metadatos de un cuadro: ``context``, ``frecuencias``, ``unidades``, ``range_by_freq``."""
    data = get_json(f"bundle/{id_grupo}", refresh=refresh).data
    if not isinstance(data, dict) or "context" not in data:
        raise ParseError(f"BCEData bundle/{id_grupo} tiene una forma inesperada.")
    return data


def grid(
    id_grupo: int,
    frecuencia: str,
    unidad: str,
    desde: str,
    hasta: str,
    refresh: bool = False,
) -> Response:
    """JSON crudo del grid de un cuadro. El API exige los cinco parámetros."""
    params = {
        "id_grupo": id_grupo,
        "frecuencia": frecuencia,
        "unidad": unidad,
        "desde": desde,
        "hasta": hasta,
    }
    return get_json("grid", params, refresh=refresh)


# --------------------------------------------------------------------------------------------
# Parse
# --------------------------------------------------------------------------------------------


def parse_grid(data: dict[str, Any], frecuencia: str) -> pd.DataFrame:
    """Convierte un grid en un DataFrame: una fila por período, una columna por serie.

    Los nombres de columna son la ruta de la fila en la jerarquía del cuadro, en
    ``snake_case`` (``DESEMPLEO`` bajo el título ``NACIONAL`` pasa a ser ``nacional_desempleo``;
    una serie de primer nivel conserva su nombre). ``attrs`` recibe ``original_columns``
    (columna -> etiqueta), ``sections`` (columna -> ruta del padre o None) y ``tokens``
    (columna -> token de la serie en BCEData).

    Raises:
        ParseError: frecuencia desconocida, etiquetas de período ilegibles o series repetidas.
    """
    if frecuencia not in FREQUENCIES:
        raise ParseError(
            f"Frecuencia de BCEData desconocida {frecuencia!r}; se esperaba {list(FREQUENCIES)}."
        )
    freq, parse_period = FREQUENCIES[frecuencia]
    columns = data.get("columns")
    rows = data.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise ParseError("El grid de BCEData no tiene 'columns' o 'rows'.")
    if not columns:
        raise ParseError("El grid de BCEData no tiene períodos ('columns' vacío).")

    try:
        index = pd.PeriodIndex([parse_period(c) for c in columns], freq=freq, name="period")
    except ValueError as exc:
        raise ParseError(
            f"Etiqueta de período {frecuencia} no reconocida en el grid de BCEData: {exc}"
        ) from exc

    series: dict[str, list[float]] = {}
    original: dict[str, str] = {}
    sections: dict[str, str | None] = {}
    tokens: dict[str, str | None] = {}
    # Rows form a tree through ``nivel``: header rows ("Cabeceras") and higher-level series
    # are the parents of the rows below them. Column names are the full path, so
    # "Exportaciones" under BIENES and under SERVICIOS stay distinct.
    path: list[str] = []
    for row in rows:
        label = str(row.get("label", "")).strip()
        tipo = row.get("tipo")
        if tipo not in ("Cabeceras", "Series"):
            continue
        level = int(row.get("nivel") or 1)
        del path[level - 1 :]
        path.append(snake_case(label))
        if tipo == "Cabeceras":
            continue
        values = row.get("values") or {}
        if not isinstance(values, dict):
            raise ParseError(f"La serie {label!r} tiene valores de tipo {type(values).__name__}.")
        name = "_".join(p for p in path if p)
        if name in series:
            raise ParseError(f"Serie repetida {name!r} en el grid de BCEData.")
        try:
            series[name] = [to_number(values.get(str(c), values.get(c))) for c in columns]
        except (TypeError, ValueError) as exc:
            raise ParseError(f"Valor no numérico en la serie {label!r}: {exc}") from exc
        original[name] = label
        sections[name] = " / ".join(path[:-1]) or None
        tokens[name] = row.get("token")
    if not series:
        raise ParseError("El grid de BCEData no contiene filas de tipo 'Series'.")

    frame = pd.DataFrame(series, index=index, dtype="float64")
    dropped: list[str] = []
    if not frame.index.is_unique:
        # BCE occasionally publishes overlapping weeks ("May 2024 (27 al 02 jun)" and
        # "Jun 2024 (01 al 07)"). Keep the first label for each period and say so.
        duplicated = frame.index.duplicated(keep="first")
        dropped = [str(c) for c, d in zip(columns, duplicated, strict=True) if d]
        frame = frame.loc[~duplicated]
    frame = frame.sort_index()
    frame.attrs.update({"original_columns": original, "sections": sections, "tokens": tokens})
    if dropped:
        frame.attrs["dropped_duplicate_periods"] = dropped
    return frame


# --------------------------------------------------------------------------------------------
# High level
# --------------------------------------------------------------------------------------------


def _ym(value: str | pd.Period | None, default: str) -> str:
    if value is None:
        return default
    return str(parse_month(value)) if not isinstance(value, pd.Period) else str(value.asfreq("M"))


def table(
    id_grupo: int,
    frecuencia: str | None = None,
    unidad: str | None = None,
    start: str | pd.Period | None = None,
    end: str | pd.Period | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    """Descarga un cuadro de BCEData como DataFrame con ``PeriodIndex``.

    ``frecuencia`` y ``unidad`` toman por defecto los valores propios del cuadro;
    ``start``/``end`` son meses (``"2020-01"``) y por defecto cubren todo el rango publicado.
    ``attrs`` contiene ``id_grupo``, ``cod_grupo``, ``nom_grupo``, ``frequency``, ``units``,
    ``url``, ``retrieved_at`` y lo que añade :func:`parse_grid`.

    Example:
        >>> from ecuadata.bce import bcedata
        >>> m2 = bcedata.table(35)                      # 1.1.1 Oferta monetaria y liquidez
        >>> bcedata.tree()                              # índice completo de cuadros
    """
    meta = bundle(id_grupo, refresh=refresh)
    frequencies = meta.get("frecuencias") or []
    if not frequencies:
        raise ParseError(f"El cuadro {id_grupo} de BCEData no ofrece ninguna frecuencia.")
    frecuencia = frecuencia or meta.get("default_frequency") or frequencies[0]
    if frecuencia not in frequencies:
        raise ValueError(
            f"El cuadro {id_grupo} no se publica con frecuencia {frecuencia!r}; "
            f"elija {frequencies}."
        )
    units = (meta.get("unidades") or {}).get(frecuencia) or []
    unidad = unidad or (units[0] if units else "")
    if units and unidad not in units:
        raise ValueError(
            f"El cuadro {id_grupo} ({frecuencia}) no tiene la unidad {unidad!r}; elija {units}."
        )
    rng = (meta.get("range_by_freq") or {}).get(frecuencia) or meta.get("range") or {}
    desde = _ym(start, rng.get("minYm", "1900-01"))
    hasta = _ym(end, rng.get("maxYm", pd.Period(datetime.now(), freq="M").strftime("%Y-%m")))

    response = grid(id_grupo, frecuencia, unidad, desde, hasta, refresh=refresh)
    frame = parse_grid(response.data, frecuencia)
    context = meta.get("context") or {}
    frame.attrs.update(
        {
            "id_grupo": id_grupo,
            "cod_grupo": context.get("cod_grupo"),
            "nom_grupo": context.get("nom_alias_grupo") or context.get("nom_grupo"),
            "frequency": frecuencia,
            "units": unidad,
            "units_note": context.get("unidad_grupo"),
            "url": response.url,
            "portal_url": PORTAL_URL,
            "retrieved_at": response.retrieved_at.isoformat(),
        }
    )
    return frame


def slice_periods(
    frame: pd.DataFrame, start: str | pd.Period | None, end: str | pd.Period | None
) -> pd.DataFrame:
    """Recorta un DataFrame con PeriodIndex a ``[start, end]`` dados como texto (``"2020-01"``)."""
    if start is None and end is None:
        return frame
    freq = frame.index.freq
    lo = pd.Period(start, freq=freq) if start is not None else None
    hi = pd.Period(end, freq=freq) if end is not None else None
    mask = pd.Series(True, index=frame.index)
    if lo is not None:
        mask &= frame.index >= lo
    if hi is not None:
        mask &= frame.index <= hi
    return frame.loc[mask.to_numpy()]

"""INEC consumer price index (Índice de Precios al Consumidor, IPC).

INEC's own download page has been broken for months (its embedded frame returns 404), so the
series is read from the Banco Central del Ecuador data portal, BCEData, which republishes
INEC's monthly IPC (table 4.2.1) with the general index, the twelve COICOP divisions and the
official monthly, annual and year-to-date changes. The numbers are INEC's; only the delivery
channel is BCE.
"""

from __future__ import annotations

import pandas as pd

from ecuadata.bce import bcedata
from ecuadata.exceptions import ParseError

SOURCE = "INEC"
VIA = "BCEData del BCE, cuadro 4.2.1 Índice de Precios al Consumidor"
TABLE = bcedata.TABLES["ipc"]

# BCEData unit and, for the percentage tables, the section header that holds each measure.
MEASURES = {
    "index": ("Indice", None, "índice (ver attrs['base'])"),
    "monthly_change": (
        "Porcentaje",
        "variacion_mensual",
        "porcentaje, variación respecto al mes anterior",
    ),
    "annual_change": (
        "Porcentaje",
        "variacion_anual",
        "porcentaje, variación respecto al mismo mes del año anterior",
    ),
    "ytd_change": (
        "Porcentaje",
        "variacion_acumulada",
        "porcentaje, variación acumulada desde diciembre del año anterior",
    ),
}

# Short, stable names for the general index and the COICOP divisions.
COLUMNS = {
    "indice_general_ipc": "general",
    "alimentos_y_bebidas_no_alcoholicas": "alimentos_bebidas_no_alcoholicas",
    "bebidas_alcoholicas_tabaco_y_estupefacientes": "bebidas_alcoholicas_tabaco",
    "prendas_de_vestir_y_calzado": "prendas_vestir_calzado",
    "vivienda_agua_electricidad_gas_y_otros_combustibles": "vivienda_servicios_basicos",
    "muebles_y_articulos_para_el_hogar_y_para_conservacion_ordinaria_del_hogar": (
        "muebles_articulos_hogar"
    ),
    "salud": "salud",
    "transporte": "transporte",
    "informacion_y_comunicacion": "informacion_comunicacion",
    "recreacion_deporte_y_cultura": "recreacion_cultura",
    "servicios_educativos": "educacion",
    "servicios_de_restaurantes_y_alojamiento": "restaurantes_alojamiento",
    "seguros_y_servicios_financieros": "seguros_servicios_financieros",
    "cuidado_personal_revision_social_y_bienes_y_servicios_diversos": "bienes_servicios_diversos",
}


def ipc(
    measure: str = "index",
    start: str | pd.Period | None = None,
    end: str | pd.Period | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    """Índice de precios al consumidor del Ecuador, mensual, por división COICOP.

    Los datos son del INEC. Como la página de descargas del INEC lleva meses rota, la serie
    se lee del portal BCEData del Banco Central, que republica el IPC oficial del INEC
    (ver ``attrs["via"]``).

    Args:
        measure: ``"index"`` (por defecto), ``"monthly_change"`` (variación mensual),
            ``"annual_change"`` (variación anual, la inflación) o ``"ytd_change"``
            (variación acumulada desde diciembre del año anterior).
        start: Primer mes a devolver, p. ej. ``"2020-01"``. Por defecto, el primero disponible.
        end: Último mes a devolver, p. ej. ``"2025-12"``. Por defecto, el último publicado.
        refresh: Volver a descargar aunque haya una copia vigente en el caché.

    Returns:
        DataFrame con ``PeriodIndex`` mensual llamado ``period`` y una columna float por
        serie: ``general`` más las doce divisiones (``alimentos_bebidas_no_alcoholicas``,
        ``transporte``, ``salud`` ...). ``df.attrs`` contiene ``source`` ("INEC"), ``via``,
        ``dataset``, ``measure``, ``units``, ``base`` (año base del índice), ``url``,
        ``retrieved_at`` y ``original_columns``.

    Raises:
        ValueError: ``measure`` desconocida.
        SourceUnavailableError / OfflineError / ParseError: ver :mod:`ecuadata.bce.bcedata`.

    Example:
        >>> ipc = ec.inec.ipc(start="2024-01")
        >>> ipc["general"].tail(3)
        >>> inflacion = ec.inec.ipc(measure="annual_change")["general"]
    """
    if measure not in MEASURES:
        raise ValueError(f"Medida desconocida {measure!r}. Elija una de: {', '.join(MEASURES)}.")
    unit, section, units_label = MEASURES[measure]

    # The full range is downloaded once and cached; start/end are applied locally so that
    # different slices share one download.
    table = bcedata.table(TABLE, frecuencia="Mensual", unidad=unit, refresh=refresh)
    frame = _select(table, section)
    frame = bcedata.slice_periods(frame, start, end)
    frame.attrs.update(
        {
            "source": SOURCE,
            "via": VIA,
            "dataset": "ipc",
            "measure": measure,
            "units": units_label,
            "base": table.attrs.get("units_note"),
            "url": table.attrs["url"],
            "portal_url": table.attrs["portal_url"],
            "retrieved_at": table.attrs["retrieved_at"],
        }
    )
    return frame


def _select(table: pd.DataFrame, section: str | None) -> pd.DataFrame:
    """Keep the columns of one section (or the unsectioned index columns) and rename them."""
    original = table.attrs["original_columns"]
    sections = table.attrs["sections"]
    keep: dict[str, str] = {}
    for column in table.columns:
        parent = sections.get(column) or ""
        if section is None and parent:
            continue
        if section is not None and not parent.startswith(section):
            continue
        key = column[len(parent) + 1 :] if parent else column
        keep[column] = COLUMNS.get(key, key)
    if "general" not in keep.values():
        raise ParseError(
            "El cuadro del IPC en BCEData ya no tiene la fila del índice general"
            + (f" bajo la sección {section!r}" if section else "")
            + f"; las columnas fueron {list(table.columns)[:6]}... Por favor abra un issue."
        )
    frame = table[list(keep)].rename(columns=keep)
    frame.attrs = {"original_columns": {keep[c]: original[c] for c in keep}}
    return frame

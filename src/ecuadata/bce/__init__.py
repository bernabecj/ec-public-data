"""Banco Central del Ecuador (BCE).

>>> import ecuadata as ec
>>> pib = ec.bce.pib_trimestral()                 # PIB, USD encadenados 2018, desestacionalizado
>>> crec = ec.bce.pib_trimestral(measure="growth_yoy")  # variación interanual de volumen, %
>>> remesas = ec.bce.remesas()                    # remesas recibidas por trimestre, USD
>>> tasas = ec.bce.tasas_interes()                # tasas de interés referenciales, %
"""

from __future__ import annotations

import pandas as pd

from ecuadata.bce import fetch as _fetch
from ecuadata.bce import parse as _parse
from ecuadata.bce._remesas import remesas
from ecuadata.bce._tasas import tasas_interes
from ecuadata.bce.parse import MEASURE_NAMES

__all__ = ["MEASURE_NAMES", "pib_trimestral", "remesas", "tasas_interes"]

SOURCE = "BCE"


def pib_trimestral(
    measure: str = "constant_prices",
    seasonally_adjusted: bool = True,
    release: str | pd.Period | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    """PIB trimestral por componente del gasto, de las cuentas nacionales trimestrales del BCE.

    Una fila por trimestre desde 2000Q1 hasta el último trimestre publicado. Las columnas son
    los componentes del gasto: ``pib``, ``consumo_hogares``, ``consumo_gobierno``, ``fbkf``,
    ``exportaciones``, ``importaciones`` y, en las tablas a precios corrientes, también
    ``oferta_final``, ``demanda_interna``, ``variacion_existencias`` y ``utilizacion_final``.

    Args:
        measure: Qué tabla de la publicación devolver:

            - ``"constant_prices"``: miles de USD a precios encadenados de 2018 (por defecto).
            - ``"current_prices"``: miles de USD a precios corrientes.
            - ``"volume_index"``: índice de volumen encadenado, 2018 = 100.
            - ``"growth_yoy"`` / ``"growth_qoq"``: variación del volumen en porcentaje,
              interanual o respecto al trimestre anterior.
            - ``"price_index"`` / ``"price_index_yoy"``: índice de precios implícito
              (2018 = 100) y su variación interanual.
            - ``"contribution_yoy"`` / ``"contribution_qoq"``: contribución de cada componente
              al crecimiento del PIB, en puntos porcentuales.
        seasonally_adjusted: Usar la tabla ajustada por estacionalidad (por defecto) o la de
            datos brutos. Las variaciones, índices de precios y contribuciones solo existen
            con ajuste estacional.
        release: Trimestre de una publicación específica, p. ej. ``"2026Q1"``. None significa
            la última publicación del BCE.
        refresh: Volver a descargar aunque haya una copia vigente en el caché.

    Returns:
        DataFrame con un ``PeriodIndex`` trimestral llamado ``quarter`` y columnas float.
        ``df.attrs`` contiene ``source``, ``dataset``, ``url``, ``release``, ``bulletin``,
        ``units``, ``retrieved_at`` y ``original_columns``.

    Raises:
        ValueError: ``measure`` desconocida o combinación que el BCE no publica.
        SourceUnavailableError: no se pudo contactar al BCE o la publicación no existe.
        OfflineError: modo sin conexión activo y la publicación no está en el caché.
        ParseError: el libro no tiene el formato que espera el parser.

    Example:
        >>> pib = ec.bce.pib_trimestral()
        >>> pib.loc["2024Q1":, ["pib", "fbkf"]]
        >>> pib.attrs["units"]
        'miles de USD, precios encadenados de 2018'
    """
    spec = _parse.measure_for(measure, seasonally_adjusted)  # fail fast, before any download
    workbook = _fetch.fetch("tou", release=release, refresh=refresh)
    frame = _parse.parse_pib_trimestral(workbook.content, measure, seasonally_adjusted)
    frame.attrs.update(
        {
            "source": SOURCE,
            "dataset": "pib_trimestral",
            "table": workbook.table,
            "sheet": spec.sheet,
            "url": workbook.url,
            "release": str(workbook.quarter),
            "bulletin": _fetch.bulletin_for(workbook.quarter),
            "retrieved_at": workbook.retrieved_at.isoformat(),
        }
    )
    return frame

"""Catálogo de conjuntos de datos: qué existe, de dónde viene y cómo se obtiene.

>>> import ecuadata as ec
>>> ec.list_sources()                 # todos los conjuntos de datos, uno por fila
>>> ec.search("inflacion")            # los que coinciden con una palabra (sin importar tildes)
>>> ec.search("empleo", status=None)  # incluir también los planificados
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from ecuadata._parsing import strip_accents

STATUSES = ("stable", "experimental", "planned")


@dataclass(frozen=True)
class Dataset:
    """One entry of the catalogue."""

    provider: str  # "BCE", "INEC", ...
    name: str  # dataset id, also the function name: "pib_trimestral"
    function: str | None  # dotted path inside ecuadata: "bce.pib_trimestral"; None if planned
    title: str
    description: str
    frequency: str  # "Q", "M", "A", "W" or "" when planned
    start: str  # first period available, "" when planned
    units: str
    status: str  # one of STATUSES
    url: str  # where the publisher exposes it
    via: str = ""  # delivery channel when it differs from the publisher
    keywords: tuple[str, ...] = field(default_factory=tuple)

    def resolve(self) -> Callable[..., pd.DataFrame]:
        """Import and return the function behind this dataset."""
        if self.function is None:
            raise NotImplementedError(
                f"{self.provider} {self.name!r} está planificado, aún no implementado."
            )
        module_name, _, attribute = self.function.rpartition(".")
        module = importlib.import_module(f"ecuadata.{module_name}")
        return getattr(module, attribute)

    @property
    def call(self) -> str:
        return f"ec.{self.function}()" if self.function else ""


DATASETS: tuple[Dataset, ...] = (
    Dataset(
        provider="BCE",
        name="pib_trimestral",
        function="bce.pib_trimestral",
        title="PIB trimestral por componente del gasto",
        description=(
            "Cuentas nacionales trimestrales: PIB, consumo de hogares y gobierno, FBKF, "
            "exportaciones e importaciones; precios corrientes y encadenados de 2018, índice "
            "de volumen, variaciones y contribuciones, con o sin ajuste estacional."
        ),
        frequency="Q",
        start="2000Q1",
        units="miles de USD / índice 2018=100 / porcentaje",
        status="experimental",
        url="https://contenido.bce.fin.ec/documentos/informacioneconomica/cuentasnacionales/trimestrales/",
        keywords=("gdp", "producto interno bruto", "cuentas nacionales", "crecimiento", "economia"),
    ),
    Dataset(
        provider="BCE",
        name="remesas",
        function="bce.remesas",
        title="Remesas de trabajadores recibidas y enviadas",
        description=(
            "Remesas de trabajadores recibidas y enviadas: monto en USD y número de giros, "
            "total nacional o por país de origen/destino."
        ),
        frequency="Q",
        start="1993Q1",
        units="USD, número de giros",
        status="experimental",
        url="https://contenido.bce.fin.ec/series-de-datos-remesas-de-trabajadores/",
        keywords=("remittances", "migrantes", "balanza de pagos", "sector externo"),
    ),
    Dataset(
        provider="BCE",
        name="tasas_interes",
        function="bce.tasas_interes",
        title="Tasas de interés referenciales y por segmento de crédito",
        description=(
            "Tasas de interés referenciales vigentes (activa, pasiva, legal, máxima "
            "convencional) y tasas activas efectivas referenciales y máximas por segmento de "
            "crédito (productivo, consumo, microcrédito, vivienda, educativo)."
        ),
        frequency="M",
        start="2015-01",
        units="porcentaje anual",
        status="experimental",
        url="https://contenido.bce.fin.ec/bcedata/",
        via="API de BCEData, cuadros 1.10.1, 1.10.2 y 1.10.2a",
        keywords=("interest rates", "credito", "prestamos", "sector monetario", "bancos"),
    ),
    Dataset(
        provider="INEC",
        name="ipc",
        function="inec.ipc",
        title="Índice de precios al consumidor (IPC) e inflación",
        description=(
            "Índice de precios al consumidor: índice general y doce divisiones COICOP; "
            "variación mensual, anual y acumulada (inflación)."
        ),
        frequency="M",
        start="2006-01",
        units="índice (jul 2025-jun 2026 = 100), porcentaje",
        status="experimental",
        url="https://www.ecuadorencifras.gob.ec/indice-de-precios-al-consumidor/",
        via="API de BCEData, cuadro 4.2.1 (datos del INEC republicados por el BCE)",
        keywords=("cpi", "inflacion", "inflation", "precios", "canasta", "coicop"),
    ),
    Dataset(
        provider="INEC",
        name="enemdu",
        function=None,
        title="Indicadores de empleo (ENEMDU)",
        description=(
            "Indicadores del mercado laboral nacional, urbano y rural: empleo adecuado, "
            "subempleo, desempleo."
        ),
        frequency="",
        start="",
        units="porcentaje",
        status="planned",
        url="https://www.ecuadorencifras.gob.ec/enemdu-2025/",
        keywords=("empleo", "desempleo", "unemployment", "labour", "trabajo", "mercado laboral"),
    ),
    Dataset(
        provider="INEC",
        name="pobreza",
        function=None,
        title="Pobreza y desigualdad",
        description="Pobreza por ingresos, pobreza extrema, pobreza multidimensional y Gini.",
        frequency="",
        start="",
        units="porcentaje, índice",
        status="planned",
        url="https://www.ecuadorencifras.gob.ec/pobreza-y-desigualdad/",
        keywords=("poverty", "desigualdad", "gini", "inequality"),
    ),
    Dataset(
        provider="SRI",
        name="recaudacion",
        function=None,
        title="Estadísticas de recaudación tributaria",
        description="Recaudación tributaria por tipo de impuesto.",
        frequency="",
        start="",
        units="USD",
        status="planned",
        url="https://www.sri.gob.ec/estadisticas-generales-de-recaudacion-sri",
        keywords=("taxes", "impuestos", "iva", "renta", "fiscal"),
    ),
)

_COLUMNS = [
    "provider",
    "dataset",
    "call",
    "status",
    "frequency",
    "start",
    "units",
    "title",
    "via",
    "url",
]


def get(name: str) -> Dataset:
    """The catalogue entry for ``name`` (``"ipc"``) or ``"provider.name"`` (``"inec.ipc"``)."""
    key = name.strip().lower()
    for dataset in DATASETS:
        if key in (dataset.name, f"{dataset.provider.lower()}.{dataset.name}"):
            return dataset
    raise KeyError(f"No existe un conjunto de datos llamado {name!r}. Vea ec.list_sources().")


def _frame(datasets: list[Dataset]) -> pd.DataFrame:
    rows = [
        {
            "provider": d.provider,
            "dataset": d.name,
            "call": d.call,
            "status": d.status,
            "frequency": d.frequency,
            "start": d.start,
            "units": d.units,
            "title": d.title,
            "via": d.via,
            "url": d.url,
        }
        for d in datasets
    ]
    frame = pd.DataFrame(rows, columns=_COLUMNS)
    return frame.set_index(["provider", "dataset"])


def list_sources(status: str | None = None) -> pd.DataFrame:
    """Todos los conjuntos de datos del catálogo, uno por fila, indexados por (fuente, dataset).

    Args:
        status: Conservar solo los ``"stable"``, ``"experimental"`` o ``"planned"``.
            None (por defecto) lista todo.

    Example:
        >>> ec.list_sources(status="experimental")["call"].tolist()
        ['ec.bce.pib_trimestral()', 'ec.bce.remesas()', 'ec.bce.tasas_interes()', 'ec.inec.ipc()']
    """
    if status is not None and status not in STATUSES:
        raise ValueError(f"Estado desconocido {status!r}; elija uno de {STATUSES}.")
    return _frame([d for d in DATASETS if status is None or d.status == status])


def _haystack(dataset: Dataset) -> str:
    parts = [
        dataset.provider,
        dataset.name,
        dataset.title,
        dataset.description,
        dataset.units,
        dataset.via,
        *dataset.keywords,
    ]
    return strip_accents(" ".join(parts)).lower()


def search(query: str, status: str | None = "implemented") -> pd.DataFrame:
    """Conjuntos de datos cuyo nombre, título, descripción o palabras clave contienen ``query``.

    La búsqueda ignora tildes y mayúsculas: ``"inflacion"`` encuentra ``ipc`` y
    ``"Remesas"`` encuentra ``remesas``. Si hay varias palabras, todas deben coincidir.

    Args:
        query: Una o más palabras.
        status: ``"implemented"`` (por defecto: stable y experimental), un estado concreto, o
            None para incluir también los planificados.

    Example:
        >>> ec.search("inflacion").index.tolist()
        [('INEC', 'ipc')]
    """
    words = [w for w in strip_accents(query).lower().split() if w]
    if not words:
        raise ValueError("Indique al menos una palabra para buscar.")
    if status == "implemented":
        allowed = {"stable", "experimental"}
    elif status is None:
        allowed = set(STATUSES)
    elif status in STATUSES:
        allowed = {status}
    else:
        raise ValueError(
            f"Estado desconocido {status!r}; elija uno de {STATUSES}, 'implemented' o None."
        )
    matches = [
        d for d in DATASETS if d.status in allowed and all(word in _haystack(d) for word in words)
    ]
    return _frame(matches)

# ecuadata

**Datos públicos del Ecuador como DataFrames de pandas.**

El Ecuador publica muchos datos útiles: series económicas del Banco Central, estadísticas del INEC, cifras tributarias del SRI. Lo difícil es llegar a ellos: están repartidos en páginas web, libros de Excel con encabezados combinados, PDF, archivos con coma decimal y enlaces que cambian con cada publicación.

`ecuadata` pone una sola API de Python delante de todo eso. Usted pide un conjunto de datos y recibe un `pandas.DataFrame` limpio y tipado. La descarga, el procesamiento y el caché ocurren detrás de esa llamada.

> **Estado: desarrollo temprano.** Las fuentes se agregan una por una; vea la [tabla de fuentes](#fuentes) y [docs/ESTADO.md](docs/ESTADO.md) para saber qué funciona hoy y con qué limitaciones.

---

## Ejemplo

```python
import ecuadata as ec

# Banco Central del Ecuador: PIB trimestral por componente del gasto
pib = ec.bce.pib_trimestral()                              # USD encadenados 2018, desestacionalizado
crecimiento = ec.bce.pib_trimestral(measure="growth_yoy")  # variación interanual, %

# BCE: remesas de trabajadores y tasas de interés
remesas = ec.bce.remesas()                                 # trimestral, USD y número de giros
por_pais = ec.bce.remesas(by="country", frequency="A")     # una columna por país
tasas = ec.bce.tasas_interes()                             # activa, pasiva, legal, máxima convencional

# INEC: índice de precios al consumidor e inflación
ipc = ec.inec.ipc(start="2020-01")
inflacion = ec.inec.ipc(measure="annual_change")["general"]

# Qué hay disponible
ec.list_sources()
ec.search("inflacion")
```

Todas las funciones devuelven un DataFrame que sigue las mismas reglas:

- **Las fechas son fechas.** Las series de tiempo usan un `PeriodIndex` con la frecuencia de la fuente (`Q`, `M`, `A`).
- **Los números son números.** Comas decimales, separadores de miles, notas al pie y marcadores como `"-"` o `"n.d."` se convierten en `float` y `NaN`.
- **Las columnas están en `snake_case`.** Las etiquetas originales de la fuente se conservan en los metadatos.
- **Los metadatos viajan con los datos.** `df.attrs` registra la fuente, la URL, las unidades y el momento de la descarga:

```python
>>> ipc.attrs
{
    "source": "INEC",
    "via": "BCEData del BCE, cuadro 4.2.1 Índice de Precios al Consumidor",
    "dataset": "ipc",
    "measure": "index",
    "units": "índice (ver attrs['base'])",
    "base": "Índice, julio 2025-junio 2026=100; ...",
    "url": "https://contenido.bce.fin.ec/wp-json/bcedata/v1/grid?...",
    "retrieved_at": "2026-10-16T15:56:48+00:00",
    "original_columns": {"general": "Índice General - IPC", ...},
}
```

---

## Instalación

```bash
pip install ecuadata
```

Python puro, 3.10 o superior. Dependencias: `pandas`, `httpx`, `openpyxl`, `platformdirs`. No necesita clave de API, cuenta ni Java.

### Entorno virtual (recomendado)

Use un entorno virtual para no mezclar las dependencias con las del sistema.

Windows (PowerShell):

```powershell
git clone https://github.com/bernabecj/ec-public-data.git
cd ec-public-data
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Linux / macOS:

```bash
git clone https://github.com/bernabecj/ec-public-data.git
cd ec-public-data
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

`requirements.txt` contiene solo las dependencias de ejecución; `requirements-dev.txt` añade el
paquete en modo editable, `pytest` y `ruff` (equivale a `pip install -e ".[dev]"`). Si PowerShell
bloquea la activación, ejecute una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Para salir del entorno: `deactivate`.

---

## Fuentes

| Institución | Conjunto de datos | Función | Estado |
|---|---|---|---|
| Banco Central del Ecuador (BCE) | Cuentas nacionales trimestrales: PIB por componente del gasto | `ec.bce.pib_trimestral()` | Experimental |
| BCE | Remesas de trabajadores recibidas y enviadas | `ec.bce.remesas()` | Experimental |
| BCE | Tasas de interés referenciales y por segmento de crédito | `ec.bce.tasas_interes()` | Experimental |
| INEC | Índice de precios al consumidor (IPC) e inflación | `ec.inec.ipc()` | Experimental |
| INEC | Indicadores de empleo (ENEMDU) | `ec.inec.enemdu()` | Planificado |
| INEC | Pobreza y desigualdad | `ec.inec.pobreza()` | Planificado |
| SRI | Estadísticas de recaudación | `ec.sri.recaudacion()` | Planificado |
| Portales municipales | Datos abiertos de Quito / Guayaquil | `ec.municipal.quito(...)` | Planificado |

Estados: **Planificado**, **Experimental** (funciona, pero el esquema de salida todavía puede cambiar), **Estable**.

Detalles de cada fuente, con columnas, unidades y particularidades: [docs/fuentes/bce.md](docs/fuentes/bce.md) y [docs/fuentes/inec.md](docs/fuentes/inec.md).

---

## Caché

Los sitios del gobierno son lentos y a veces están caídos, así que cada descarga se guarda en disco.

```python
ec.config.cache_dir          # por defecto, la carpeta de caché del usuario en el sistema
ec.config.cache_ttl = "7d"   # cuánto tiempo reutilizar una descarga antes de refrescarla

ec.inec.ipc(refresh=True)    # ignorar el caché en esta llamada
ec.cache.clear()             # borrar todo
ec.cache.clear("bce")        # borrar una fuente
```

El caché guarda los **archivos originales descargados** (libros de Excel, respuestas JSON). Si un parser cambia, puede volver a procesar los archivos guardados sin descargar nada.

Con `ec.config.offline = True` se lee únicamente del caché. Las llamadas que necesitarían descargar algo lanzan `OfflineError`.

---

## Diseño

Cada fuente es un módulo autónomo con las mismas partes:

```
fetch   → descargar los archivos originales: XLSX, JSON, HTML
parse   → convertir el archivo en un DataFrame ordenado y tipado
cache   → guardar los archivos originales en disco
expose  → una función pública pequeña con parámetros documentados
```

Descargar y procesar están separados a propósito. Los parsers son funciones puras de bytes a DataFrame, así que se prueban sin red. Cuando una institución cambia el formato de un archivo, la corrección está solo en el parser.

```
src/ecuadata/
├── __init__.py        # ec.bce, ec.inec, ec.config, ec.cache, ec.list_sources, ec.search
├── _catalog.py        # catálogo de conjuntos de datos
├── config.py
├── cache.py
├── http.py            # cliente compartido: reintentos, pausas entre solicitudes, user agent
├── _parsing.py        # utilidades: comas decimales, meses en español, etiquetas de trimestre
├── bce/
│   ├── fetch.py       # libros de cuentas nacionales trimestrales
│   ├── parse.py
│   ├── bcedata.py     # cliente del API REST de BCEData (portal de datos del BCE)
│   ├── _remesas.py
│   └── _tasas.py
└── inec/
    └── _ipc.py
tests/
├── fixtures/          # archivos reales grabados, una carpeta por fuente
├── bce/
└── inec/
scripts/
└── record_fixtures.py # graba archivos reales de las instituciones para las pruebas
```

---

## Pruebas

Por defecto las pruebas usan **respuestas grabadas** y no tocan la red. Cada fuente tiene archivos reales guardados en `tests/fixtures/`, tal como los sirvió la institución. Las pruebas de los parsers verifican nombres de columnas, tipos, frecuencia del índice y algunos valores conocidos.

```bash
pytest                 # rápido, sin red, determinista
pytest -m live         # opcional: consulta las fuentes reales
pytest -x -vv          # detenerse en la primera falla y mostrar el detalle completo
pytest --lf            # repetir solo las pruebas que fallaron la última vez
```

Las pruebas `live` detectan la falla más común en una librería como esta: una fuente que cambia su formato sin avisar. Cuando una falla, la corrección es:

1. Grabar un archivo nuevo con `python scripts/record_fixtures.py`.
2. Ajustar el parser hasta que las pruebas pasen.
3. Subir ambos cambios juntos.

---

## Agregar una fuente

1. **Fetch.** Encontrar la URL estable (o el patrón de URL) y escribir la descarga.
2. **Parse.** Convertir los bytes en un DataFrame que siga las convenciones de arriba.
3. **Catálogo.** Agregar la entrada en `_catalog.py`.
4. **Pruebas.** Grabar una respuesta real en `tests/fixtures/<fuente>/` y escribir pruebas del parser.
5. **Documentar.** Agregar la fila en la tabla de fuentes y la página en `docs/fuentes/`.

Las contribuciones son bienvenidas. Por favor abra un issue antes, para que dos personas no construyan lo mismo.

---

## Hoja de ruta

- [x] Núcleo: cliente HTTP, caché, configuración, utilidades de procesamiento
- [x] Primera fuente de extremo a extremo: PIB trimestral del BCE
- [x] IPC del INEC
- [x] Remesas y tasas de interés del BCE
- [x] Catálogo: `list_sources()` y `search()`
- [ ] ENEMDU y pobreza (INEC)
- [ ] Recaudación del SRI
- [ ] Sitio de documentación
- [ ] Primera publicación en PyPI
- [ ] Datos abiertos municipales (Quito, Guayaquil)

---

## Aviso

`ecuadata` es un proyecto independiente. No está afiliado ni respaldado por el Banco Central del Ecuador, el INEC, el SRI ni ningún municipio. Los datos pertenecen a quienes los publican y están sujetos a sus términos. Revise siempre `df.attrs["url"]` y cite la fuente original.

## Licencia

[MIT](LICENSE)

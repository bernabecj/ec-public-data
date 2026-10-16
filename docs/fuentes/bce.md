# Banco Central del Ecuador (BCE)

Tres conjuntos de datos, de dos canales distintos del BCE:

- Archivos XLSX publicados en `contenido.bce.fin.ec/documentos/...` (cuentas nacionales, remesas).
- **BCEData**, el portal de datos del BCE (`contenido.bce.fin.ec/bcedata/`), que expone un API REST
  público en `/wp-json/bcedata/v1/` con unos 80 cuadros de la Información Estadística Mensual
  (tasas de interés, IPC, balanza de pagos, mercado laboral, PIB anual, agregados monetarios...).

## `ec.bce.pib_trimestral()`

PIB trimestral por componente del gasto, de las cuentas nacionales trimestrales.

```python
pib = ec.bce.pib_trimestral()                                  # precios encadenados 2018, desestacionalizado
nominal = ec.bce.pib_trimestral("current_prices", seasonally_adjusted=False)
crecimiento = ec.bce.pib_trimestral("growth_yoy")              # variación interanual de volumen, %
anterior = ec.bce.pib_trimestral(release="2026Q1")             # una publicación específica
```

| Parámetro | Valores | Por defecto |
|---|---|---|
| `measure` | `constant_prices`, `current_prices`, `volume_index`, `growth_yoy`, `growth_qoq`, `price_index`, `price_index_yoy`, `contribution_yoy`, `contribution_qoq` | `constant_prices` |
| `seasonally_adjusted` | `True` / `False` (las variaciones, índices de precios y contribuciones solo existen con ajuste) | `True` |
| `release` | trimestre de la publicación, p. ej. `"2026Q1"`; `None` = la más reciente | `None` |
| `refresh` | volver a descargar | `False` |

**Salida.** `PeriodIndex` trimestral `quarter` desde 2000Q1. Columnas: `pib`, `consumo_hogares`,
`consumo_gobierno`, `fbkf`, `exportaciones`, `importaciones`; las tablas a precios corrientes añaden
`oferta_final`, `demanda_interna`, `variacion_existencias`, `utilizacion_final`. Unidades en
`attrs["units"]`: miles de USD, índice 2018 = 100, porcentaje o puntos porcentuales según la medida.

**Origen.** Libro `tou_<boletín>_<AAAATT>.xlsx` en
`https://contenido.bce.fin.ec/documentos/informacioneconomica/cuentasnacionales/trimestrales/`.
Cada hoja (`Dem_Corr_bru`, `Dem_Cad_ajus`, `Dem_Ivol_ajus_vY`...) es una medida; las filas son
trimestres (`2000.I`) y las columnas los componentes. El BCE publica cada trimestre unos 90 días
después de terminado. Una publicación ya descargada no caduca en el caché; "la más reciente" se
vuelve a buscar cuando la copia tiene más de `cache_ttl`.

**Particularidades.** `consumo_hogares` incluye a las instituciones sin fines de lucro que sirven a
los hogares (nota `(*)` del BCE). Las variaciones interanuales son `NaN` en el año 2000.

## `ec.bce.remesas()`

Remesas de trabajadores recibidas por el Ecuador y enviadas desde el Ecuador.

```python
remesas = ec.bce.remesas()                                     # recibidas, trimestral
anual = ec.bce.remesas(frequency="A")
enviadas = ec.bce.remesas(flow="sent")
por_pais = ec.bce.remesas(by="country")                        # una columna por país + total
giros = ec.bce.remesas(by="country", count=True)               # número de giros por país
```

| Parámetro | Valores | Por defecto |
|---|---|---|
| `flow` | `received` (recibidas), `sent` (enviadas) | `received` |
| `frequency` | `Q` trimestral, `A` anual | `Q` |
| `by` | `None` (total nacional), `country` | `None` |
| `count` | con `by="country"`, número de giros en vez de monto | `False` |

**Salida.** `PeriodIndex` `period`. Totales: `monto_usd` (USD) y `numero_giros` (desde 2007 en
recibidas, 2010 en enviadas). Por país: una columna por país en `snake_case` (`estados_unidos_de_america`,
`espana`...) más `total`; `attrs["country_codes"]` da el código numérico de cada país y
`attrs["original_columns"]` el nombre original.

**Cobertura.** Recibidas 1993Q1 →, enviadas 2005Q1 →; por país desde 2007Q1 (recibidas) y 2009Q4
(enviadas). El BCE publica cada trimestre, unos 90 días después.

**Origen.** `https://contenido.bce.fin.ec/documentos/Estadisticas/SectorExterno/BalanzaPagos/Remesas/Flujo_de_remesas_de_trabajadores.xlsx`
(nombre fijo; se refresca según `cache_ttl`). Hojas `RR_t`, `RR_a`, `RE_t`, `RE_a` (totales) y
`RRpais_*`, `REpais_*`, `RRpaisg_*`, `REpaisg_*` (por país, montos y giros). Página de referencia:
`https://contenido.bce.fin.ec/series-de-datos-remesas-de-trabajadores/`.

**Particularidades.** Desde julio de 2025 el BCE cambió al levantamiento por microdatos; las bases
detalladas (CSV por parroquia y por entidad) existen pero no se descargan. Un país aparece en dos filas
con distinta capitalización; se fusionan (ver `attrs["merged_duplicate_rows"]`).

## `ec.bce.tasas_interes()`

Tasas de interés mensuales, en porcentaje anual.

```python
tasas = ec.bce.tasas_interes()                                 # pasiva, activa, legal, maxima_convencional
segmentos = ec.bce.tasas_interes("segments", start="2024-01")  # referencial y máxima por segmento
```

| Parámetro | Valores | Por defecto |
|---|---|---|
| `kind` | `reference` (tasas referenciales vigentes), `segments` (por segmento de crédito) | `reference` |
| `start`, `end` | meses `"AAAA-MM"` | todo el rango |

**Salida.** `PeriodIndex` mensual `period`. `reference`: `pasiva`, `activa`, `legal`,
`maxima_convencional` (2015-01 →). `segments`: para cada segmento, la tasa activa efectiva referencial
(`productivo_corporativo`, `consumo`, `microcredito_minorista`, `vivienda_de_interes_publico`...) y la
máxima (`maxima_productivo_corporativo`...). La segmentación cambió en mayo de 2021; los segmentos
anteriores (`consumo_ordinario`, `comercial_prioritario_pymes`...) quedan en `NaN` desde entonces y los
nuevos son `NaN` antes.

**Origen.** BCEData, cuadros 1.10.1 (referenciales, frecuencia mensual), 1.10.2 (segmentos agosto
2015 – abril 2021) y 1.10.2a (segmentos mayo 2021 →). Las dos tablas por segmento se unen en una sola
serie; `attrs["tables"]` y `attrs["urls"]` indican de dónde salió cada parte.

**Nota.** La tasa básica semanal existe en BCEData (cuadro 1.10.1, frecuencia semanal) pero no se expone
por esta función; se puede obtener con `ecuadata.bce.bcedata.table(49, frecuencia="Semanal")`.

## Acceso directo a BCEData

`ecuadata.bce.bcedata` es el cliente que usan `tasas_interes()` e `ipc()`. Sirve para cualquier cuadro del portal:

```python
from ecuadata.bce import bcedata

bcedata.tree()                         # índice de cuadros (id_grupo, código, nombre)
bcedata.bundle(35)                     # frecuencias, unidades y rango de un cuadro
bcedata.table(35)                      # 1.1.1 Oferta monetaria (M1) y liquidez total (M2)
bcedata.table(2, frecuencia="Anual")   # 3.2.1 Balanza de pagos normalizada
```

`table()` devuelve un DataFrame con `PeriodIndex` (semanal, mensual, trimestral o anual según el cuadro)
y una columna por serie, nombrada por su ruta en la jerarquía del cuadro
(`nacional_desempleo`, `cuenta_corriente_bienes_y_servicios_exportaciones`). Los nombres originales están
en `attrs["original_columns"]`.

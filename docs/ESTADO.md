# Estado del proyecto

Última actualización: octubre de 2026. Este documento resume qué funciona hoy, cómo se
obtiene cada dato y qué limitaciones conocemos. Se actualiza con cada fase del proyecto.

## Qué funciona hoy

| Función | Datos | Período | Canal de descarga | Estado |
|---|---|---|---|---|
| `ec.bce.pib_trimestral()` | PIB y componentes del gasto, 12 medidas (precios corrientes y encadenados, índice de volumen, variaciones, índice de precios, contribuciones) | 2000Q1 → último trimestre publicado | Libro XLSX `tou_<boletín>_<AAAATT>.xlsx` del BCE; el número de boletín se calcula a partir del trimestre | Experimental |
| `ec.bce.remesas()` | Remesas recibidas y enviadas: monto en USD y número de giros; total o por país | Recibidas 1993Q1 →, enviadas 2005Q1 →; por país desde 2007 / 2009Q4 | Libro XLSX con nombre fijo `Flujo_de_remesas_de_trabajadores.xlsx` | Experimental |
| `ec.bce.tasas_interes()` | Tasas referenciales vigentes (pasiva, activa, legal, máxima convencional) y tasas por segmento de crédito (referencial y máxima) | 2015-01 → mes en curso; segmentos desde 2015-08 | API REST de **BCEData**, cuadros 1.10.1, 1.10.2 y 1.10.2a | Experimental |
| `ec.inec.ipc()` | Índice de precios al consumidor: índice general y 12 divisiones COICOP; variación mensual, anual y acumulada | 2006-01 → último mes publicado | API REST de **BCEData**, cuadro 4.2.1 (datos del INEC republicados por el BCE) | Experimental |
| `ec.list_sources()`, `ec.search()` | Catálogo de conjuntos de datos | — | Sin red | Estable |

Todas las funciones comparten el mismo comportamiento:

- Caché en disco de los archivos originales, con vigencia configurable (`ec.config.cache_ttl`, 7 días por defecto). Una publicación trimestral ya descargada no caduca nunca.
- Modo sin conexión (`ec.config.offline = True`): solo lee del caché y lanza `OfflineError` si falta algo.
- Pausas entre solicitudes y reintentos ante errores 5xx, para no provocar bloqueos de IP.
- Validación de argumentos **antes** de descargar nada.
- Errores en español con la causa y el siguiente paso: `SourceUnavailableError` (la institución no responde o movió el archivo), `ParseError` (el formato cambió), `OfflineError`.

Verificación: `pytest` corre 192 pruebas sin red sobre archivos reales grabados en `tests/fixtures/`; `pytest -m live` consulta las fuentes reales y comprueba el esquema de cada función.

## Qué NO funciona todavía

| Conjunto de datos | Situación |
|---|---|
| `ec.inec.enemdu()` | Planificado. BCEData publica los indicadores del mercado laboral del INEC (cuadro 4.2.5: empleo adecuado, subempleo, desempleo; nacional, urbano y rural; 2007-12 →), así que el camino está despejado. |
| `ec.inec.pobreza()` | Planificado. La página del INEC solo enlaza PDF y mapas; no se ha encontrado una fuente tabular estable. |
| `ec.sri.recaudacion()` | Planificado. Sin investigar. |
| Portales municipales | Planificado. Sin investigar. |

## Limitaciones conocidas

### 1. La página del IPC del INEC está rota

La página oficial del IPC (`ecuadorencifras.gob.ec/indice-de-precios-al-consumidor/`) carga su lista de descargas en un marco (`iframe`) que devuelve **error 404**, también desde un navegador. Las páginas de "históricos" del INEC están congeladas en diciembre de 2018 y se descartaron por obsoletas. Se probaron doce convenciones de nombre de archivo de 2018 y 2026 sin éxito.

Por eso `ec.inec.ipc()` lee el IPC desde **BCEData**, el portal de datos del Banco Central, que republica las cifras oficiales del INEC (índice general, divisiones y variaciones). Los números son los del INEC; solo cambia el canal. `df.attrs["source"]` dice `"INEC"` y `df.attrs["via"]` indica el cuadro de BCEData. Si el INEC repara su página, el canal se puede cambiar sin alterar la función.

Consecuencia: no se dispone del IPC por ciudades ni por productos, solo el nacional por división.

### 2. Bloqueo de IP por parte del BCE

`contenido.bce.fin.ec` bloquea direcciones IP que hacen muchas solicitudes seguidas (respondió 403 durante el desarrollo de este proyecto). La librería espera al menos 2 segundos entre solicitudes y no reintenta cuando la conexión es rechazada. Si recibe `SourceUnavailableError` con "bloqueando su IP", espere unas horas o cambie de red; mientras tanto `ec.config.offline = True` permite seguir trabajando con lo que ya esté en caché.

El mismo servidor cierra conexiones al azar (`Server disconnected`); un reintento suele bastar.

### 3. Numeración de boletines del BCE

Las cuentas nacionales trimestrales se descargan por nombre de archivo (`tou_136_202602.xlsx`), donde el número de boletín sube en uno cada trimestre. La librería lo calcula a partir de un ancla (boletín 132 = 2025Q2, confirmado hasta 136 = 2026Q2). Si el BCE saltara un número, `pib_trimestral()` lanzaría `SourceUnavailableError` indicando que la numeración pudo cambiar; la corrección es actualizar el ancla en `bce/fetch.py`.

### 4. Dependencia de BCEData

`tasas_interes()` e `ipc()` dependen del API REST de BCEData (`/wp-json/bcedata/v1/`). Es un API público sin autenticación, pero no documentado oficialmente; sus rutas se dedujeron del propio portal. Si el API cambia, las funciones lanzan `SourceUnavailableError` o `ParseError` con la URL afectada. Los documentos JSON se guardan en caché, así que un cambio en el API no afecta a lo ya descargado.

### 5. Dos tablas aún no verificadas con datos reales

Las pruebas de la **variación del IPC** (`measure="monthly_change"`, `"annual_change"`, `"ytd_change"`) y de las **tasas referenciales mensuales** usan respuestas construidas a partir de la estructura declarada por el API (las filas del `bundle`), no respuestas grabadas. `pytest -m live` las verifica contra el servidor real; si el formato difiere, el ajuste está en `inec/_ipc.py::_select` y `bce/_tasas.py::_reference`.

### 6. Particularidades de los datos de origen que la librería corrige

- BCEData publica a veces dos semanas superpuestas en las tasas semanales; se conserva la primera y se anota en `attrs["dropped_duplicate_periods"]`.
- El libro de remesas lista un mismo país en dos filas que difieren solo en mayúsculas; se fusionan por código de país y se anota en `attrs["merged_duplicate_rows"]`.
- Los encabezados del BCE traen notas al pie pegadas al texto (`Número de giros1`, `Hogares (*)`); se eliminan al construir los nombres de columna.
- El IPC cambió de base en 2026 (julio 2025 – junio 2026 = 100); la base vigente se expone en `attrs["base"]` tal como la declara la fuente.

### 7. Alcance

- Solo estadísticas agregadas. No se descargan microdatos (por ejemplo, las bases de remesas por parroquia del BCE o las encuestas del INEC).
- Sin soporte de PDF: las fuentes que solo publican PDF (como las resoluciones de tasas de la Junta de Política y Regulación Financiera) quedan fuera.
- El esquema de salida (nombres de columnas, valores de `attrs`) puede cambiar mientras las fuentes estén en estado Experimental.

## Cómo verificar el estado en su máquina

```bash
pip install -e ".[dev]"
pytest                        # 192 pruebas sin red
pytest -m live                # consulta las fuentes reales (1-2 minutos)
python scripts/record_fixtures.py --dataset bcedata   # regraba las respuestas del API
```

# Instituto Nacional de Estadística y Censos (INEC)

## `ec.inec.ipc()`

Índice de precios al consumidor, mensual, por división de consumo (COICOP).

```python
ipc = ec.inec.ipc()                                    # índice, 2006-01 → último mes
inflacion_anual = ec.inec.ipc("annual_change")["general"]
inflacion_mensual = ec.inec.ipc("monthly_change", start="2025-01")
acumulada = ec.inec.ipc("ytd_change")                  # desde diciembre del año anterior
```

| Parámetro | Valores | Por defecto |
|---|---|---|
| `measure` | `index`, `monthly_change`, `annual_change`, `ytd_change` | `index` |
| `start`, `end` | meses `"AAAA-MM"` | todo el rango |
| `refresh` | volver a descargar | `False` |

**Salida.** `PeriodIndex` mensual `period`. Columnas: `general` y las doce divisiones:

| Columna | División del INEC |
|---|---|
| `alimentos_bebidas_no_alcoholicas` | Alimentos y bebidas no alcohólicas |
| `bebidas_alcoholicas_tabaco` | Bebidas alcohólicas, tabaco y estupefacientes |
| `prendas_vestir_calzado` | Prendas de vestir y calzado |
| `vivienda_servicios_basicos` | Vivienda, agua, electricidad, gas y otros combustibles |
| `muebles_articulos_hogar` | Muebles y artículos para el hogar y para conservación ordinaria del hogar |
| `salud` | Salud |
| `transporte` | Transporte |
| `informacion_comunicacion` | Información y comunicación |
| `recreacion_cultura` | Recreación, deporte y cultura |
| `educacion` | Servicios educativos |
| `restaurantes_alojamiento` | Servicios de restaurantes y alojamiento |
| `seguros_servicios_financieros` | Seguros y servicios financieros (desde 2019) |
| `bienes_servicios_diversos` | Cuidado personal, revisión social y bienes y servicios diversos |

Las etiquetas originales están en `attrs["original_columns"]`. Si el INEC añade una división, aparece con
su nombre en `snake_case`.

**Base del índice.** El INEC cambió la base en 2026: julio 2025 – junio 2026 = 100. La base vigente se
expone en `attrs["base"]` tal como la declara la fuente. Las variaciones porcentuales no dependen de la base.

**Cobertura.** 2006-01 → último mes publicado (el INEC publica en los primeros días del mes siguiente;
BCEData lo replica poco después).

**Origen y canal.** Los datos son del INEC, pero se leen desde **BCEData**, el portal de datos del Banco
Central (cuadro 4.2.1 *Índice de Precios al Consumidor*, unidades `Indice` y `Porcentaje`). La página
oficial del INEC tiene rota su lista de descargas (ver [ESTADO.md](../ESTADO.md)). Por eso:

- `attrs["source"]` es `"INEC"` y `attrs["via"]` indica el cuadro de BCEData;
- solo está disponible el IPC nacional por división; no el desglose por ciudad ni por producto.

## Planificado

- `ec.inec.enemdu()`: indicadores del mercado laboral (empleo adecuado, subempleo, desempleo; nacional,
  urbano y rural). BCEData los publica en el cuadro 4.2.5 desde 2007-12, que ya se puede consultar con
  `ecuadata.bce.bcedata.table(68)`.
- `ec.inec.pobreza()`: pobreza por ingresos, pobreza extrema, multidimensional y Gini. Sin fuente tabular
  estable identificada.

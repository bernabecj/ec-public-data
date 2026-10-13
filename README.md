# ecuadata

**Ecuadorian public data as pandas DataFrames.**

Ecuador publishes plenty of useful public data: Banco Central economic series, INEC statistics, SRI tax figures, municipal open data portals. Getting at it is the hard part. It is spread across web pages, Excel workbooks with merged headers, PDFs, CSVs with decimal commas, and URLs that change between releases.

`ecuadata` puts one Python API in front of all of it. You ask for a dataset and get back a clean, typed `pandas.DataFrame`. Fetching, parsing, and caching happen behind that call.

> **Status: early development.** The API below is the design target. Sources are added one at a time; see the [source table](#sources) for what works today.

---

## Example

```python
import ecuadata as ec

# Banco Central del Ecuador: quarterly GDP
gdp = ec.bce.series("pib_trimestral")

# INEC: monthly consumer price index
cpi = ec.inec.ipc(start="2020-01", end="2025-12")

# SRI: tax collection by tax type
tax = ec.sri.recaudacion(year=2024)

# Find out what is available
ec.list_sources()
ec.search("inflacion")
```

Every call returns a DataFrame that follows the same rules:

- **Dates are real dates.** Time series use a `DatetimeIndex` or `PeriodIndex` at the source's frequency.
- **Numbers are numbers.** Decimal commas, thousands separators, footnote markers, and `"-"` / `"n.d."` placeholders become proper floats and `NaN`.
- **Columns are `snake_case`.** The original source labels are kept in the metadata.
- **Metadata travels with the data.** `df.attrs` records the source, URL, units, and retrieval time:

```python
>>> cpi.attrs
{
    "source": "INEC",
    "dataset": "ipc",
    "url": "https://www.ecuadorencifras.gob.ec/...",
    "units": "index (2014 = 100)",
    "retrieved_at": "2026-10-13T16:30:00-05:00",
    "original_columns": {...},
}
```

---

## Installation

```bash
pip install ecuadata
```

Pure Python, 3.10 or newer. Dependencies: `pandas`, `httpx`, `openpyxl`, `platformdirs`. You don't need an API key, an account, or a Java runtime.

For development:

```bash
git clone https://github.com/bernabecj/ec-public-data.git
cd ec-public-data
pip install -e ".[dev]"
```

---

## Sources

| Provider | Dataset | Function | Status |
|---|---|---|---|
| Banco Central del Ecuador (BCE) | Quarterly national accounts | `ec.bce.series("pib_trimestral")` | Planned |
| BCE | Monthly statistical bulletin series | `ec.bce.series(...)` | Planned |
| BCE | Interest rates | `ec.bce.tasas_interes()` | Planned |
| BCE | Remittances | `ec.bce.remesas()` | Planned |
| INEC | Consumer price index (IPC) | `ec.inec.ipc()` | Planned |
| INEC | Employment survey indicators (ENEMDU) | `ec.inec.enemdu()` | Planned |
| INEC | Poverty and inequality | `ec.inec.pobreza()` | Planned |
| SRI | Tax collection statistics | `ec.sri.recaudacion()` | Planned |
| Municipal portals | Quito / Guayaquil open data | `ec.municipal.quito(...)` | Planned |

Status values: **Planned**, **Experimental** (works, but the output schema may still change), **Stable**.

---

## Caching

Government sites are slow and sometimes down, so every download is cached on disk.

```python
ec.config.cache_dir          # defaults to the OS user cache directory
ec.config.cache_ttl = "7d"   # how long before data is re-fetched

ec.inec.ipc(refresh=True)    # bypass the cache for this call
ec.cache.clear()             # clear everything
ec.cache.clear("bce")        # clear one provider
```

The cache stores the **raw downloaded files** as well as the parsed results. If a parser changes, it can re-parse from the stored files without downloading anything again.

Set `ec.config.offline = True` to read only from the cache. Calls that would need a download then raise an error.

---

## Design

Each source is a self-contained module with the same four parts:

```
fetch   → download the raw file(s): HTML, XLSX, CSV, PDF
parse   → turn the raw file into a tidy, typed DataFrame
cache   → store the raw files and parsed output on disk
expose  → a small public function with documented parameters
```

Fetch and parse are kept apart on purpose. Parsers are pure functions from bytes to a DataFrame, so they can be tested without network access. When an institution changes a spreadsheet layout, the fix is in the parser alone.

```
src/ecuadata/
├── __init__.py
├── config.py
├── cache.py
├── http.py            # shared client: retries, timeouts, user agent
├── _parsing.py        # shared helpers: decimal commas, Spanish month names, merged headers
├── bce/
│   ├── __init__.py
│   ├── fetch.py
│   └── parse.py
├── inec/
├── sri/
└── municipal/
tests/
├── fixtures/          # recorded raw responses, one folder per source
│   ├── bce/
│   └── inec/
├── bce/
└── inec/
```

---

## Testing

By default the tests use **recorded responses** and make no network calls. Each source has real files saved under `tests/fixtures/` as the institution served them. The parser tests run against those files and check column names, dtypes, index frequency, and a few known values.

```bash
pytest                 # fast, offline, deterministic
pytest -m live         # opt-in: hits the real sources
```

The `live` tests catch the most common failure for a library like this: a source quietly changing its format. When one fails, the fix is:

1. Record a fresh fixture.
2. Update the parser until the tests pass.
3. Commit both together.

---

## Adding a source

Each new source follows the same checklist:

1. **Fetch.** Find the stable URL or URL pattern and write `fetch.py`.
2. **Parse.** Write `parse.py` to turn raw bytes into a DataFrame that follows the conventions above.
3. **Cache.** Register the dataset with the cache layer (usually a single line).
4. **Test.** Save a real response to `tests/fixtures/<provider>/` and write parser tests against it.
5. **Document.** Add a row to the source table and a docstring with an example.

Pull requests that add a source are welcome. Please open an issue first so two people don't build the same one.

---

## Roadmap

- [ ] Core: HTTP client, cache, config, shared parsing helpers
- [ ] First source end to end: BCE quarterly GDP
- [ ] INEC IPC
- [ ] SRI tax collection
- [ ] `list_sources()` and `search()` catalogue
- [ ] Documentation site
- [ ] First release on PyPI
- [ ] Municipal open data (Quito, Guayaquil)

---

## Disclaimer

`ecuadata` is an independent project. It is not affiliated with or endorsed by the Banco Central del Ecuador, INEC, SRI, or any municipality. The data belongs to its publishers and is subject to their terms. Always check `df.attrs["url"]` and cite the original source.

## License

[MIT](LICENSE)

# Changelog

All notable changes to `ecuadata` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `ec.bce.pib_trimestral()`: quarterly GDP by expenditure component from the BCE quarterly
  national accounts workbook, 12 measures (current/chained prices, volume index, growth,
  price index, contributions), seasonally adjusted or raw.
- `ec.bce.remesas()`: workers' remittances received and sent, totals or by country, quarterly
  or annual, from BCE's fixed-name workbook.
- `ec.bce.tasas_interes()`: reference interest rates and rates by credit segment, monthly,
  from the BCEData REST API (tables 1.10.1, 1.10.2, 1.10.2a stitched across the 2021 break).
- `ec.inec.ipc()`: INEC consumer price index (general and 12 COICOP divisions; index and
  monthly/annual/year-to-date changes) served through BCEData table 4.2.1, because INEC's own
  download page is broken.
- `ecuadata.bce.bcedata`: client for the BCEData REST API (`tree`, `bundle`, `grid`, `table`)
  with cached JSON, offline support and a generic grid parser for weekly, monthly, quarterly
  and annual tables.
- `ec.list_sources()` and `ec.search()`: offline catalogue of implemented and planned datasets.
- `_parsing.parse_month`, `parse_week`, `parse_year`, `month_number`.
- `scripts/record_fixtures.py`: probes BCE and INEC URLs, records real files and API documents
  into `tests/fixtures/`, and writes a manifest of every attempt (including failures).
- Test suite: 192 offline tests on recorded fixtures plus 5 opt-in `live` tests.
- Documentation in Spanish: README, `docs/ESTADO.md` (state and limitations),
  `docs/fuentes/bce.md`, `docs/fuentes/inec.md`.

### Changed
- User-facing text (docstrings of public functions, error messages, descriptive `attrs`
  values, catalogue titles) is in Spanish.
- `ecuadata.bce` exposes dedicated functions instead of a generic `series()`.

### Fixed
- `cache.files()` hid `.json` data files by treating every `.json` as a sidecar.

### Removed
- `test_data.py` scratch probe at the repository root (superseded by the recording script).

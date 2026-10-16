# Test fixtures

Real files served by each institution, recorded with `scripts/record_fixtures.py`.
Parser tests run against these files; nothing here is edited by hand.

```
tests/fixtures/
├── manifest.json              # every URL attempted: status, final URL, size, SHA-256
├── bce/
│   ├── pib_trimestral/        # tou_<bulletin>_<YYYYQQ>.xlsx, landing pages
│   ├── remesas/
│   └── tasas_interes/
└── inec/
    ├── ipc/                   # serie histórica workbook(s), landing.html, discovered_links.txt
    ├── enemdu/                # landing pages only (deferred dataset)
    └── pobreza/               # landing pages only (deferred dataset)
```

## Recording

```bash
pip install -e ".[dev]"
python scripts/record_fixtures.py                 # everything
python scripts/record_fixtures.py --provider inec # one provider
python scripts/record_fixtures.py --dataset ipc   # one dataset
python scripts/record_fixtures.py --list          # show what would be attempted
```

Flags for uncooperative servers:

| Problem | Flag |
|---|---|
| 403 / 429, or connection refused (IP blocked) | wait, then rerun; already recorded files are skipped |
| Site rejects the library user agent | `--user-agent browser` |
| Rate limiting | `--delay 10` |
| Need fresh copies | `--force` |

Broken links are expected. Each failed URL is still written to `manifest.json`, which is
how we learn which URL patterns exist today.

## Refreshing after a source changes its format

1. `python scripts/record_fixtures.py --dataset <name> --force`
2. Fix the parser until `pytest` passes.
3. Commit the fixture, the manifest and the parser change together.

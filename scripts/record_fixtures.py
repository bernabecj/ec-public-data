"""Record real files from BCE and INEC into ``tests/fixtures/``.

The script is a *probe* as much as a recorder. Government URLs break often, so each dataset
lists several candidate URLs and/or a landing page to discover links from. Every attempt,
successful or not, is written to ``tests/fixtures/manifest.json`` with its status code, final
URL, size and SHA-256. A run with many failures is still useful: the manifest tells us which
URL patterns actually exist today.

Usage (from the repository root, after ``pip install -e ".[dev]"``)::

    python scripts/record_fixtures.py                      # everything
    python scripts/record_fixtures.py --provider inec      # one provider
    python scripts/record_fixtures.py --dataset remesas    # one dataset
    python scripts/record_fixtures.py --user-agent browser # if a site rejects the library UA
    python scripts/record_fixtures.py --delay 10 --force   # slower, and re-download everything

Behaviour when a source misbehaves:

* 403 / 429 or a connection failure marks the host as **blocked**; every remaining request to
  that host is skipped so we never hammer a server that is already refusing us. Wait a while
  (or switch networks) and rerun: files already recorded are skipped, so only the missing ones
  are attempted.
* A 200 response that is not really an XLSX (an HTML error page, for instance) is recorded as
  ``not_xlsx`` and not saved as a fixture.

When done, share the whole ``tests/fixtures/`` folder (and ideally the console output).
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlencode, urljoin, urlparse

import httpx
import pandas as pd

from ecuadata.bce import fetch as bce_fetch

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
MANIFEST = FIXTURES / "manifest.json"

USER_AGENTS = {
    "ecuadata": "ecuadata (+https://github.com/bernabecj/ec-public-data)",
    "browser": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
}
XLSX_MAGIC = b"PK\x03\x04"
XLS_MAGIC = b"\xd0\xcf\x11\xe0"  # legacy OLE2 workbooks, still served by INEC
BLOCKING_STATUSES = {403, 429}
BCEDATA_API = "https://contenido.bce.fin.ec/wp-json/bcedata/v1"
# Hosts known to block aggressive clients get a longer pause between requests.
HOST_DELAY = {"contenido.bce.fin.ec": 5.0}
MAX_DISCOVERED = 4  # files to download per discovery step
TIMEOUT = 60.0

# --------------------------------------------------------------------------------------------
# Recipes: what to record for each dataset
# --------------------------------------------------------------------------------------------


@dataclass
class Recipe:
    provider: str
    dataset: str
    # Direct URLs to try, in priority order. Each is (filename to save as, url).
    direct: list[tuple[str, str]] = field(default_factory=list)
    # Landing pages whose HTML is saved, and whose links matching ``link_pattern`` are downloaded.
    pages: list[tuple[str, str]] = field(default_factory=list)
    link_pattern: str | None = None
    # If True, stop trying direct URLs after ``direct_hits`` successes (e.g. only need the
    # latest two releases, not every quarter we guessed).
    direct_hits: int | None = None
    # BCEData tables (id_grupo) to sample: the bundle is fetched first, then one grid using
    # the bundle's own frequency, unit and full range, exactly as the library client will.
    api_tables: list[int] = field(default_factory=list)
    # Deferred datasets: landing pages only, so the follow-up phase has something to look at.
    note: str = ""


SPANISH_MONTHS = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}  # fmt: skip


def _recent_months(n: int, today: date | None = None) -> list[pd.Period]:
    last_finished = pd.Period(today or date.today(), freq="M") - 1
    return [last_finished - i for i in range(n)]


def _recent_quarters(n: int, today: date | None = None) -> list[pd.Period]:
    last_finished = pd.Period(today or date.today(), freq="Q") - 1
    return [last_finished - i for i in range(n)]


def recipes(today: date | None = None) -> list[Recipe]:
    quarters = _recent_quarters(6, today)
    anchor = pd.Period("2025Q2", freq="Q")
    if anchor not in quarters:
        quarters.append(anchor)  # known-good release, confirms the bulletin numbering

    contenido = "https://contenido.bce.fin.ec/"
    api = contenido + "wp-json/bcedata/v1"
    tasas = contenido + "documentos/Estadisticas/SectorMonFin/TasasInteres/"
    inec = "https://www.ecuadorencifras.gob.ec/"
    spreadsheets = r"(?i)\.(xlsx?|csv)$"

    return [
        Recipe(
            provider="bce",
            dataset="bcedata",
            # BCE's data portal (BCEData) exposes a WordPress REST API (no auth for GET).
            # Tables sampled: 63 IPC, 49/50/51 interest rates, 2 balance of payments (remesas),
            # 68 labour market (ENEMDU, deferred), 90 GDP by expenditure, 35 the app default.
            pages=[
                ("rest_index.json", api),
                ("tree.json", api + "/tree"),
                # Second unit / frequency of tables whose default was already sampled.
                (
                    "grid_63_porcentaje.json",
                    api + "/grid?id_grupo=63&frecuencia=Mensual&unidad=Porcentaje"
                    "&desde=2005-02&hasta=2026-12",
                ),
                (
                    "grid_49_mensual.json",
                    api + "/grid?id_grupo=49&frecuencia=Mensual&unidad=Porcentaje"
                    "&desde=2015-01&hasta=2026-12",
                ),
            ],
            api_tables=[63, 49, 50, 51, 2, 68, 90, 35],
            note="API discovery",
        ),
        Recipe(
            provider="bce",
            dataset="pib_trimestral",
            direct=[
                (bce_fetch.filename_for("tou", q), bce_fetch.url_for("tou", q)) for q in quarters
            ],
            direct_hits=2,
        ),
        Recipe(
            provider="bce",
            dataset="remesas",
            # Stable file names (no date in them) under the old statistics folder.
            direct=[
                (
                    name,
                    contenido
                    + "documentos/Estadisticas/SectorExterno/BalanzaPagos/Remesas/"
                    + name,
                )
                for name in (
                    "Flujo_de_remesas_de_trabajadores.xlsx",
                    "Serie_hist%C3%B3rica_remesas_de_trabajadores.xlsx",
                )
            ],
            pages=[
                ("series_de_datos.html", contenido + "series-de-datos-remesas-de-trabajadores/")
            ],
            link_pattern=r"(?i)remesas.*\.xlsx$",
        ),
        Recipe(
            provider="bce",
            dataset="tasas_interes",
            pages=[
                ("indice.html", tasas + "Indice.htm"),
                ("historico.html", tasas + "TasasHistorico.htm"),
                # Monthly "rates in force" pages, one per month since 2007-08. Samples to see
                # how the layout evolved.
                ("TasasVigentes092026.html", tasas + "TasasVigentes092026.htm"),
                ("TasasVigentes012020.html", tasas + "TasasVigentes012020.htm"),
                ("TasasVigentes012015.html", tasas + "TasasVigentes012015.htm"),
                ("TasasVigentes012010.html", tasas + "TasasVigentes012010.htm"),
                ("TasasVigentes082007.html", tasas + "TasasVigentes082007.htm"),
            ],
            link_pattern=spreadsheets,
        ),
        Recipe(
            provider="inec",
            dataset="ipc",
            # INEC's own IPC page is broken (its download iframe 404s, also in a browser) and
            # twelve file-name guesses based on the 2018 and 2026 conventions all 404. Only the
            # landing page is kept, in case INEC repairs it; the recorder follows the iframe.
            pages=[("landing.html", inec + "indice-de-precios-al-consumidor/")],
            link_pattern=r"(?i)(serie|hist|ipc|inflacion|tabulado).*\.(xlsx?|csv)$",
        ),
        Recipe(
            provider="inec",
            dataset="enemdu",
            pages=[
                ("landing.html", inec + "enemdu-2025/"),
                (
                    "landing_general.html",
                    inec + "empleo-encuesta-nacional-de-empleo-desempleo-y-subempleo-enemdu/",
                ),
            ],
            note="deferred: landing pages only",
        ),
        Recipe(
            provider="inec",
            dataset="pobreza",
            pages=[("landing_general.html", inec + "pobreza-y-desigualdad/")],
            note="deferred: landing pages only",
        ),
    ]


# --------------------------------------------------------------------------------------------
# Recorder
# --------------------------------------------------------------------------------------------


def _expected_magic(filename: str) -> bytes | None:
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        return XLSX_MAGIC
    if lower.endswith(".xls"):
        return XLS_MAGIC
    return None


def _looks_like_html(response: httpx.Response) -> bool:
    """True for HTML, XML, JSON or JavaScript: anything worth saving as a text "page"."""
    content_type = response.headers.get("content-type", "")
    if any(kind in content_type for kind in ("html", "xml", "json", "javascript")):
        return True
    head = response.content[:512].lstrip()
    return head.startswith((b"<", b"{", b"[", b"var ", b"(function", b"!function", b"/*"))


@dataclass
class Attempt:
    provider: str
    dataset: str
    url: str
    outcome: str  # saved | skipped_existing | http_<code> | not_xlsx | blocked | error
    saved_as: str | None = None
    final_url: str | None = None
    status: int | None = None
    content_type: str | None = None
    bytes: int | None = None
    sha256: str | None = None
    error: str | None = None
    elapsed_s: float | None = None
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Recorder:
    def __init__(self, user_agent: str, delay: float, force: bool, dry_run: bool) -> None:
        self.delay = delay
        self.force = force
        self.dry_run = dry_run
        self.blocked_hosts: set[str] = set()
        self.attempts: list[Attempt] = []
        self._last_request = 0.0
        self.client = httpx.Client(
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "es-EC,es;q=0.9,en;q=0.8",
            },
            timeout=TIMEOUT,
            follow_redirects=True,
        )

    # -- HTTP ---------------------------------------------------------------------------------

    def _throttle(self, host: str) -> None:
        delay = max(self.delay, HOST_DELAY.get(host, 0.0))
        wait = self._last_request + delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def get(self, recipe: Recipe, url: str) -> tuple[httpx.Response | None, Attempt]:
        host = urlparse(url).netloc
        attempt = Attempt(recipe.provider, recipe.dataset, url, outcome="blocked")
        if host in self.blocked_hosts:
            attempt.error = f"{host} marked as blocked earlier in this run"
            return None, attempt
        if self.dry_run:
            attempt.outcome = "dry_run"
            return None, attempt
        started = time.monotonic()
        for retry in (False, True):
            self._throttle(host)
            try:
                response = self.client.get(url)
                break
            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ReadTimeout) as exc:
                # contenido.bce.fin.ec drops connections at random; one retry usually works.
                attempt.outcome = "error"
                attempt.error = f"{type(exc).__name__}: {exc}"
                if retry:
                    attempt.elapsed_s = round(time.monotonic() - started, 1)
                    return None, attempt
                # The throttle at the top of the loop spaces out the retry.
            except Exception as exc:  # a probe must never abort the whole run
                attempt.outcome = "error"
                attempt.error = f"{type(exc).__name__}: {exc}"
                attempt.elapsed_s = round(time.monotonic() - started, 1)
                if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
                    self.blocked_hosts.add(host)
                    attempt.error += " (host marked as blocked for the rest of this run)"
                return None, attempt
        attempt.elapsed_s = round(time.monotonic() - started, 1)
        attempt.status = response.status_code
        attempt.final_url = str(response.url)
        attempt.content_type = response.headers.get("content-type")
        attempt.bytes = len(response.content)
        # A 403 on a folder URL is the server refusing to list a directory, not an IP block.
        if response.status_code in BLOCKING_STATUSES and not url.endswith("/"):
            self.blocked_hosts.add(host)
            attempt.outcome = "blocked"
            attempt.error = f"HTTP {response.status_code}; host marked as blocked for this run"
            return None, attempt
        if response.status_code != 200:
            attempt.outcome = f"http_{response.status_code}"
            if "json" in (attempt.content_type or ""):
                attempt.error = response.text[:300]
            return None, attempt
        attempt.outcome = "ok"
        return response, attempt

    # -- Saving -------------------------------------------------------------------------------

    def _target(self, recipe: Recipe, filename: str) -> Path:
        return FIXTURES / recipe.provider / recipe.dataset / filename

    def _save(self, attempt: Attempt, target: Path, content: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        attempt.outcome = "saved"
        attempt.saved_as = target.relative_to(FIXTURES).as_posix()
        attempt.sha256 = hashlib.sha256(content).hexdigest()

    def _existing(self, recipe: Recipe, filename: str, url: str) -> Attempt | None:
        target = self._target(recipe, filename)
        if self.force or not target.exists():
            return None
        return Attempt(
            recipe.provider,
            recipe.dataset,
            url,
            outcome="skipped_existing",
            saved_as=target.relative_to(FIXTURES).as_posix(),
            bytes=target.stat().st_size,
            sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        )

    def record_file(self, recipe: Recipe, filename: str, url: str) -> Attempt:
        """Download a data file (xlsx expected) and save it if it really is one."""
        if existing := self._existing(recipe, filename, url):
            return self._log(existing)
        response, attempt = self.get(recipe, url)
        if response is not None:
            expected = _expected_magic(filename)
            if expected and not response.content.startswith(expected):
                attempt.outcome = "not_xlsx"
                attempt.error = f"body starts with {response.content[:12]!r}"
            else:
                self._save(attempt, self._target(recipe, filename), response.content)
        return self._log(attempt)

    def record_page(self, recipe: Recipe, filename: str, url: str) -> tuple[str | None, Attempt]:
        """Download an HTML page and save it. Returns the text for link discovery."""
        # Pages are always re-downloaded: they are small and their links change every release
        # (INEC renames the IPC iframe each month), so a stale copy would mislead discovery.
        target = self._target(recipe, filename)
        response, attempt = self.get(recipe, url)
        if response is None:
            return None, self._log(attempt)
        if not _looks_like_html(response):
            # e.g. the BCE "landing page" that is really a JPEG.
            attempt.outcome = "not_html"
            attempt.error = f"body starts with {response.content[:12]!r}"
            return None, self._log(attempt)
        self._save(attempt, target, response.content)
        self._log(attempt)
        return response.text, attempt

    # -- Discovery ----------------------------------------------------------------------------

    @staticmethod
    def meta_refresh(page_html: str, base_url: str) -> str | None:
        """Target of a ``<meta http-equiv="refresh" content="0;url=...">`` redirect, if any."""
        match = re.search(
            r"""<meta[^>]+http-equiv\s*=\s*["']?refresh["']?[^>]*content\s*=\s*["']\s*\d+\s*;\s*(?:url\s*=\s*)?([^"'>]+)["']""",
            page_html,
            flags=re.I,
        ) or re.search(
            r"""<meta[^>]+content\s*=\s*["']\s*\d+\s*;\s*(?:url\s*=\s*)?([^"'>]+)["'][^>]*http-equiv\s*=\s*["']?refresh""",
            page_html,
            flags=re.I,
        )
        return urljoin(base_url, html.unescape(match[1]).strip()) if match else None

    @staticmethod
    def iframes(page_html: str, base_url: str) -> list[str]:
        """Absolute URLs of ``<iframe src>`` in ``page_html``. INEC hides download lists there."""
        found: list[str] = []
        for src in re.findall(r"""<iframe[^>]+src\s*=\s*["']([^"']+)["']""", page_html, flags=re.I):
            absolute = urljoin(base_url, html.unescape(src).strip())
            if absolute not in found:
                found.append(absolute)
        return found

    @staticmethod
    def discover(page_html: str, base_url: str, pattern: str) -> list[str]:
        """Absolute http(s) URLs of links in ``page_html`` whose path matches ``pattern``."""
        regex = re.compile(pattern)
        found: list[str] = []
        for href in re.findall(r"""href\s*=\s*["']([^"']+)["']""", page_html, flags=re.I):
            href = html.unescape(href).strip()
            if "\\" in href:
                continue  # Windows share path, not a URL
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            # BCE pages contain links to internal file shares (\\SERVER\share\file.xls); skip
            # anything that is not a web URL.
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                continue
            if regex.search(unquote(parsed.path)) and absolute not in found:
                found.append(absolute)
        return found

    # -- Orchestration ------------------------------------------------------------------------

    def run(self, recipe: Recipe) -> None:
        print(
            f"\n=== {recipe.provider}/{recipe.dataset}"
            + (f"  ({recipe.note})" if recipe.note else "")
        )
        hits = 0
        for filename, url in recipe.direct:
            attempt = self.record_file(recipe, filename, url)
            if attempt.outcome in {"saved", "skipped_existing"}:
                hits += 1
                if recipe.direct_hits and hits >= recipe.direct_hits:
                    print(f"    (have {hits} releases, not trying older quarters)")
                    break

        for id_grupo in recipe.api_tables:
            self.record_api_table(recipe, id_grupo)

        discovered: list[str] = []
        pages = list(recipe.pages)
        seen_pages: set[str] = set()
        while pages:
            filename, url = pages.pop(0)
            if url in seen_pages:
                continue
            seen_pages.add(url)
            text, _ = self.record_page(recipe, filename, url)
            if not text:
                continue
            # Follow meta-refresh redirects (old BCE index pages) and embedded frames one level
            # down; their links count as discovered too.
            if (target := self.meta_refresh(text, url)) and target not in seen_pages:
                pages.append(
                    (
                        "redirect_"
                        + (unquote(urlparse(target).path.rsplit("/", 1)[-1]) or "index.html"),
                        target,
                    )
                )
            for frame in self.iframes(text, url):
                frame_path = unquote(urlparse(frame).path).lower()
                is_document = frame_path.endswith((".pdf", ".docx", ".doc", ".xlsx", ".xls"))
                if urlparse(frame).netloc == urlparse(url).netloc and not is_document:
                    frame_name = "iframe_" + (
                        unquote(urlparse(frame).path.rsplit("/", 1)[-1]) or "index.html"
                    )
                    pages.append((frame_name, frame))
            if recipe.link_pattern:
                for link in self.discover(text, url, recipe.link_pattern):
                    if link not in discovered:
                        discovered.append(link)

        if discovered:
            print(f"    discovered {len(discovered)} links; downloading up to {MAX_DISCOVERED}")
            known = {url for _, url in recipe.direct}
            for link in [d for d in discovered if d not in known][:MAX_DISCOVERED]:
                filename = unquote(urlparse(link).path.rsplit("/", 1)[-1]) or "download"
                self.record_file(recipe, filename, link)
            # Keep the full list for later, even the ones we did not download.
            links_path = self._target(recipe, "discovered_links.txt")
            links_path.parent.mkdir(parents=True, exist_ok=True)
            links_path.write_text("\n".join(discovered) + "\n", encoding="utf-8")

    def record_api_table(self, recipe: Recipe, id_grupo: int) -> None:
        """Record ``bundle/<id>`` and one ``grid`` call built from what the bundle says."""
        api = BCEDATA_API
        text, _ = self.record_page(recipe, f"bundle_{id_grupo}.json", f"{api}/bundle/{id_grupo}")
        if not text:
            return
        try:
            bundle = json.loads(text)
            freq = bundle["frecuencias"][0]
            unit = bundle["unidades"][freq][0]
            rng = bundle.get("range_by_freq", {}).get(freq) or bundle["range"]
            desde, hasta = rng["minYm"], rng["maxYm"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            print(f"    bundle {id_grupo}: cannot build a grid request ({exc})")
            return
        params = urlencode(
            {
                "id_grupo": id_grupo,
                "frecuencia": freq,
                "unidad": unit,
                "desde": desde,
                "hasta": hasta,
            }
        )
        self.record_page(recipe, f"grid_{id_grupo}.json", f"{api}/grid?{params}")

    def _log(self, attempt: Attempt) -> Attempt:
        self.attempts.append(attempt)
        detail = attempt.saved_as or attempt.error or ""
        if attempt.status and attempt.outcome not in {"saved", "skipped_existing"}:
            detail = f"HTTP {attempt.status} {attempt.content_type or ''} {detail}".strip()
        print(
            f"  [{attempt.outcome:<16}] {attempt.url}\n{'':21}{detail}"
            if detail
            else f"  [{attempt.outcome:<16}] {attempt.url}"
        )
        return attempt


# --------------------------------------------------------------------------------------------
# Manifest and CLI
# --------------------------------------------------------------------------------------------


def update_manifest(attempts: Iterable[Attempt], user_agent: str) -> None:
    previous: dict = {}
    if MANIFEST.exists():
        try:
            previous = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except ValueError:
            previous = {}
    # One entry per URL; newest attempt wins, unless the new one was a skip of an existing file.
    by_url: dict[str, dict] = {a["url"]: a for a in previous.get("attempts", [])}
    for attempt in attempts:
        entry = asdict(attempt)
        if attempt.outcome in {"skipped_existing", "dry_run"} and attempt.url in by_url:
            continue
        by_url[attempt.url] = entry
    manifest = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "user_agent": user_agent,
        "attempts": sorted(by_url.values(), key=lambda a: (a["provider"], a["dataset"], a["url"])),
    }
    FIXTURES.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def summary(attempts: list[Attempt], blocked: set[str]) -> None:
    print("\n=== Summary")
    counts: dict[str, int] = {}
    for attempt in attempts:
        counts[attempt.outcome] = counts.get(attempt.outcome, 0) + 1
    for outcome, count in sorted(counts.items()):
        print(f"  {outcome:<16} {count}")
    if blocked:
        print(f"\n  Blocked hosts: {', '.join(sorted(blocked))}")
        print(
            "  Wait a while, then rerun (optionally with --user-agent browser or a larger --delay)."
        )
        print("  Already recorded files are skipped, so only the missing ones will be attempted.")
    print(f"\n  Manifest: {MANIFEST}")
    print(f"  Please share the whole {FIXTURES}/ folder.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--provider", nargs="*", choices=["bce", "inec"], help="only these providers"
    )
    parser.add_argument("--dataset", nargs="*", help="only these datasets (e.g. ipc remesas)")
    parser.add_argument("--user-agent", choices=list(USER_AGENTS), default="ecuadata")
    parser.add_argument(
        "--delay", type=float, default=3.0, help="seconds between requests (default 3)"
    )
    parser.add_argument("--force", action="store_true", help="re-download files that already exist")
    parser.add_argument("--dry-run", action="store_true", help="list what would be requested")
    parser.add_argument("--list", action="store_true", help="print the recipes and exit")
    args = parser.parse_args(argv)

    selected = [
        r
        for r in recipes()
        if (not args.provider or r.provider in args.provider)
        and (not args.dataset or r.dataset in args.dataset)
    ]
    if args.list:
        for r in selected:
            print(f"{r.provider}/{r.dataset}: {len(r.direct)} urls, {len(r.pages)} pages {r.note}")
        return 0
    if not selected:
        print("Nothing selected.", file=sys.stderr)
        return 2

    user_agent = USER_AGENTS[args.user_agent]
    recorder = Recorder(user_agent, args.delay, args.force, args.dry_run)
    try:
        for recipe in selected:
            recorder.run(recipe)
    except KeyboardInterrupt:
        print("\nInterrupted; writing what we have to the manifest.")
    finally:
        if not args.dry_run:
            update_manifest(recorder.attempts, user_agent)
        summary(recorder.attempts, recorder.blocked_hosts)
    return 0


if __name__ == "__main__":
    sys.exit(main())

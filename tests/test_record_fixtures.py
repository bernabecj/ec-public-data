"""Tests for scripts/record_fixtures.py, run entirely against a mock transport."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pandas as pd
import pytest

from ecuadata.bce import fetch as bce_fetch

SCRIPT = Path(__file__).parent.parent / "scripts" / "record_fixtures.py"
XLSX = b"PK\x03\x04 workbook"
HTML = b"<html>Not found</html>"


@pytest.fixture(scope="module")
def rf():
    spec = importlib.util.spec_from_file_location("record_fixtures", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve string annotations via sys.modules
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fixtures_dir(rf, tmp_path, monkeypatch):
    monkeypatch.setattr(rf, "FIXTURES", tmp_path)
    monkeypatch.setattr(rf, "MANIFEST", tmp_path / "manifest.json")
    return tmp_path


@pytest.fixture
def recorder(rf, fixtures_dir):
    """Build a Recorder whose requests go to ``handler``; returns (recorder, requests seen)."""

    def build(handler, **kwargs):
        seen: list[str] = []

        def recording(request):
            seen.append(str(request.url))
            return handler(request)

        options = {"user_agent": "test", "delay": 0, "force": False, "dry_run": False}
        options.update(kwargs)
        rec = rf.Recorder(**options)
        rec.client = httpx.Client(transport=httpx.MockTransport(recording), follow_redirects=True)
        return rec, seen

    return build


def recipe(rf, **kwargs):
    defaults = {"provider": "bce", "dataset": "demo"}
    defaults.update(kwargs)
    return rf.Recipe(**defaults)


# -- Link discovery --------------------------------------------------------------------------


def test_discover_resolves_and_filters_links(rf):
    page = """
        <a href="/documentos/SERIE%20HISTORICA%20IPC_sep_2025.xlsx">serie</a>
        <a href='https://other.gob.ec/ipc.xls'>old format</a>
        <a href="boletin.pdf">pdf</a>
        <a href="/documentos/SERIE%20HISTORICA%20IPC_sep_2025.xlsx">duplicate</a>
        <a href="https://x.gob.ec/a.xlsx?x=1&amp;y=2">entity</a>
    """
    links = rf.Recorder.discover(page, "https://www.ecuadorencifras.gob.ec/ipc/", r"\.xlsx?$")
    assert links == [
        "https://www.ecuadorencifras.gob.ec/documentos/SERIE%20HISTORICA%20IPC_sep_2025.xlsx",
        "https://other.gob.ec/ipc.xls",
        "https://x.gob.ec/a.xlsx?x=1&y=2",
    ]


def test_discover_matches_pattern_against_decoded_path(rf):
    page = '<a href="/Inflacion/SERIE%20HISTORICA%20IPC.xlsx">a</a><a href="/otro.xlsx">b</a>'
    links = rf.Recorder.discover(page, "https://inec.gob.ec/", r"(?i)serie.*\.xlsx$")
    assert links == ["https://inec.gob.ec/Inflacion/SERIE%20HISTORICA%20IPC.xlsx"]


# -- Recording single files ------------------------------------------------------------------


def test_record_file_saves_real_xlsx(rf, recorder, fixtures_dir):
    rec, _ = recorder(lambda request: httpx.Response(200, content=XLSX))
    attempt = rec.record_file(recipe(rf), "a.xlsx", "https://h.ec/a.xlsx")
    assert attempt.outcome == "saved"
    assert attempt.saved_as == "bce/demo/a.xlsx"
    assert (fixtures_dir / "bce" / "demo" / "a.xlsx").read_bytes() == XLSX
    assert attempt.sha256 and attempt.bytes == len(XLSX)


def test_record_file_rejects_html_served_as_xlsx(rf, recorder, fixtures_dir):
    rec, _ = recorder(
        lambda request: httpx.Response(200, content=HTML, headers={"content-type": "text/html"})
    )
    attempt = rec.record_file(recipe(rf), "a.xlsx", "https://h.ec/a.xlsx")
    assert attempt.outcome == "not_xlsx"
    assert attempt.content_type == "text/html"
    assert not (fixtures_dir / "bce" / "demo" / "a.xlsx").exists()


def test_record_file_logs_http_errors_without_saving(rf, recorder, fixtures_dir):
    rec, _ = recorder(lambda request: httpx.Response(404))
    attempt = rec.record_file(recipe(rf), "a.xlsx", "https://h.ec/a.xlsx")
    assert attempt.outcome == "http_404"
    assert attempt.status == 404
    assert not list(fixtures_dir.rglob("*.xlsx"))


def test_record_file_records_redirect_target(rf, recorder):
    def handler(request):
        if request.url.path == "/old.xlsx":
            return httpx.Response(301, headers={"location": "https://h.ec/new.xlsx"})
        return httpx.Response(200, content=XLSX)

    rec, _ = recorder(handler)
    attempt = rec.record_file(recipe(rf), "old.xlsx", "https://h.ec/old.xlsx")
    assert attempt.outcome == "saved"
    assert attempt.final_url == "https://h.ec/new.xlsx"


def test_record_page_saves_html_and_returns_text(rf, recorder, fixtures_dir):
    rec, _ = recorder(lambda request: httpx.Response(200, content=b"<a href='x.xlsx'>x</a>"))
    text, attempt = rec.record_page(recipe(rf), "landing.html", "https://h.ec/")
    assert attempt.outcome == "saved"
    assert "x.xlsx" in text
    assert (fixtures_dir / "bce" / "demo" / "landing.html").exists()


# -- Resume and force ------------------------------------------------------------------------


def test_existing_file_is_skipped_without_network(rf, recorder, fixtures_dir):
    target = fixtures_dir / "bce" / "demo" / "a.xlsx"
    target.parent.mkdir(parents=True)
    target.write_bytes(XLSX)
    rec, seen = recorder(lambda request: httpx.Response(200, content=b"PK\x03\x04 newer"))
    attempt = rec.record_file(recipe(rf), "a.xlsx", "https://h.ec/a.xlsx")
    assert attempt.outcome == "skipped_existing"
    assert seen == []
    assert target.read_bytes() == XLSX


def test_force_redownloads_existing_file(rf, recorder, fixtures_dir):
    target = fixtures_dir / "bce" / "demo" / "a.xlsx"
    target.parent.mkdir(parents=True)
    target.write_bytes(XLSX)
    rec, seen = recorder(
        lambda request: httpx.Response(200, content=b"PK\x03\x04 newer"), force=True
    )
    attempt = rec.record_file(recipe(rf), "a.xlsx", "https://h.ec/a.xlsx")
    assert attempt.outcome == "saved"
    assert len(seen) == 1
    assert target.read_bytes() == b"PK\x03\x04 newer"


def test_pages_are_always_refreshed_even_if_recorded(rf, recorder, fixtures_dir):
    """Landing pages change every release, so a stale copy must never drive discovery."""
    page = fixtures_dir / "bce" / "demo" / "landing.html"
    page.parent.mkdir(parents=True)
    page.write_text('<a href="stale.xlsx">f</a>', encoding="utf-8")

    def handler(request):
        if request.url.path == "/":
            return httpx.Response(200, content=b'<a href="fresh.xlsx">f</a>')
        return httpx.Response(200, content=XLSX)

    rec, seen = recorder(handler)
    rec.run(recipe(rf, pages=[("landing.html", "https://h.ec/")], link_pattern=r"\.xlsx$"))
    assert seen == ["https://h.ec/", "https://h.ec/fresh.xlsx"]
    assert "fresh.xlsx" in page.read_text(encoding="utf-8")


def test_iframes_to_documents_are_not_followed(rf, recorder):
    page = (
        b'<iframe src="/viewer/Tasas_Enero_2026.pdf"></iframe>'
        b'<iframe src="https://other.ec/embed.html"></iframe>'
        b'<iframe src="/ipc_oct.html"></iframe>'
    )

    def handler(request):
        return httpx.Response(200, content=page if request.url.path == "/" else b"<html></html>")

    rec, seen = recorder(handler)
    rec.run(recipe(rf, pages=[("landing.html", "https://h.ec/")], link_pattern=r"\.xlsx$"))
    assert seen == ["https://h.ec/", "https://h.ec/ipc_oct.html"]


# -- Blocking behaviour ----------------------------------------------------------------------


@pytest.mark.parametrize("status", [403, 429])
def test_blocking_status_stops_further_requests_to_host(rf, recorder, status):
    rec, seen = recorder(lambda request: httpx.Response(status))
    r = recipe(rf)
    first = rec.record_file(r, "a.xlsx", "https://blocked.ec/a.xlsx")
    second = rec.record_file(r, "b.xlsx", "https://blocked.ec/b.xlsx")
    other = rec.record_file(r, "c.xlsx", "https://other.ec/c.xlsx")
    assert first.outcome == "blocked" and first.status == status
    assert second.outcome == "blocked" and second.status is None  # never requested
    assert other.outcome == "blocked" and other.status == status  # other hosts still tried
    assert seen == ["https://blocked.ec/a.xlsx", "https://other.ec/c.xlsx"]
    assert rec.blocked_hosts == {"blocked.ec", "other.ec"}


def test_connect_error_marks_host_blocked(rf, recorder):
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)

    rec, seen = recorder(refuse)
    r = recipe(rf)
    first = rec.record_file(r, "a.xlsx", "https://down.ec/a.xlsx")
    second = rec.record_file(r, "b.xlsx", "https://down.ec/b.xlsx")
    assert first.outcome == "error" and "ConnectError" in first.error
    assert second.outcome == "blocked"
    assert len(seen) == 1


def test_read_timeout_is_retried_once_and_does_not_block_host(rf, recorder):
    def slow(request):
        raise httpx.ReadTimeout("slow", request=request)

    rec, seen = recorder(slow)
    r = recipe(rf)
    rec.record_file(r, "a.xlsx", "https://slow.ec/a.xlsx")
    second = rec.record_file(r, "b.xlsx", "https://slow.ec/b.xlsx")
    assert second.outcome == "error"
    assert len(seen) == 4  # each URL tried twice
    assert not rec.blocked_hosts


def test_server_disconnect_recovers_on_retry(rf, recorder):
    calls = {"n": 0}

    def flaky(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.RemoteProtocolError("Server disconnected", request=request)
        return httpx.Response(200, content=XLSX)

    rec, seen = recorder(flaky)
    attempt = rec.record_file(recipe(rf), "a.xlsx", "https://flaky.ec/a.xlsx")
    assert attempt.outcome == "saved"
    assert len(seen) == 2


def test_discover_skips_windows_share_paths(rf):
    page = (
        '<a href="\\\\BCEQCLUSTER_VOL1_SERVER\\home1\\tasas\\TasaBasica.xls">share</a>'
        '<a href="/\\\\SERVER\\x.xls">share2</a>'
        '<a href="ok.xls">web</a>'
    )
    assert rf.Recorder.discover(page, "https://h.ec/", r"\.xls$") == ["https://h.ec/ok.xls"]


def test_dry_run_makes_no_requests(rf, recorder):
    rec, seen = recorder(lambda request: httpx.Response(200, content=XLSX), dry_run=True)
    attempt = rec.record_file(recipe(rf), "a.xlsx", "https://h.ec/a.xlsx")
    assert attempt.outcome == "dry_run"
    assert seen == []


# -- Recipe orchestration --------------------------------------------------------------------


def test_run_stops_guessing_after_enough_direct_hits(rf, recorder):
    rec, seen = recorder(lambda request: httpx.Response(200, content=XLSX))
    direct = [(f"f{i}.xlsx", f"https://h.ec/f{i}.xlsx") for i in range(6)]
    rec.run(recipe(rf, direct=direct, direct_hits=2))
    assert seen == ["https://h.ec/f0.xlsx", "https://h.ec/f1.xlsx"]


def test_run_keeps_guessing_past_failures(rf, recorder):
    def handler(request):
        return httpx.Response(200 if request.url.path.endswith("f3.xlsx") else 404, content=XLSX)

    rec, seen = recorder(handler)
    direct = [(f"f{i}.xlsx", f"https://h.ec/f{i}.xlsx") for i in range(6)]
    rec.run(recipe(rf, direct=direct, direct_hits=1))
    assert len(seen) == 4
    assert [a.outcome for a in rec.attempts] == ["http_404"] * 3 + ["saved"]


def test_run_discovers_downloads_and_lists_links(rf, recorder, fixtures_dir):
    page = (
        b'<a href="/d/SERIE%20IPC.xlsx">a</a><a href="/d/known.xlsx">k</a><a href="/d/x.pdf">p</a>'
    )

    def handler(request):
        if request.url.path == "/ipc/":
            return httpx.Response(200, content=page)
        return httpx.Response(200, content=XLSX)

    rec, seen = recorder(handler)
    rec.run(
        recipe(
            rf,
            provider="inec",
            dataset="ipc",
            direct=[("known.xlsx", "https://h.ec/d/known.xlsx")],
            pages=[("landing.html", "https://h.ec/ipc/")],
            link_pattern=r"\.xlsx$",
        )
    )
    # The direct URL is not downloaded twice via discovery; the discovered file keeps its name.
    assert seen == [
        "https://h.ec/d/known.xlsx",
        "https://h.ec/ipc/",
        "https://h.ec/d/SERIE%20IPC.xlsx",
    ]
    folder = fixtures_dir / "inec" / "ipc"
    assert (folder / "SERIE IPC.xlsx").read_bytes() == XLSX
    assert (folder / "discovered_links.txt").read_text().splitlines() == [
        "https://h.ec/d/SERIE%20IPC.xlsx",
        "https://h.ec/d/known.xlsx",
    ]


def test_run_caps_discovered_downloads(rf, recorder, monkeypatch):
    monkeypatch.setattr(rf, "MAX_DISCOVERED", 2)
    page = "".join(f'<a href="/f{i}.xlsx">x</a>' for i in range(10)).encode()

    def handler(request):
        return httpx.Response(200, content=page if request.url.path == "/" else XLSX)

    rec, seen = recorder(handler)
    rec.run(recipe(rf, pages=[("landing.html", "https://h.ec/")], link_pattern=r"\.xlsx$"))
    assert len(seen) == 3  # page + 2 files


# -- Manifest --------------------------------------------------------------------------------


def test_manifest_records_failures_and_merges_across_runs(rf, fixtures_dir):
    saved = rf.Attempt("bce", "d", "https://h.ec/a.xlsx", "saved", saved_as="bce/d/a.xlsx")
    failed = rf.Attempt("bce", "d", "https://h.ec/b.xlsx", "http_404", status=404)
    rf.update_manifest([saved, failed], "ua")

    skipped = rf.Attempt("bce", "d", "https://h.ec/a.xlsx", "skipped_existing")
    retried = rf.Attempt("bce", "d", "https://h.ec/b.xlsx", "saved", saved_as="bce/d/b.xlsx")
    rf.update_manifest([skipped, retried], "ua")

    manifest = json.loads((fixtures_dir / "manifest.json").read_text(encoding="utf-8"))
    by_url = {a["url"]: a for a in manifest["attempts"]}
    assert len(by_url) == 2
    assert by_url["https://h.ec/a.xlsx"]["outcome"] == "saved"  # skip did not overwrite
    assert by_url["https://h.ec/b.xlsx"]["outcome"] == "saved"  # retry replaced the failure
    assert manifest["user_agent"] == "ua"


def test_manifest_survives_corrupt_previous_file(rf, fixtures_dir):
    (fixtures_dir / "manifest.json").write_text("{not json", encoding="utf-8")
    rf.update_manifest([rf.Attempt("bce", "d", "https://h.ec/a.xlsx", "http_404")], "ua")
    assert json.loads((fixtures_dir / "manifest.json").read_text())["attempts"][0]["status"] is None


# -- Recipes ---------------------------------------------------------------------------------


def test_recipes_cover_phase_datasets(rf):
    names = {(r.provider, r.dataset) for r in rf.recipes()}
    assert {("bce", "pib_trimestral"), ("bce", "remesas"), ("bce", "tasas_interes")} <= names
    assert ("inec", "ipc") in names


def test_recipes_have_unique_filenames_and_absolute_urls(rf):
    for r in rf.recipes():
        names = [name for name, _ in r.direct + r.pages]
        assert len(names) == len(set(names)), r.dataset
        for _, url in r.direct + r.pages:
            assert url.startswith("https://"), url
        if r.pages and not r.note:
            assert r.link_pattern, f"{r.dataset} has pages but no link pattern"


def test_pib_recipe_uses_fetch_url_pattern_and_anchor(rf):
    from datetime import date

    pib = next(r for r in rf.recipes(today=date(2026, 10, 13)) if r.dataset == "pib_trimestral")
    urls = [url for _, url in pib.direct]
    assert urls[0] == bce_fetch.url_for("tou", pd.Period("2026Q3", freq="Q"))
    assert bce_fetch.url_for("tou", "2025Q2") in urls  # known-good anchor always probed


# -- CLI -------------------------------------------------------------------------------------


def test_cli_list_and_filters(rf, capsys):
    assert rf.main(["--list", "--dataset", "ipc"]) == 0
    out = capsys.readouterr().out
    assert "inec/ipc" in out and "bce/" not in out


def test_cli_nothing_selected(rf):
    assert rf.main(["--dataset", "nope"]) == 2


def test_cli_dry_run_writes_no_manifest(rf, fixtures_dir, capsys):
    assert rf.main(["--dry-run", "--dataset", "remesas"]) == 0
    assert not (fixtures_dir / "manifest.json").exists()
    assert "dry_run" in capsys.readouterr().out

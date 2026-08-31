"""Exporting and importing the quote archive between machines.

Two things matter here. The exported file must carry a format marker so a
future version can tell what it is reading - it carried none at all before.
And an import must never destroy a quote: every machine starts its series at
CC-YYYY-0001, so two colleagues almost certainly hold different quotes under
the same number.
"""
import json

from playwright.sync_api import sync_playwright

from harness import app_page, build_long_quote, serve


def _archive_of(page):
    return page.evaluate("loadArchive()")


def _import_file(page, path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    page.set_input_files("#importArchiveInput", str(path))
    page.wait_for_timeout(700)


def test_the_export_carries_a_format_marker(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            build_long_quote(page, 2)
            page.wait_for_timeout(700)
            page.click("#openArchiveBtn")
            with page.expect_download(timeout=30000) as dl:
                page.click("#exportArchiveBtn")
            out = tmp_path / "archive.json"
            dl.value.save_as(str(out))
            live = _archive_of(page)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["format"] == "cc-quote-archive"
    assert payload["format_version"] == 2
    assert payload["app_version"]
    assert payload["exported_at"]
    assert set(payload["quotes"].keys()) == set(live.keys())


def test_a_file_exported_before_the_format_marker_still_imports(tmp_path):
    """The old export was the bare store object. Those files exist on people's
    disks and in email threads; they must keep working."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            legacy = {
                "CC-2019-0042": {
                    "quote_id": "CC-2019-0042",
                    "saved_at": "2019-05-04T10:00:00.000Z",
                    "customer_name": "Legacy Customer",
                }
            }
            _import_file(page, tmp_path / "legacy.json", legacy)
            store = _archive_of(page)
    assert store["CC-2019-0042"]["customer_name"] == "Legacy Customer"


def test_a_file_from_a_newer_version_still_yields_its_quotes(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            future = {
                "format": "cc-quote-archive",
                "format_version": 99,
                "exported_at": "2030-01-01T00:00:00.000Z",
                "app_version": "9.9.9",
                "quotes": {
                    "CC-2030-0001": {
                        "quote_id": "CC-2030-0001",
                        "customer_name": "Future Customer",
                        "something_we_do_not_know_about": {"nested": True},
                    }
                },
            }
            _import_file(page, tmp_path / "future.json", future)
            store = _archive_of(page)
    assert store["CC-2030-0001"]["customer_name"] == "Future Customer"


def test_re_importing_your_own_backup_does_not_duplicate_anything(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            build_long_quote(page, 2)
            page.wait_for_timeout(700)
            before = _archive_of(page)
            payload = {
                "format": "cc-quote-archive",
                "format_version": 1,
                "exported_at": "2026-08-26T00:00:00.000Z",
                "app_version": "1.5.0",
                "quotes": before,
            }
            _import_file(page, tmp_path / "same.json", payload)
            after = _archive_of(page)
    assert set(after.keys()) == set(before.keys()), (
        "re-importing an identical backup created duplicates"
    )


def test_a_colliding_quote_is_kept_alongside_and_never_overwrites(tmp_path):
    """The one that matters. Two machines both hold CC-2026-0001, for different
    customers. Importing must not destroy the local one."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            build_long_quote(page, 2)
            page.fill("#custName", "My Own Customer")
            page.wait_for_timeout(700)
            my_id = page.evaluate("QUOTE_ID")
            theirs = {
                "format": "cc-quote-archive",
                "format_version": 1,
                "exported_at": "2026-08-26T00:00:00.000Z",
                "app_version": "1.5.0",
                "quotes": {
                    my_id: {
                        "quote_id": my_id,
                        "saved_at": "2026-08-01T00:00:00.000Z",
                        "customer_name": "Their Different Customer",
                    }
                },
            }
            _import_file(page, tmp_path / "theirs.json", theirs)
            store = _archive_of(page)
    assert store[my_id]["customer_name"] == "My Own Customer", (
        "the imported quote overwrote a local one"
    )
    kept = [k for k, v in store.items() if v.get("customer_name") == "Their Different Customer"]
    assert kept, "the imported quote was dropped instead of being kept alongside"
    assert kept[0] != my_id


def test_a_file_that_is_not_an_archive_is_refused_and_changes_nothing(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            build_long_quote(page, 2)
            page.wait_for_timeout(700)
            before = _archive_of(page)
            path = tmp_path / "junk.json"
            path.write_text("[1, 2, 3]", encoding="utf-8")
            page.set_input_files("#importArchiveInput", str(path))
            page.wait_for_timeout(700)
            after = _archive_of(page)
    assert after == before, "a junk file changed the archive"
    assert any("archive" in a.lower() for a in alerts), f"no clear refusal: {alerts}"

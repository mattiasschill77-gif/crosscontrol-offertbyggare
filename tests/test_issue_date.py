import re
from playwright.sync_api import sync_playwright

from harness import app_page, build_long_quote, download_quote_pdf, page_texts, serve


def _open(p, url):
    return app_page(p, url)


def test_issue_date_defaults_to_today():
    with serve() as url, sync_playwright() as p:
        with _open(p, url) as (page, _alerts):
            today = page.evaluate("new Date().toISOString().slice(0,10)")
            assert page.input_value("#issueDate") == today


def test_a_chosen_issue_date_reaches_the_screen_and_the_pdf(tmp_path):
    out = tmp_path / "dated.pdf"
    with serve() as url, sync_playwright() as p:
        with _open(p, url) as (page, alerts):
            build_long_quote(page, 2)
            page.fill("#issueDate", "2026-03-04")
            page.wait_for_timeout(400)
            on_screen = page.inner_text("#docRoot")
            export = page.evaluate("buildExportObj()")
            download_quote_pdf(page, alerts, out)
    in_pdf = " ".join(re.sub(r"\s+", " ", t) for t in page_texts(out))
    assert export["issued_date"] in on_screen, "screen and export disagree on the issue date"
    assert export["issued_date"] in in_pdf, "the PDF did not get the chosen issue date"
    assert "2026" in export["issued_date"]


def test_validity_is_counted_from_the_issue_date_not_from_today():
    with serve() as url, sync_playwright() as p:
        with _open(p, url) as (page, _alerts):
            page.select_option("#termValidity", "30")
            page.fill("#issueDate", "2026-03-04")
            page.wait_for_timeout(400)
            export = page.evaluate("buildExportObj()")
    # fmtDate uses en-GB with 2-digit day/month/numeric year (verified by reading
    # fmtDate's source), so 2026-03-04 + 30 days is fully determined: 2026-04-03.
    assert export["issued_date"] == "04/03/2026"
    assert export["valid_until"] == "03/04/2026"


def test_the_warning_is_internal_only(tmp_path):
    out = tmp_path / "future.pdf"
    with serve() as url, sync_playwright() as p:
        with _open(p, url) as (page, alerts):
            build_long_quote(page, 2)
            page.fill("#issueDate", "2027-12-31")
            page.wait_for_timeout(400)
            note = page.inner_text("#issueDateNote")
            doc = page.inner_text("#docRoot")
            download_quote_pdf(page, alerts, out)
    assert note.strip(), "no internal warning for a future issue date"
    assert note.strip() not in doc, "the warning leaked into the customer document"
    in_pdf = " ".join(page_texts(out))
    assert note.strip() not in in_pdf, "the warning leaked into the PDF"


def test_an_archived_quote_keeps_the_date_it_was_issued():
    """Before this, the archive stored no date and both renderers computed from
    TODAY, so a quote issued in August and reopened in November re-dated itself
    to November with a fresh validity window."""
    with serve() as url, sync_playwright() as p:
        with _open(p, url) as (page, _alerts):
            build_long_quote(page, 2)
            page.fill("#issueDate", "2026-03-04")
            page.wait_for_timeout(600)
            quote_id = page.evaluate("QUOTE_ID")
            saved = page.evaluate("buildQuoteSnapshot()")
            assert saved.get("issue_date") == "2026-03-04", "the archive record has no issue date"
            page.evaluate("saveArchiveStore(Object.assign(loadArchive(), {[QUOTE_ID]: buildQuoteSnapshot()}))")
            # Come back to it the way the archive panel does.
            page.fill("#issueDate", "2026-07-01")
            page.wait_for_timeout(400)
            page.evaluate("(id) => openQuote(id)", quote_id)
            page.wait_for_timeout(400)
            assert page.input_value("#issueDate") == "2026-03-04"


def test_a_record_saved_before_this_release_still_opens():
    """Records written before the issue date existed have no issue_date key.
    They must fall back to today rather than breaking or blanking the field."""
    with serve() as url, sync_playwright() as p:
        with _open(p, url) as (page, _alerts):
            today = page.evaluate("new Date().toISOString().slice(0,10)")
            page.evaluate("""() => {
                const store = loadArchive();
                const rec = buildQuoteSnapshot();
                delete rec.issue_date;
                rec.quote_id = 'CC-2026-9999';
                store['CC-2026-9999'] = rec;
                saveArchiveStore(store);
            }""")
            page.fill("#issueDate", "2026-03-04")
            page.wait_for_timeout(300)
            page.evaluate("openQuote('CC-2026-9999')")
            page.wait_for_timeout(400)
            assert page.input_value("#issueDate") == today


def test_a_new_quote_is_dated_today_again():
    """Starting a new quote must not inherit the previous quote's date."""
    with serve() as url, sync_playwright() as p:
        with _open(p, url) as (page, _alerts):
            today = page.evaluate("new Date().toISOString().slice(0,10)")
            page.fill("#issueDate", "2026-03-04")
            page.wait_for_timeout(400)
            page.evaluate("startNewQuote()")
            page.wait_for_timeout(400)
            assert page.input_value("#issueDate") == today

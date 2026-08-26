"""The quote number is editable, and cannot destroy an archived quote.

Zak's ask: CC-2026-0001 tells the customer they are the first quote of the
year. His own suggestion was the one built - default to what it does today,
make the box editable, the same pattern as the VAT note - which also gives
his year-month-customer-# format for free without a format system.

The hazard is the archive: it is keyed on the quote number, so an edit can
rename a record, orphan it, or overwrite a different quote entirely.
"""
from playwright.sync_api import sync_playwright

from harness import app_page, build_long_quote, download_quote_pdf, page_texts, serve


def test_the_number_defaults_to_the_generated_one():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            assert page.input_value("#currentQuoteId").startswith("CC-")


def test_a_typed_number_reaches_the_document_and_the_export(tmp_path):
    out = tmp_path / "renamed.pdf"
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            build_long_quote(page, 2)
            page.fill("#currentQuoteId", "2026-03-HUSCO-247")
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(500)
            export = page.evaluate("buildExportObj()")
            doc = page.inner_text("#docRoot")
            download_quote_pdf(page, alerts, out)
    assert export["quote_id"] == "2026-03-HUSCO-247"
    assert "2026-03-HUSCO-247" in doc
    assert "2026-03-HUSCO-247" in " ".join(page_texts(out))


def test_renaming_moves_the_archive_record_instead_of_duplicating_it():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            build_long_quote(page, 2)
            page.wait_for_timeout(700)
            old_id = page.evaluate("QUOTE_ID")
            page.fill("#currentQuoteId", "CC-2026-0500")
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(700)
            store = page.evaluate("loadArchive()")
    assert "CC-2026-0500" in store, "the renamed quote is not in the archive"
    assert old_id not in store, "the old record was left behind as a duplicate"


def test_an_existing_number_is_refused_and_nothing_is_lost():
    """The one that matters: typing a number that already exists must not
    overwrite that quote."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            build_long_quote(page, 2)
            page.fill("#custName", "First Customer")
            page.wait_for_timeout(700)
            first_id = page.evaluate("QUOTE_ID")
            page.evaluate("startNewQuote()")
            page.wait_for_timeout(500)
            build_long_quote(page, 2)
            page.fill("#custName", "Someone Else")
            page.wait_for_timeout(700)
            page.fill("#currentQuoteId", first_id)
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(700)
            store = page.evaluate("loadArchive()")
            still_mine = page.evaluate("QUOTE_ID")
            shown = page.input_value("#currentQuoteId")
    assert store[first_id]["customer_name"] == "First Customer", (
        "an archived quote was overwritten by reusing its number"
    )
    assert still_mine != first_id, "the duplicate number was accepted"
    assert shown == still_mine, "the field kept a number the app did not accept"


def test_a_higher_number_moves_the_counter():
    """Zak's point: set it once, not on every quote."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.fill("#currentQuoteId", "CC-2026-0500")
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(500)
            page.evaluate("startNewQuote()")
            page.wait_for_timeout(500)
            assert page.evaluate("QUOTE_ID") == "CC-2026-0501"


def test_a_lower_number_leaves_the_counter_alone():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.fill("#currentQuoteId", "CC-2026-0500")
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(500)
            page.evaluate("startNewQuote()")
            page.wait_for_timeout(500)
            page.fill("#currentQuoteId", "CC-2026-0002")
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(500)
            page.evaluate("startNewQuote()")
            page.wait_for_timeout(500)
            assert page.evaluate("QUOTE_ID") == "CC-2026-0502"


def test_a_path_character_does_not_break_the_export(tmp_path):
    """Free text means a number can contain a path character. Measured
    2026-08-26: Chrome sanitises its own suggested download name
    ("quote-CC_2026_0007.pdf"), so the app needs no sanitiser of its own - but
    the export must still complete, raise no alert, and the document must show
    the number exactly as the user typed it."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            build_long_quote(page, 2)
            page.fill("#currentQuoteId", "CC/2026/0007")
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(500)
            with page.expect_download(timeout=30000) as dl:
                page.click("#downloadPdfBtn")
            suggested = dl.value.suggested_filename
            dl.value.save_as(str(tmp_path / "slash.pdf"))
            doc = page.inner_text("#docRoot")
    assert not alerts, f"export alerted: {alerts}"
    assert "/" not in suggested and "\\" not in suggested, f"unsafe name: {suggested!r}"
    assert "CC/2026/0007" in doc, "the document must show the number exactly as typed"
    assert (tmp_path / "slash.pdf").stat().st_size > 0


def test_an_empty_number_is_refused():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            before = page.evaluate("QUOTE_ID")
            page.fill("#currentQuoteId", "")
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(400)
            assert page.evaluate("QUOTE_ID") == before
            assert page.input_value("#currentQuoteId") == before

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


def test_a_number_containing_markup_renders_identically_everywhere(tmp_path):
    """The number became free text, so it must be escaped like every other user
    field. Unescaped, the screen strips the tags while pdfmake prints them
    literally - the KAM checks the screen and the customer gets something else."""
    out = tmp_path / "markup.pdf"
    typed = "2026-08-<b>HUSCO</b>-14"
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            build_long_quote(page, 2)
            page.fill("#currentQuoteId", typed)
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(500)
            doc = page.inner_text("#docRoot")
            download_quote_pdf(page, alerts, out)
    in_pdf = " ".join(page_texts(out))
    assert typed in doc, f"the screen document changed the number: {doc[:200]!r}"
    assert typed in in_pdf, "the PDF and the screen disagree about the quote number"


def test_an_archived_number_containing_markup_cannot_run_code():
    """Archives are exported and imported between colleagues, so a hostile
    quote_id is not purely self-inflicted."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.evaluate("""() => {
                const store = loadArchive();
                const rec = buildQuoteSnapshot();
                rec.quote_id = '<img src=x onerror="window.__pwned=true">';
                store[rec.quote_id] = rec;
                saveArchiveStore(store);
                openQuote(rec.quote_id);
            }""")
            page.wait_for_timeout(500)
            assert page.evaluate("window.__pwned === true") is False


def test_an_absurd_number_cannot_wreck_the_counter():
    """parseInt is unbounded: 23 digits reach 1e+23, where n + 1 === n, so
    nextQuoteId() would return the same id forever and every new quote would
    overwrite the previous one in the archive."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.fill("#currentQuoteId", "CC-2026-99999999999999999999999")
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(500)
            page.evaluate("startNewQuote()")
            page.wait_for_timeout(400)
            first = page.evaluate("QUOTE_ID")
            page.evaluate("startNewQuote()")
            page.wait_for_timeout(400)
            second = page.evaluate("QUOTE_ID")
    assert first != second, f"two new quotes got the same number: {first!r}"
    assert "e+" not in first, f"the counter went floating point: {first!r}"


def test_minting_never_lands_on_a_number_already_in_the_archive():
    """An imported archive does not move the counter, so the series can walk
    straight into a colleague's quote."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.evaluate("""() => {
                const store = loadArchive();
                const rec = buildQuoteSnapshot();
                const year = new Date().getFullYear();
                rec.quote_id = `CC-${year}-0002`;
                rec.customer_name = 'IMPORTED CUSTOMER';
                store[rec.quote_id] = rec;
                saveArchiveStore(store);
            }""")
            for _ in range(3):
                page.evaluate("startNewQuote()")
                page.wait_for_timeout(300)
            store = page.evaluate("loadArchive()")
            year = page.evaluate("new Date().getFullYear()")
    key = f"CC-{year}-0002"
    assert store[key]["customer_name"] == "IMPORTED CUSTOMER", (
        "minting a new quote overwrote an archived one"
    )

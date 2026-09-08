"""The optional List Price column on the quote (v1.8.0).

Asked for by a colleague. Default ON, so a colleague who never finds the
checkbox sees the build they had.

Asserted on what the PDF actually contains, not on the checkbox's state: the
whole point is that the number leaves the document. The discount tag goes with
the column - a discount advertised off a price the customer can no longer see is
worse than either alone.
"""
from playwright.sync_api import sync_playwright

from harness import app_page, download_quote_pdf, page_texts, serve

PART = "C000 144-05"      # CCpilot VI
LIST_PRICE = "526.76"     # its list price
TIER_PRICE = "256.96"     # its 100-249 tier price


def _quote(page, show_list, discount=12):
    page.fill("#custName", "Caudwell Marine Ltd")
    page.evaluate(f"addProductToCart({PART!r})")
    page.wait_for_timeout(300)
    page.evaluate(
        "(d) => { const it = cart.find(c => c.partNumber === %r);"
        "  it.extraDiscountPct = d; renderAll(); }" % PART,
        discount,
    )
    page.set_checked("#showListPrice", show_list)
    page.wait_for_timeout(400)


def test_the_checkbox_is_checked_by_default():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            assert page.is_checked("#showListPrice")


def test_on_the_list_price_and_the_discount_tag_are_in_the_pdf(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            _quote(page, show_list=True)
            pdf = download_quote_pdf(page, alerts, tmp_path / "on.pdf")
    text = " ".join(page_texts(pdf))
    assert LIST_PRICE in text
    assert "negotiated discount" in text


def test_off_removes_both_from_the_pdf(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            _quote(page, show_list=False)
            # The printed unit price is the DISCOUNTED one (256.96 less 12%), not the
            # tier price - read it from the app rather than hardcoding, or the
            # non-vacuity check asserts a number the document never contained.
            unit = page.evaluate(
                "computeLine(cart.find(c => c.partNumber === %r)).finalUnitPrice" % PART
            )
            pdf = download_quote_pdf(page, alerts, tmp_path / "off.pdf")
    text = " ".join(page_texts(pdf))
    assert LIST_PRICE not in text, "the list price is still in the customer's PDF"
    assert "negotiated discount" not in text, "a discount off a price the customer cannot see"
    assert f"{unit:,.2f}" in text, "the unit price must still be there - the probe is not vacuous"


def test_off_removes_the_column_from_the_screen():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _quote(page, show_list=False)
            headers = page.locator("#docRoot table.quote-table thead th").all_inner_texts()
    assert len(headers) == 4, headers
    assert not any("List" in h for h in headers)


def test_the_choice_survives_the_archive():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _quote(page, show_list=False)
            snapshot = page.evaluate("buildQuoteSnapshot()")
            export = page.evaluate("buildExportObj()")
            qid = page.evaluate("QUOTE_ID")
            # Autosave is DEBOUNCED, so a wait_for_timeout is a race: at 400ms the
            # record still held the previous state and this test failed against
            # correct code. autoSaveNow() writes it synchronously.
            page.evaluate("autoSaveNow()")
            page.wait_for_timeout(200)
            assert page.evaluate("(id) => loadArchive()[id].show_list_price", qid) is False

            # Move to a NEW quote before flipping the checkbox back. Autosave writes
            # store[QUOTE_ID] on every change (HANDOFF.md §21.4), so ticking the box
            # while the saved quote is still open overwrites the very record this
            # test is about to reopen - and the test then passes or fails on the
            # autosave, not on the restore.
            page.evaluate("startNewQuote()")
            page.wait_for_timeout(200)
            page.set_checked("#showListPrice", True)
            page.wait_for_timeout(200)
            page.evaluate(f"openQuote({qid!r})")
            page.wait_for_timeout(300)
            restored = page.is_checked("#showListPrice")
    assert snapshot["show_list_price"] is False
    assert export["show_list_price"] is False
    assert restored is False

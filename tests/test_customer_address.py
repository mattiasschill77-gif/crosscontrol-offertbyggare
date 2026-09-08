"""The customer address (v1.8.0).

Asked for by a colleague: the company address under the company name on the
quote, and - the owner's call on 2026-09-08 - a full TO block on the price list
as well.

What these guard, worst consequence first:

1. The address is escaped. It is interpolated into HTML in renderDoc(),
   plRenderDoc() and generate_pdf.py, and archives move between colleagues, so an
   archived record carrying markup executes on open. This is the trap the quote
   number had (HANDOFF.md §20.2).
2. It really reaches both PDFs, not just the screen.
3. A blank address changes nothing, so a colleague's next quote does not silently
   change shape.
"""
from playwright.sync_api import sync_playwright

from harness import app_page, download_quote_pdf, page_texts, serve

ADDRESS = "Marine House, Dock Road\nBirkenhead\nCH41 1LQ"


def _quote_with_address(page, address=ADDRESS):
    page.fill("#custName", "Caudwell Marine Ltd")
    page.fill("#custContact", "James Caudwell")
    page.fill("#custAddress", address)
    page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number)")
    page.wait_for_timeout(400)


def test_the_address_is_carried_by_the_export_and_the_archive():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _quote_with_address(page)
            export = page.evaluate("buildExportObj()")
            snapshot = page.evaluate("buildQuoteSnapshot()")
    assert export["customer"]["address"] == ADDRESS
    assert snapshot["customer_address"] == ADDRESS


def test_the_address_is_on_screen_under_the_company_name():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _quote_with_address(page)
            billto = page.inner_text("#docRoot .billto")
    name_at = billto.index("Caudwell Marine Ltd")
    addr_at = billto.index("Dock Road")
    attn_at = billto.index("attn:")
    assert name_at < addr_at < attn_at, f"wrong order in the bill-to block: {billto!r}"


def test_the_address_reaches_the_quote_pdf(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            _quote_with_address(page)
            pdf = download_quote_pdf(page, alerts, tmp_path / "quote.pdf")
    first = page_texts(pdf)[0]
    assert "Dock Road" in first
    assert "CH41 1LQ" in first


def test_a_blank_address_renders_no_address_block():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.fill("#custName", "Caudwell Marine Ltd")
            page.fill("#custAddress", "")
            page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number)")
            page.wait_for_timeout(400)
            addr_nodes = page.locator("#docRoot .billto .addr").count()
    assert addr_nodes == 0


def test_the_address_is_escaped_on_screen_and_in_the_pdf(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            _quote_with_address(page, "Dock <b>Road</b>")
            html = page.inner_html("#docRoot .billto")
            text = page.inner_text("#docRoot .billto")
            pdf = download_quote_pdf(page, alerts, tmp_path / "quote.pdf")
    assert "<b>Road</b>" not in html, "the address was injected as live markup"
    assert "&lt;b&gt;Road&lt;/b&gt;" in html
    assert "<b>Road</b>" in text, "the tags must be visible as text, not swallowed"
    assert "<b>Road</b>" in page_texts(pdf)[0]

"""The printed numbers must multiply out (v1.8.0).

Prices are held in EUR and converted at display time. The unit price and the line
total used to be rounded to cents INDEPENDENTLY, so in a converted currency the
document contradicted itself:

    CCpilot V1000 2CAN, 965.08 EUR, qty 15, USD at 1.08
    printed   UNIT $1,042.29   QTY 15   TOTAL $15,634.30
    but       15 x 1,042.29  = $15,634.35

Found by the owner reviewing a real quote on screen, and present in the shipped
v1.7.2 build - not introduced by the v1.8.0 work.

These assert on what the document prints, parsed back out of it, because that is
the only thing a customer can check.
"""
import re

from playwright.sync_api import sync_playwright

from harness import app_page, download_quote_pdf, page_texts, serve

PART = "C000 154-50"       # CCpilot V1000, 2CAN - 965.08 EUR, an awkward one at 1.08
MONEY_RE = re.compile(r"[-+]?[\d,]+\.\d{2}")


def _money(text):
    """Strip whatever the currency wears. EUR/USD prefix a symbol; SEK suffixes ' kr'."""
    return float(re.sub(r"[^0-9.\-]", "", text.replace(",", "")))


def _one_line_quote(page, currency, qty=15):
    page.fill("#custName", "Caudwell Marine Ltd")
    page.evaluate(f"addProductToCart({PART!r})")
    page.wait_for_timeout(300)
    page.evaluate(
        "(q) => { cart = cart.filter(c => c.partNumber === %r);"
        "  cart[0].qty = q; renderAll(); }" % PART,
        qty,
    )
    page.select_option("#currencySelect", currency)
    page.wait_for_timeout(400)


def _row_figures(page):
    """Unit price, qty and total as the on-screen document prints them."""
    cells = page.locator("#docRoot table.quote-table tbody tr").first.locator("td.num")
    texts = cells.all_inner_texts()
    # columns: [list price], unit, qty, total - list price may be hidden
    nums = [t.strip() for t in texts if t.strip()]
    unit, qty, total = nums[-3], nums[-2], nums[-1]
    return _money(unit), int(qty.replace(",", "")), _money(total)


def test_the_screen_document_multiplies_out_in_usd():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _one_line_quote(page, "USD")
            unit, qty, total = _row_figures(page)
    assert round(unit * qty, 2) == total, (
        f"printed {unit} x {qty} = {round(unit * qty, 2)} but the document says {total}"
    )


def test_the_screen_document_multiplies_out_in_sek():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _one_line_quote(page, "SEK")
            unit, qty, total = _row_figures(page)
    assert round(unit * qty, 2) == total, (
        f"printed {unit} x {qty} = {round(unit * qty, 2)} but the document says {total}"
    )


def test_eur_is_unchanged_and_still_multiplies_out():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _one_line_quote(page, "EUR")
            unit, qty, total = _row_figures(page)
    assert round(unit * qty, 2) == total
    assert unit == 965.08, f"the EUR unit price moved: {unit}"


def test_the_pdf_multiplies_out_and_the_total_matches_the_row(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            _one_line_quote(page, "USD")
            unit, qty, total = _row_figures(page)
            pdf = download_quote_pdf(page, alerts, tmp_path / "quote.pdf")

    text = " ".join(page_texts(pdf))
    flat = re.sub(r"\s+", " ", text)
    for label, value in (("unit price", unit), ("line total", total)):
        printed = f"{value:,.2f}"
        assert printed in flat, f"{label} {printed} is not in the PDF"
    assert round(unit * qty, 2) == total

    # and the subtotal agrees with the single line it is made of
    subtotal_matches = [m for m in MONEY_RE.findall(flat) if _money(m) == total]
    assert len(subtotal_matches) >= 2, (
        "the line total should appear at least twice - once on the row and once as "
        f"the subtotal/total; found {len(subtotal_matches)} occurrence(s) of {total:,.2f}"
    )

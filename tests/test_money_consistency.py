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


# --------------------------------------------------------------------------- #
# The screen was fixed in afc61a9; the DOCUMENT was not (v1.8.2 device gate).
#
# buildExportObj() rounded every EUR money field to cents BEFORE the currency
# conversion, and both PDF paths print those rounded fields. The screen prints
# the full-precision value, so the two disagreed and the PDF did not multiply
# out - the exact defect of the module docstring above, surviving on the only
# surface the customer actually receives.
#
# Measured on the delivered v1.8.2 build, over 1161 product/quantity
# combinations per currency: the screen was right every time, the PDF was wrong
# on 40 in USD and 552 in SEK. EUR was clean at every one, because at rate 1
# the rounding is a no-op - which is also why the guard above never saw it.
# --------------------------------------------------------------------------- #

VI = "C000 144-05"          # CCpilot VI - 2,929.34 kr at 11.4, and it does NOT round-trip


def _sek_line(page, qty, typed=None):
    """One CCpilot VI line in SEK, optionally with a price typed in kronor."""
    page.fill("#custName", "Caudwell Marine Ltd")
    page.select_option("#currencySelect", "SEK")
    page.wait_for_timeout(300)
    page.evaluate(
        "(q) => { cart = []; addProductToCart(%r); cart[0].qty = q; renderAll(); }" % VI,
        qty,
    )
    page.wait_for_timeout(300)
    if typed is not None:
        page.locator('[data-action="unitprice"]').first.fill(str(typed))
        page.wait_for_timeout(400)


def test_a_typed_unit_price_reaches_the_pdf_unaltered(tmp_path):
    """The worst of the three: a NEGOTIATED price, changed in the customer's PDF.

    A price typed in kronor is stored as typed/rate, which is not a 2-decimal EUR
    number. Rounding it to cents on the way into the export moved it back out by
    more than a cent once multiplied by 11.4: 2,750.00 kr typed printed as
    2,750.02 kr, a figure nobody agreed to.
    """
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            _sek_line(page, qty=101, typed=2750.00)
            unit, _qty, _total = _row_figures(page)
            pdf = download_quote_pdf(page, alerts, tmp_path / "typed.pdf")

    assert unit == 2750.00, f"the screen shows {unit}, not the typed price - probe is vacuous"
    flat = re.sub(r"\s+", " ", " ".join(page_texts(pdf)))
    assert "2,750.00" in flat, "the PDF does not print the price that was typed"
    assert "2,750.02" not in flat, "the PDF altered a negotiated unit price"


def test_the_pdf_line_total_multiplies_out_in_sek(tmp_path):
    """Same assertion as the PDF guard above, on a fixture that can actually fail.

    ⚠️ That guard uses 965.08 EUR x 15 at 1.08, where round(unit x qty, 2) / rate
    lands on exactly 14,476.25 EUR - so rounding the EUR total to cents is a no-op
    and the guard passes whether the defect is present or not. CCpilot VI x 15 in
    SEK does not round-trip: the screen prints 43,940.10 and the PDF printed
    43,940.05.
    """
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            _sek_line(page, qty=15)
            unit, qty, total = _row_figures(page)
            pdf = download_quote_pdf(page, alerts, tmp_path / "sek.pdf")

    assert round(unit * qty, 2) == total, "the screen is wrong - the fixture is broken"
    flat = re.sub(r"\s+", " ", " ".join(page_texts(pdf)))
    assert f"{total:,.2f}" in flat, (
        f"the screen prints {total:,.2f} and the PDF does not - "
        f"{unit:,.2f} x {qty} must equal the printed total on both"
    )


def test_the_pdf_subtotal_agrees_with_the_rows_it_is_made_of(tmp_path):
    """subtotal_eur was rounded too, so the totals block could disagree with the
    lines above it by a cent even when every line was right."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            page.fill("#custName", "Caudwell Marine Ltd")
            page.select_option("#currencySelect", "SEK")
            page.wait_for_timeout(300)
            page.evaluate(
                """() => {
                    cart = [];
                    FLAT_PRODUCTS.slice(0, 6).forEach(p => addProductToCart(p.part_number));
                    const qtys = [15, 7, 123, 250, 33, 101];
                    cart.forEach((c, i) => c.qty = qtys[i % qtys.length]);
                    renderAll();
                }"""
            )
            page.wait_for_timeout(500)
            rows = page.locator("#docRoot table.quote-table tbody tr")
            totals = []
            for i in range(rows.count()):
                nums = [t.strip() for t in rows.nth(i).locator("td.num").all_inner_texts()]
                nums = [n for n in nums if n]
                if len(nums) >= 3:
                    totals.append(_money(nums[-1]))
            pdf = download_quote_pdf(page, alerts, tmp_path / "subtotal.pdf")

    assert len(totals) >= 6, f"only {len(totals)} rows - the fixture proves nothing"
    printed_sum = round(sum(totals), 2)
    flat = re.sub(r"\s+", " ", " ".join(page_texts(pdf)))
    assert f"{printed_sum:,.2f}" in flat, (
        f"the PDF's rows sum to {printed_sum:,.2f} and its totals block does not say so"
    )

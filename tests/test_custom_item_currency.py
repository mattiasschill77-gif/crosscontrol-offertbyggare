"""A custom item's price is typed in the displayed currency (v1.8.3).

Reported by the owner. The value was stored raw and then run through the same
EUR->display conversion the catalogue prices use, so the number typed was treated
as euros and marked up. Measured before the fix, typing 9500:

    EUR  ->  EUR 9,500.00     correct
    USD  ->  $10,260.00       9500 x 1.08
    SEK  ->  108,300.00 kr    9500 x 11.4

In SEK a 9 500 kr engineering line quoted the customer 108 300 kr. Pre-existing -
computeLine's custom branch is identical on the v1.7.2 tag.

⚠️ The tests type through the REAL input and read the figure back off the rendered
document, because that is the pair that disagreed. Asserting on cart state alone
would have passed throughout: customUnitPrice was always "the number typed", it was
the render that reinterpreted it.
"""
import re

from playwright.sync_api import sync_playwright

from harness import app_page, serve

TYPED = "9500"


def _money(text):
    """EUR/USD prefix a symbol; SEK suffixes ' kr'."""
    return float(re.sub(r"[^0-9.\-]", "", text.replace(",", "")))


def _custom_line(page, currency, qty=3):
    page.evaluate("cart = []; renderAll();")
    page.select_option("#currencySelect", currency)
    page.wait_for_timeout(250)
    page.click("#addCustomBtn")
    page.wait_for_timeout(250)
    line_id = page.evaluate("cart[cart.length - 1].lineId")
    row = page.locator(f'[data-row-line-id="{line_id}"]')
    row.locator('[data-action="custom-desc"]').fill("Software development")
    row.locator('[data-action="custom-price"]').fill(TYPED)
    row.locator('[data-action="qty"]').fill(str(qty))
    page.wait_for_timeout(400)
    return line_id


def _doc_row(page):
    cells = page.locator("#docRoot table.quote-table tbody tr").first.locator("td.num")
    nums = [t.strip() for t in cells.all_inner_texts() if t.strip()]
    return _money(nums[-3]), int(nums[-2].replace(",", "")), _money(nums[-1])


def test_the_document_prints_the_number_that_was_typed_in_every_currency():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            for currency in ("EUR", "USD", "SEK"):
                _custom_line(page, currency)
                unit, qty, total = _doc_row(page)
                assert unit == float(TYPED), (
                    f"{currency}: typed {TYPED} but the customer's document says {unit}"
                )
                assert round(unit * qty, 2) == total, (
                    f"{currency}: {qty} x {unit} = {unit * qty} but the total says {total}"
                )


def test_the_price_is_stored_in_eur():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _custom_line(page, "SEK")
            stored = page.evaluate("cart[0].customUnitPrice")
            rate = page.evaluate("CURRENCY_RATES.SEK.rate")
    assert rate > 1, "the fixture rate must not be 1 or this proves nothing"
    assert round(stored, 2) == round(float(TYPED) / rate, 2), (
        f"stored {stored}, expected {float(TYPED) / rate:.2f} EUR"
    )


def test_switching_currency_converts_the_price_instead_of_reinterpreting_it():
    """Type 9500 kr, switch to EUR: the line must become ~833 EUR, not 9500 EUR."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _custom_line(page, "SEK")
            rate = page.evaluate("CURRENCY_RATES.SEK.rate")
            page.select_option("#currencySelect", "EUR")
            page.wait_for_timeout(400)
            unit, _qty, _total = _doc_row(page)
            field = page.locator('[data-action="custom-price"]').first.input_value()
    expected = round(float(TYPED) / rate, 2)
    assert unit == expected, f"after switching to EUR the document says {unit}, expected {expected}"
    assert float(field) == expected, f"the input still shows {field}, expected {expected}"


def test_the_field_shows_which_currency_it_is_in():
    """It showed no symbol at all, which is why typing euros into a SEK quote was
    so easy to do. Every other price field in the card names its currency."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            line_id = _custom_line(page, "SEK")
            row_text = page.locator(f'[data-row-line-id="{line_id}"] .qty-row').inner_text()
    assert "kr" in row_text, f"no currency marker beside the custom price field: {row_text!r}"

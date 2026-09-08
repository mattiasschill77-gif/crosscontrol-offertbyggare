"""A typed unit price over a volume tier (v1.8.0).

Asked for by a colleague, with "keep the deviation warning". The owner's calls
on 2026-09-08: the typed price wins and clears Extra discount, the flag shows on
ANY difference from the tier price, and clicking another tier keeps the typed
price - a stray click must never destroy a negotiated number.

What these guard, worst consequence first:

1. The total agrees with the visible lines. A document whose total disagrees
   with its own rows is the failure this tool has already had once.
2. The typed price is stored in EUR and converted, not reinterpreted. Typing
   245.00 in EUR and switching to SEK must show the SEK equivalent, not 245 kr.
3. A tier click does not silently discard it.
"""
from playwright.sync_api import sync_playwright

from harness import app_page, download_quote_pdf, page_texts, serve

PART = "C000 144-05"    # CCpilot VI - list 526.76, tier 100-249 at 256.96

# The app SEEDS a demo cart on a fresh browser profile, and C000 144-05 is one of
# the seeded lines - addProductToCart no-ops for a part already in the cart
# (HANDOFF.md §18.4). So the line is found, never added, and every row lookup goes
# through its lineId: ":has-text('CCpilot VI')" also matches "CCpilot VI, LinX-Base"
# and would silently drive the wrong row.


def _row(page, line_id):
    return page.locator(f'[data-row-line-id="{line_id}"]')


def _line_with_override(page, price=245.00, qty=150):
    """Returns the lineId of the CCpilot VI line, with an override typed on it."""
    page.evaluate(f"addProductToCart({PART!r})")
    page.wait_for_timeout(300)
    line_id = page.evaluate(
        "(q) => { const it = cart.find(c => c.partNumber === %r);"
        "  it.qty = q; renderAll(); return it.lineId; }" % PART,
        qty,
    )
    _row(page, line_id).locator('[data-action="unitprice"]').fill(str(price))
    page.wait_for_timeout(400)
    return line_id


def test_the_typed_price_becomes_the_line_price():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _line_with_override(page)
            computed = page.evaluate(
                "computeLine(cart.find(c => c.partNumber === %r))" % PART
            )
    assert round(computed["finalUnitPrice"], 2) == 245.00
    assert round(computed["tierPrice"], 2) == 256.96
    assert round(computed["lineTotal"], 2) == 36750.00


def test_the_discount_is_cleared_and_disabled():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            line_id = _line_with_override(page)
            disc = _row(page, line_id).locator('[data-action="discount"]')
            pct = page.evaluate("cart.find(c => c.partNumber === %r).extraDiscountPct" % PART)
            disabled = disc.is_disabled()
    assert pct == 0
    assert disabled


def test_the_deviation_flag_shows_for_a_price_above_the_tier_too():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            line_id = _line_with_override(page, price=300.00)
            flag = _row(page, line_id).locator('[data-computed="deviation"]')
            cls = flag.get_attribute("class") or ""
            txt = flag.inner_text()
    assert "show" in cls, "the flag is hidden for a price ABOVE the tier"
    assert "+16.7" in txt, txt


def test_clicking_another_tier_keeps_the_typed_price():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            line_id = _line_with_override(page)
            _row(page, line_id).locator(".tier-chip").nth(1).click()
            page.wait_for_timeout(300)
            item = page.evaluate("cart.find(c => c.partNumber === %r)" % PART)
    assert round(item["unitPriceOverride"], 2) == 245.00
    assert item["selectedTier"] == "250-499"


def test_use_tier_price_clears_the_override():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            line_id = _line_with_override(page)
            _row(page, line_id).locator('[data-action="clear-override"]').click()
            page.wait_for_timeout(300)
            item = page.evaluate("cart.find(c => c.partNumber === %r)" % PART)
            disabled = _row(page, line_id).locator('[data-action="discount"]').is_disabled()
    assert item["unitPriceOverride"] is None
    assert not disabled


def test_a_price_typed_in_another_currency_is_stored_in_eur():
    """⚠️ The price must be typed while a NON-EUR currency is selected.

    An earlier version of this test typed it in EUR, where fxOut() is 1 and the
    division is a no-op - so it passed with the conversion deleted. The Task 10
    break pass caught it. Type in SEK, and the stored value has to come back as
    EUR or nothing here holds.
    """
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.select_option("#currencySelect", "SEK")
            page.wait_for_timeout(300)
            rate = page.evaluate("CURRENCY_RATES.SEK.rate")
            assert rate > 1, "the fixture rate must not be 1 or this proves nothing"

            page.evaluate(f"addProductToCart({PART!r})")
            page.wait_for_timeout(300)
            line_id = page.evaluate(
                "() => { const it = cart.find(c => c.partNumber === %r);"
                "  it.qty = 150; renderAll(); return it.lineId; }" % PART
            )
            typed_sek = round(245.00 * rate, 2)
            _row(page, line_id).locator('[data-action="unitprice"]').fill(str(typed_sek))
            page.wait_for_timeout(400)
            stored = page.evaluate(
                "cart.find(c => c.partNumber === %r).unitPriceOverride" % PART
            )

            # Back to EUR: the line must read 245.00, not the SEK figure.
            page.select_option("#currencySelect", "EUR")
            page.wait_for_timeout(300)
            computed = page.evaluate(
                "computeLine(cart.find(c => c.partNumber === %r))" % PART
            )

    assert round(stored, 2) == 245.00, \
        f"typed {typed_sek} kr at {rate} SEK/EUR; stored {stored} instead of 245.00 EUR"
    assert round(computed["finalUnitPrice"], 2) == 245.00, \
        "a currency switch must convert an override, never reinterpret it"


def test_the_typed_price_and_the_total_reach_the_pdf(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            _line_with_override(page)
            page.evaluate("cart = cart.filter(c => c.partNumber === %r); renderAll();" % PART)
            page.wait_for_timeout(300)
            pdf = download_quote_pdf(page, alerts, tmp_path / "quote.pdf")
    text = " ".join(page_texts(pdf))
    assert "245.00" in text
    assert "36,750.00" in text, "the total must agree with the visible line"
    assert "256.96" not in text, "the tier price must not print as the unit price"


def test_the_override_survives_the_archive():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _line_with_override(page)
            export = page.evaluate("buildExportObj()")
            qid = page.evaluate("QUOTE_ID")
            # Autosave is debounced; force it rather than racing a timer.
            page.evaluate("autoSaveNow()")
            page.wait_for_timeout(200)
            page.evaluate("cart = []; renderAll();")
            page.evaluate(f"openQuote({qid!r})")
            page.wait_for_timeout(400)
            restored = page.evaluate(
                "cart.find(c => c.partNumber === %r).unitPriceOverride" % PART
            )
    line = [l for l in export["lines"] if l["part_number"] == PART][0]
    assert round(line["unit_price_override_eur"], 2) == 245.00
    assert round(restored, 2) == 245.00


MK_SEK = 4711.25
MK_NEEDLE = "4711"


def test_cost_and_margin_never_reach_the_quote_pdf(tmp_path):
    """The hard rule of this repo, re-checked against the newest path by which cost
    could reach a customer document: an override changes what margin is calculated
    FROM, so the margin card is live while a typed price is set.

    Non-vacuous by construction - the cost is asserted to be ON the internal card
    first, then asserted absent from the customer's PDF.
    """
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            line_id = _line_with_override(page)
            page.evaluate(
                "(mk) => { const it = cart.find(c => c.partNumber === %r);"
                "  it.mkSekOverride = mk; renderAll(); }" % PART,
                MK_SEK,
            )
            page.wait_for_timeout(400)
            # ⚠️ inner_text() does NOT include an <input>'s value, so reading the
            # row's text and searching for the cost finds nothing, and the
            # non-vacuity check then fails against correct code. Read the field.
            mk_field = _row(page, line_id).locator('[data-action="mk"]').input_value()
            margin_row = _row(page, line_id).locator('[data-computed="tgrow"]').inner_text()
            pdf = download_quote_pdf(page, alerts, tmp_path / "quote.pdf")

    assert MK_NEEDLE in mk_field.replace(",", "").replace(" ", ""), \
        f"the cost is not on the internal card ({mk_field!r}) - this probe proves nothing"
    assert "Margin" in margin_row, \
        f"the margin row is missing ({margin_row!r}) - this probe proves nothing"

    pages = page_texts(pdf)
    flat_pdf = " ".join(pages).replace(",", "").replace(" ", "").replace(" ", "")
    assert MK_NEEDLE not in flat_pdf, "manufacturing cost reached the customer's PDF"
    assert "Margin" not in " ".join(pages), "the margin label reached the customer's PDF"

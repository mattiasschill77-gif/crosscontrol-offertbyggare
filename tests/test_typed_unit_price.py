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
from playwright.sync_api import TimeoutError as PlaywrightTimeout
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


# --------------------------------------------------------------------------- #
# Found by the v1.8.2 device gate, both from one cause.
#
# setUnitPriceOverride() mutated the cart and returned, calling neither
# renderDoc() nor scheduleAutoSave() - unlike setQty() and setExtraDiscount(),
# which both do. So typing a negotiated price left the live document showing the
# tier price, and never wrote the price to the archive.
#
# ⚠️ The archive guard above could not see the second half: it calls autoSaveNow()
# explicitly, following this repo's own "autosave is debounced, force it rather
# than racing a timer" advice - which is right for a timing race, and here
# bypassed the missing scheduleAutoSave() entirely. A guard that forces the save
# cannot tell you whether anything would have saved.
# --------------------------------------------------------------------------- #


def _doc_row_cells(page):
    row = page.locator("#docRoot table.quote-table tbody tr").first
    return [t.strip() for t in row.locator("td.num").all_inner_texts()]


def test_the_live_document_shows_a_typed_price_without_another_edit():
    """The preview is what the KAM checks before sending. It kept printing the
    tier price until some unrelated control happened to call renderDoc()."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.evaluate(
                "() => { cart = []; addProductToCart(%r); cart[0].qty = 101; renderAll(); }"
                % PART
            )
            page.wait_for_timeout(300)
            before = _doc_row_cells(page)
            page.locator('[data-action="unitprice"]').first.fill("245.00")
            page.wait_for_timeout(600)
            after = _doc_row_cells(page)
            # no renderDoc(), no renderAll(), no other control touched

    assert "256.96" in " ".join(before), f"the fixture did not start at the tier price: {before}"
    joined = " ".join(after)
    assert "245.00" in joined, (
        f"the document still shows {after} - a typed price does not reach the preview"
    )
    assert "24,745.00" in joined, "the document's line total did not follow the typed price"


def test_a_typed_price_is_autosaved_without_being_forced():
    """⚠️ This test must NOT call autoSaveNow(). Forcing the save is exactly what
    hid the defect: the price reached the archive only because the test put it
    there. Type, wait past the 500ms debounce, and read what the app saved.

    ⚠️ The archive record is an object keyed by quote_id holding the RAW cart
    (`rec.cart`, `partNumber`, `unitPriceOverride`) - NOT the export object's
    `lines` / `part_number` / `unit_price_override_eur`. HANDOFF.md §25.1: the
    record stores what restores a field, the export carries what the document
    prints. Reading the export's names here finds no line at all and the guard
    stays red for the wrong reason.
    """
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.fill("#custName", "Caudwell Marine Ltd")
            page.evaluate(
                "() => { cart = []; addProductToCart(%r); cart[0].qty = 101; renderAll(); }"
                % PART
            )
            page.wait_for_timeout(300)
            qid = page.evaluate("QUOTE_ID")
            page.evaluate("autoSaveNow()")   # a baseline record, with no override on it
            page.wait_for_timeout(300)

            page.locator('[data-action="unitprice"]').first.fill("245.00")

            # Condition-based, not a fixed sleep: poll until the app writes it.
            saved = None
            try:
                page.wait_for_function(
                    """(args) => {
                        const a = JSON.parse(localStorage.getItem('cc_quote_archive_v1') || 'null');
                        if (!a) return false;
                        const rec = Array.isArray(a) ? a.find(r => r.quote_id === args.qid)
                                                     : a[args.qid];
                        if (!rec || !rec.cart) return false;
                        const l = rec.cart.find(x => x.partNumber === args.part);
                        return !!l && Math.abs((l.unitPriceOverride || 0) - 245) < 0.005;
                    }""",
                    arg={"qid": qid, "part": PART},
                    timeout=5000,
                )
                saved = 245.0
            except PlaywrightTimeout:
                saved = page.evaluate(
                    """(args) => {
                        const a = JSON.parse(localStorage.getItem('cc_quote_archive_v1') || 'null');
                        const rec = Array.isArray(a) ? a.find(r => r.quote_id === args.qid)
                                                     : a[args.qid];
                        const l = rec && rec.cart &&
                                  rec.cart.find(x => x.partNumber === args.part);
                        return l ? l.unitPriceOverride : 'no line';
                    }""",
                    arg={"qid": qid, "part": PART},
                )
            live = page.evaluate("cart.find(c => c.partNumber === %r).unitPriceOverride" % PART)

    assert round(live, 2) == 245.00, "the fixture never set the override at all"
    assert saved == 245.0, (
        f"the archive holds {saved!r} after 5s while the cart holds 245.00 - a typed "
        "price is lost if the KAM types it and closes the tab"
    )


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


def test_the_unit_price_row_does_not_collide_with_the_tier_chips():
    """Reported by the owner from a screenshot: the Unit price box looked like it
    overlapped the volume-tier pills.

    The row had NO top margin while every sibling (.extra-discount-row, .mk-row)
    has 10px, so it sat flush against the chips - measured 0px gap - and the
    input's 3px focus ring bled up into them.

    Asserted geometrically at three panel widths, with the field FOCUSED, because
    the focus ring is what made a zero gap read as a collision. No text assertion
    can see this.
    """
    RING = 3   # --focus-ring spreads 3px beyond the input on every side

    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            line_id = page.evaluate(
                "() => { cart = []; renderAll(); addProductToCart(%r);"
                "  const it = cart.find(c => c.partNumber === %r);"
                "  it.qty = 15; renderAll(); return it.lineId; }" % (PART, PART)
            )
            page.wait_for_timeout(300)
            row = _row(page, line_id)
            row.locator('[data-action="unitprice"]').click()
            page.wait_for_timeout(200)

            for panel in (420, 560, 700):
                page.evaluate(
                    "(w) => document.documentElement.style.setProperty('--panel-w', w + 'px')",
                    panel,
                )
                page.wait_for_timeout(250)
                chips = row.locator(".tier-select-row").bounding_box()
                unit = row.locator(".unitprice-row").bounding_box()
                gap = unit["y"] - (chips["y"] + chips["height"])
                assert gap >= RING, (
                    f"panel {panel}px: only {gap:.1f}px between the tier chips and the "
                    f"Unit price row - the {RING}px focus ring overlaps the chips"
                )

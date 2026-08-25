# tests/test_input_limits.py
"""
Task 8 (owner, post-review): bound the free-text fields that reach the
customer document, as defence in depth against the two deletion bugs this
branch already fixed (dontBreakRows silently dropping a priced product row;
`unbreakable` silently dropping the whole TERMS block). Limits are the
owner's, do not change without asking:

    per-line note (textarea)            1000
    custom line item description         400
    VAT / Tariff note (#vatNote)         400
    Named place (#termIncotermLocation)  120

Every limit sits well under the measured overflow thresholds (~2,100 chars
for the terms block, ~3,200 for a product row) established in
test_pagination.py, so a field capped at its limit can never trigger either
deletion bug on its own.

Also verifies the small "N / MAX" counter next to each field, and that the
per-line controls keep the accessible names required by HANDOFF.md §11.
"""
import pytest
from playwright.sync_api import sync_playwright

from harness import app_page, serve

NOTE_LIMIT = 1000
CUSTOM_DESC_LIMIT = 400
VAT_NOTE_LIMIT = 400
NAMED_PLACE_LIMIT = 120


@pytest.fixture
def lines_page():
    """Yields (page, alerts). A fresh browser context has no localStorage, so
    the app's own seedDemoContent() runs and puts a product line AND a
    custom line on screen with no action needed here - see HANDOFF.md's
    startup section. Assert that rather than assume it, so this test fails
    loudly (not silently against empty controls) if that seeding ever
    changes."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            assert page.evaluate("cart.length") == 3, (
                "expected the demo seed (2 products + 1 custom line); "
                "if seeding changed, this test needs a product/custom line added explicitly"
            )
            assert page.evaluate("cart[2].isCustom") is True
            yield page, alerts


# ---------------------------------------------------------------------------
# maxlength attribute present, correct value, on every template
# ---------------------------------------------------------------------------

def test_maxlength_on_standard_line_note(lines_page):
    page, _ = lines_page
    note = page.locator('#productList .product-row:not(.custom-row) textarea[data-action="note"]').first
    assert note.get_attribute("maxlength") == str(NOTE_LIMIT)


def test_maxlength_on_custom_line_note(lines_page):
    # The per-line note exists in TWO templates (standard line, custom line) -
    # HANDOFF.md §11 documents the extra-discount input being patched in only
    # one of them by mistake. Check this one separately from the standard one.
    page, _ = lines_page
    note = page.locator('#productList .custom-row textarea[data-action="note"]').first
    assert note.get_attribute("maxlength") == str(NOTE_LIMIT)


def test_maxlength_on_custom_line_description(lines_page):
    page, _ = lines_page
    desc = page.locator('#productList input.custom-desc-input').first
    assert desc.get_attribute("maxlength") == str(CUSTOM_DESC_LIMIT)


def test_maxlength_on_vat_note(lines_page):
    page, _ = lines_page
    assert page.get_attribute("#vatNote", "maxlength") == str(VAT_NOTE_LIMIT)


def test_maxlength_on_named_place(lines_page):
    page, _ = lines_page
    assert page.get_attribute("#termIncotermLocation", "maxlength") == str(NAMED_PLACE_LIMIT)


# ---------------------------------------------------------------------------
# enforcement - must use real keystrokes, not fill()
#
# Playwright's locator.fill() sets the DOM value directly (it's meant for
# fast, reliable form-filling) and does NOT run the browser's native
# maxlength truncation - that only fires on real input events from typing.
# fill()-ing 2000 characters into a maxlength=400 field leaves value.length
# at 2000 and would make an enforcement test pass even with no maxlength
# attribute at all. So this section uses press_sequentially(), which
# dispatches one real keydown/input per character exactly like a user typing,
# to actually exercise the browser's enforcement.
# ---------------------------------------------------------------------------

def test_standard_line_note_is_capped_when_typed(lines_page):
    page, _ = lines_page
    note = page.locator('#productList .product-row:not(.custom-row) textarea[data-action="note"]').first
    note.fill("")  # clear the seeded note; fill('') has nothing to bypass
    note.press_sequentially("n" * (NOTE_LIMIT + 20))
    assert note.input_value() == "n" * NOTE_LIMIT


def test_custom_line_description_is_capped_when_typed(lines_page):
    page, _ = lines_page
    desc = page.locator('#productList input.custom-desc-input').first
    desc.fill("")
    desc.press_sequentially("d" * (CUSTOM_DESC_LIMIT + 20))
    assert desc.input_value() == "d" * CUSTOM_DESC_LIMIT


def test_vat_note_is_capped_when_typed(lines_page):
    page, _ = lines_page
    page.fill("#vatNote", "")
    page.locator("#vatNote").press_sequentially("v" * (VAT_NOTE_LIMIT + 20))
    assert page.input_value("#vatNote") == "v" * VAT_NOTE_LIMIT


def test_named_place_is_capped_when_typed(lines_page):
    page, _ = lines_page
    page.fill("#termIncotermLocation", "")
    page.locator("#termIncotermLocation").press_sequentially("p" * (NAMED_PLACE_LIMIT + 20))
    assert page.input_value("#termIncotermLocation") == "p" * NAMED_PLACE_LIMIT


# ---------------------------------------------------------------------------
# the two deletion-bug regression tests must still pass with fill() bypassing
# maxlength on purpose - covered by test_pagination.py, not repeated here.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# counter reflects remaining room
# ---------------------------------------------------------------------------

def test_named_place_counter_matches_seeded_value(lines_page):
    # #termIncotermLocation ships with a default value ("Alfta, Sweden"), so
    # the counter should already read correctly with no typing at all.
    page, _ = lines_page
    value = page.input_value("#termIncotermLocation")
    counter = page.locator("#termIncotermLocation + .char-count")
    assert counter.text_content().strip() == f"{len(value)} / {NAMED_PLACE_LIMIT}"


def test_vat_note_counter_updates_while_typing(lines_page):
    page, _ = lines_page
    page.fill("#vatNote", "")
    page.locator("#vatNote").press_sequentially("c" * 240)
    counter = page.locator("#vatNote + .char-count")
    assert counter.text_content().strip() == f"240 / {VAT_NOTE_LIMIT}"


def test_standard_line_note_counter_updates_while_typing(lines_page):
    page, _ = lines_page
    note = page.locator('#productList .product-row:not(.custom-row) textarea[data-action="note"]').first
    note.fill("")
    note.press_sequentially("n" * 55)
    counter = page.locator(
        '#productList .product-row:not(.custom-row) textarea[data-action="note"] + .char-count'
    ).first
    assert counter.text_content().strip() == f"55 / {NOTE_LIMIT}"


def test_counter_hidden_when_field_is_empty(lines_page):
    # Chosen behaviour: only show the counter once the field has content, so
    # a blank custom-line note/description doesn't clutter the panel.
    page, _ = lines_page
    note = page.locator('#productList .product-row:not(.custom-row) textarea[data-action="note"]').first
    note.fill("")
    note.dispatch_event("input")
    counter = page.locator(
        '#productList .product-row:not(.custom-row) textarea[data-action="note"] + .char-count'
    ).first
    assert not counter.is_visible()


# ---------------------------------------------------------------------------
# accessibility contract (HANDOFF.md §11) must survive
# ---------------------------------------------------------------------------

def test_counters_are_decorative_and_fields_keep_their_accessible_names(lines_page):
    page, _ = lines_page
    custom_note = page.locator('#productList .custom-row textarea[data-action="note"]').first
    assert custom_note.get_attribute("aria-label") == "Note for this custom item"
    custom_note_counter = page.locator('#productList .custom-row textarea[data-action="note"] + .char-count').first
    assert custom_note_counter.get_attribute("aria-hidden") == "true"

    desc = page.locator('#productList input.custom-desc-input').first
    assert desc.get_attribute("aria-label") == "Custom item description"
    desc_counter = page.locator('#productList input.custom-desc-input + .char-count').first
    assert desc_counter.get_attribute("aria-hidden") == "true"

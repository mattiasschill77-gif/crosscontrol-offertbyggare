"""The export block folds (v1.7.2).

.generate-bar sits outside .panel-scroll, so it is a fixed footer of the control
panel: its height can never be scrolled away, and on a laptop screen it
permanently crowded out the controls above it. It folds now.

What these guard, in order of what would actually hurt:

1. The default is expanded. Anyone who never touches the toggle sees exactly the
   build they had before, so the change cannot surprise a colleague.
2. Collapsing really recovers height - measured in pixels, not inferred from a
   class or an attribute. A fold that folds nothing is the whole failure mode.
3. The Download button survives the fold. Hiding the primary action inside the
   thing you collapsed would be worse than the crowding it fixes.
4. The choice survives a reload, which is the only reason to persist it at all.
"""
from playwright.sync_api import sync_playwright

from harness import app_page, serve

KEY = "cc_export_expanded_v1"


def _bar_height(page):
    return page.evaluate(
        "Math.round(document.querySelector('.generate-bar').getBoundingClientRect().height)"
    )


def test_default_is_expanded_on_a_fresh_profile():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            assert page.evaluate(f"localStorage.getItem('{KEY}')") is None
            assert page.get_attribute("#exportToggleBtn", "aria-expanded") == "true"
            assert page.is_visible("#saveToFolderBtn")
            assert page.is_visible("#exportJsonBtn")


def test_collapsing_actually_recovers_height():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            expanded = _bar_height(page)
            page.click("#exportToggleBtn")
            page.wait_for_timeout(200)
            collapsed = _bar_height(page)
            extras_display = page.evaluate(
                "getComputedStyle(document.getElementById('exportExtras')).display"
            )
    # Measured 2026-08-31 at 381 -> 129. Assert on a floor, not the exact number:
    # the bar's height moves with the archive status line's wrapping.
    assert extras_display == "none"
    assert expanded - collapsed > 150, f"folded only {expanded - collapsed}px ({expanded} -> {collapsed})"


def test_the_download_button_stays_visible_when_collapsed():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.click("#exportToggleBtn")
            page.wait_for_timeout(200)
            assert page.is_visible("#downloadPdfBtn")
            assert page.is_visible("#archiveStatus")
            # And it is still the real control, not just painted: clicking it
            # exports. Asserted through a download event, never a button label.
            page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number)")
            page.wait_for_timeout(300)
            with page.expect_download(timeout=30000) as dl:
                page.click("#downloadPdfBtn")
            assert dl.value.suggested_filename.endswith(".pdf")


def test_the_choice_survives_a_reload():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.click("#exportToggleBtn")
            assert page.evaluate(f"localStorage.getItem('{KEY}')") == "0"
            page.reload()
            page.wait_for_function("typeof addProductToCart === 'function'")
            assert page.get_attribute("#exportToggleBtn", "aria-expanded") == "false"

            page.click("#exportToggleBtn")
            assert page.evaluate(f"localStorage.getItem('{KEY}')") == "1"
            page.reload()
            page.wait_for_function("typeof addProductToCart === 'function'")
            assert page.get_attribute("#exportToggleBtn", "aria-expanded") == "true"

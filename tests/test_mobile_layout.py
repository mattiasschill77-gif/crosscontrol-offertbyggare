"""The app on a phone.

Scope, set by the owner: it must not look broken. Reading a quote and showing
it to someone should work. Building a whole quote with a thumb is explicitly
not in scope.

Measured 2026-08-26 before any change: at 390x844 the page was 798px wide, so
the whole thing scrolled sideways. Everything below the top bar already fitted
- the 1000px breakpoint collapses the grid correctly - and the entire overflow
came from the top bar, a flex row that refused to wrap.

⚠️ These run in Chromium with an iPhone viewport, not on an iPhone. Safari is a
different engine; the real check is the owner's own phone.
"""
import pytest
from playwright.sync_api import sync_playwright

from harness import serve

PHONE = {"width": 390, "height": 844}
TABLET = {"width": 768, "height": 1024}
DESKTOP = {"width": 1440, "height": 900}

OVERFLOW_JS = """() => {
  const de = document.documentElement;
  const vw = de.clientWidth;
  const out = [];
  document.querySelectorAll('body *').forEach(el => {
    const b = el.getBoundingClientRect();
    if (b.right > vw + 1 && b.width > 0 && b.height > 0) {
      out.push(el.tagName.toLowerCase()
        + (el.id ? '#' + el.id : '')
        + (typeof el.className === 'string' && el.className ? '.' + el.className.split(' ')[0] : '')
        + ' right=' + Math.round(b.right));
    }
  });
  const seen = new Set();
  return { viewport: vw, pageWidth: Math.round(de.scrollWidth),
           offenders: out.filter(o => !seen.has(o) && seen.add(o)).slice(0, 8) };
}"""


def _measure(viewport, with_product=True):
    with serve() as url, sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=viewport, is_mobile=viewport["width"] < 768,
                                  has_touch=viewport["width"] < 768)
        page = ctx.new_page()
        page.on("dialog", lambda d: d.accept())
        page.goto(url)
        page.wait_for_function(
            "typeof addProductToCart === 'function' && FLAT_PRODUCTS.length > 0"
        )
        if with_product:
            page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number)")
            page.wait_for_timeout(600)
        result = page.evaluate(OVERFLOW_JS)
        result["tabsVisible"] = page.is_visible(".topbar-tabs")
        result["quoteIdVisible"] = page.is_visible("#currentQuoteId")
        result["archiveBtnVisible"] = page.is_visible("#openArchiveBtn")
        result["docVisible"] = page.is_visible("#docRoot")
        browser.close()
    return result


@pytest.mark.parametrize("viewport,name", [(PHONE, "phone"), (TABLET, "tablet")])
def test_the_page_does_not_scroll_sideways(viewport, name):
    r = _measure(viewport)
    assert not r["offenders"], f"{name}: elements stick out past the viewport: {r['offenders']}"
    assert r["pageWidth"] <= r["viewport"] + 1, (
        f"{name}: the page is {r['pageWidth']}px wide in a {r['viewport']}px viewport"
    )


def test_the_things_you_need_to_read_a_quote_are_still_there_on_a_phone():
    """Collapsing the top bar must not mean hiding the way back to the archive."""
    r = _measure(PHONE)
    assert r["docVisible"], "the document is not visible on a phone"
    assert r["tabsVisible"], "the Quote builder / Price list tabs disappeared"
    assert r["archiveBtnVisible"], "the Archive button disappeared"
    assert r["quoteIdVisible"], "the quote number disappeared"


def test_the_desktop_layout_is_untouched():
    """A regression guard: this work is only allowed to change narrow screens."""
    r = _measure(DESKTOP)
    assert not r["offenders"], f"desktop regressed: {r['offenders']}"
    assert r["pageWidth"] <= r["viewport"] + 1
    assert r["tabsVisible"] and r["archiveBtnVisible"] and r["quoteIdVisible"]


def test_the_document_keeps_its_real_width_on_a_phone():
    """The invariant a geometric test CAN check, and the one that matters.

    The first attempt at this made the page stop scrolling sideways while the
    document was still squeezed from 780px to ~316px. Nothing overflowed in DOM
    terms - the five-column price table simply collapsed until the headers
    collided and the totals ran into the page edge - so the overflow test above
    passed and a screenshot showed a broken document.

    Keeping the real width and scaling the whole thing down is what makes the
    columns land where they were designed to. If someone reintroduces
    max-width:100% here, this fails."""
    with serve() as url, sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=PHONE, is_mobile=True, has_touch=True)
        page = ctx.new_page()
        page.on("dialog", lambda d: d.accept())
        page.goto(url)
        page.wait_for_function(
            "typeof addProductToCart === 'function' && FLAT_PRODUCTS.length > 0"
        )
        page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number); renderAll();")
        page.wait_for_timeout(700)
        r = page.evaluate("""() => {
            const d = document.getElementById('docRoot');
            const cs = getComputedStyle(d);
            return { cssWidth: parseFloat(cs.width), maxWidth: cs.maxWidth,
                     visualWidth: Math.round(d.getBoundingClientRect().width),
                     sigCols: getComputedStyle(d.querySelector('.signature-grid')).gridTemplateColumns };
        }""")
        browser.close()
    assert r["cssWidth"] > 700, f"the document is squeezed to {r['cssWidth']}px instead of 780"
    assert r["visualWidth"] <= PHONE["width"], "the scaled document is wider than the screen"
    assert len(r["sigCols"].split()) == 2, (
        "the acceptance block stopped being two columns - the preview must match "
        f"the PDF, got {r['sigCols']!r}"
    )

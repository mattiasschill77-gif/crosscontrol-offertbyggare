"""The price list PDF's column widths (v1.8.0).

`widths` was built once and passed by reference to every family's table. pdfmake
REPLACES the entries of that array in place with annotated objects during layout,
so all 18 family tables were laid out with the FIRST family's measurements -
identical to twelve decimal places when probed.

CCpilot VI's prices are ~40pt wide; CCpilot V1200's are wider. Families after the
first therefore got a NET PRICE column sized for someone else's numbers, and the
price broke mid-number: "€2,438.6" on one line and "0" on the next.

Measured before the fix: 56 whole prices and 73 orphaned digits out of 129 items.
57% of the price list was printing broken prices to customers, in v1.7.2.

The guard looks for a line that is nothing but one or two digits, because that is
what a mid-number break leaves behind. It is the symptom a customer sees, not an
internal width number, so it keeps meaning the same thing if the layout changes.
"""
import re

import fitz
from playwright.sync_api import sync_playwright

from harness import app_page, serve

ORPHAN_RE = re.compile(r"^\d{1,2}$")
# A price with a thousands separator - the ones that were breaking.
WIDE_PRICE_RE = re.compile(r"\d{1,3},\d{3}\.\d{2}")


def _select_everything(page):
    page.evaluate("switchView('pricelist')")
    page.fill("#plCustName", "Caudwell Marine Ltd")
    page.evaluate(
        """() => {
            plSections(PRICE_DATA).forEach(g =>
                (g.products || []).forEach(p => PL.selection[p.part_number] = true));
            plRenderAll();
        }"""
    )
    page.wait_for_timeout(400)


def test_no_price_is_broken_across_two_lines(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            _select_everything(page)
            with page.expect_download(timeout=60000) as dl:
                page.click("#plDownloadPdfBtn")
            pdf = tmp_path / "pricelist.pdf"
            dl.value.save_as(str(pdf))
            assert not alerts, f"alert fired during export: {alerts}"

    with fitz.open(str(pdf)) as doc:
        text = "\n".join(pg.get_text() for pg in doc)

    wide = WIDE_PRICE_RE.findall(text)
    assert len(wide) > 20, (
        f"only {len(wide)} four-figure prices in the document - the fixture is not "
        "exercising the wide-price families and this guard proves nothing"
    )

    orphans = [ln.strip() for ln in text.splitlines() if ORPHAN_RE.match(ln.strip())]
    assert not orphans, (
        f"{len(orphans)} line(s) contain nothing but a digit or two "
        f"({orphans[:8]}) - a price was broken across two lines"
    )

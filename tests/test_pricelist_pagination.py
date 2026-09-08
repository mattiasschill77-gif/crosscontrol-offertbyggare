"""The price list PDF's family heading (v1.8.0).

buildPricelistDocDefinition pushed each family as two independent content nodes -
a one-row table holding the grey band, then the product table - so a page break
could fall between them and the band printed alone at the foot of a page. The
next page then opened with prices under no heading at all.

The band is located by FONT, not by string: it is the only text drawn in Poppins
whose content equals a family name. Product descriptions contain the same words
("CCpilot V1200, LinX Base") but are drawn in Roboto, so a text-only search would
match those and the guard would pass vacuously.
"""
import re

import fitz
from playwright.sync_api import sync_playwright

from harness import app_page, serve

PART_RE = re.compile(r"^[A-Z]\d{3}")   # C000 144-05, S020 156-50, C000082-26


def _select_everything(page):
    """Every product and every accessory, so the PDF runs to several pages."""
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


def _family_names(page):
    return page.evaluate("plSections(PRICE_DATA).map(g => g.group)")


def _spans(pdf_page):
    for block in pdf_page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                yield span


def test_a_family_band_is_never_below_every_product_row_on_its_page(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            _select_everything(page)
            families = set(_family_names(page))

            with page.expect_download(timeout=60000) as dl:
                page.click("#plDownloadPdfBtn")
            pdf = tmp_path / "pricelist.pdf"
            dl.value.save_as(str(pdf))
            assert not alerts, f"alert fired during export: {alerts}"

    bands_seen = 0
    with fitz.open(str(pdf)) as doc:
        assert doc.page_count > 2, "the fixture must span pages or this proves nothing"
        for n, pdf_page in enumerate(doc, start=1):
            band_ys, row_ys = [], []
            for span in _spans(pdf_page):
                text = span["text"].strip()
                if "Poppins" in span["font"] and text in families:
                    band_ys.append(span["bbox"][1])
                elif PART_RE.match(text):
                    row_ys.append(span["bbox"][1])
            if not band_ys:
                continue
            bands_seen += len(band_ys)
            assert row_ys, f"page {n} carries a family band and no product row at all"
            assert max(row_ys) > max(band_ys), (
                f"page {n}: a family band is below every product row on the page - "
                "it was stranded at the foot"
            )

    assert bands_seen, "no family band was found in the PDF - the probe is vacuous"

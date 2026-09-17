"""The v1.9.0 quote restyle, approved on the mockup 2026-09-17.

These read the PDF's own structure with PyMuPDF - fonts, drawings, image
placement - because every one of these changes is invisible to a text assertion.
"""
import json
import pathlib
import subprocess
import sys

import fitz  # PyMuPDF
import pytest
from playwright.sync_api import sync_playwright

from harness import app_page, download_quote_pdf, serve

ORANGE = (0xF7 / 255, 0x97 / 255, 0x1C / 255)
REPO = pathlib.Path(__file__).resolve().parents[1]

try:
    import weasyprint  # noqa: F401
    HAVE_WEASY = True
except Exception:  # OSError when Pango is missing, not ImportError
    HAVE_WEASY = False


def _one_line_pdf(page, alerts, out):
    page.fill("#custName", "Caudwell Marine Ltd")
    page.evaluate("cart = []; addProductToCart('C000 144-05'); renderAll();")
    page.wait_for_timeout(300)
    return download_quote_pdf(page, alerts, out)


def _first_page(pdf_path):
    return fitz.open(pdf_path)[0]


def _spans_containing(pg, needle):
    return [
        s for b in pg.get_text("dict")["blocks"] if b.get("type") == 0
        for l in b["lines"] for s in l["spans"] if needle in s["text"]
    ]


def test_the_pdf_uses_only_helvetica(tmp_path):
    """Owner's call: pdfmake's built-in Helvetica, nothing embedded. Reader
    substitutes Arial for it on Windows."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            pdf = _one_line_pdf(page, alerts, tmp_path / "q.pdf")
    doc = fitz.open(pdf)
    names = {f[3] for pg in doc for f in pg.get_fonts()}
    assert names, "no fonts at all - the probe is vacuous"
    assert all(n.startswith("Helvetica") for n in names), names
    assert not any("Roboto" in n or "Poppins" in n for n in names), names


def test_the_orange_rule_is_gone_from_the_header(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            pdf = _one_line_pdf(page, alerts, tmp_path / "q.pdf")
    pg = _first_page(pdf)
    # A 4 pt orange stroke across the page, above y=110, is the old rule.
    rules = [
        d for d in pg.get_drawings()
        if d.get("color") and all(abs(a - b) < 0.02 for a, b in zip(d["color"], ORANGE))
        and d.get("width", 0) >= 3 and d["rect"].y1 < 110
    ]
    assert not rules, f"the orange header rule is still drawn: {[r['rect'] for r in rules]}"


def test_the_logo_is_200pt_wide(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            pdf = _one_line_pdf(page, alerts, tmp_path / "q.pdf")
    pg = _first_page(pdf)
    imgs = pg.get_image_info()
    assert imgs, "no image on page 1 - where is the logo?"
    logo = max(imgs, key=lambda i: i["bbox"][2] - i["bbox"][0])
    width = logo["bbox"][2] - logo["bbox"][0]
    assert abs(width - 200) < 1.5, f"logo is {width:.1f} pt wide, expected 200"


def test_there_is_room_between_the_logo_and_the_title(tmp_path):
    """The 200 pt logo is 16 pt taller than the old one. Without the larger top
    margin it sits on PRICE QUOTE - measured on the mockup before the change."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            pdf = _one_line_pdf(page, alerts, tmp_path / "q.pdf")
    pg = _first_page(pdf)
    logo = max(pg.get_image_info(), key=lambda i: i["bbox"][2] - i["bbox"][0])
    title = pg.search_for("PRICE QUOTE")
    assert title, "PRICE QUOTE not found on page 1"
    gap = title[0].y0 - logo["bbox"][3]
    # search_for's rect includes ~8 pt of ascender padding above the caps at
    # 24 pt, so the visible ~29 pt gap measures ~21 here. Before the change
    # this measured about -9: the old layout left 3 pt.
    assert gap >= 18, f"only {gap:.1f} pt between the logo and the title"


def test_the_part_number_is_bold_and_in_ink(tmp_path):
    """Marketing: the part number was too hard to see. 9 pt grey -> 10 pt bold ink."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            pdf = _one_line_pdf(page, alerts, tmp_path / "q.pdf")
    pg = _first_page(pdf)
    spans = _spans_containing(pg, "C000 144-05")
    assert spans, "part number not found as a text span"
    s = spans[0]
    assert "Bold" in s["font"], f"part number is set in {s['font']}"
    assert s["size"] >= 10, f"part number is {s['size']} pt"
    assert s["color"] == 0x2B2B2A, f"part number colour is #{s['color']:06x}, expected the ink"


def test_unit_price_heading_is_one_line_and_clear_of_qty(tmp_path):
    """Marketing: the two headings were too close to tell apart. Cause: the
    column was as narrow as the price, so UNIT PRICE wrapped and its second
    line sat 12 pt from QTY."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            pdf = _one_line_pdf(page, alerts, tmp_path / "q.pdf")
    pg = _first_page(pdf)
    unit = pg.search_for("UNIT PRICE")
    assert len(unit) == 1, f"UNIT PRICE found {len(unit)} times - it wraps or is missing"
    qty = pg.search_for("QTY")
    assert qty, "QTY heading not found"
    gap = qty[0].x0 - unit[0].x1
    # 6 pt on the price side + 22 pt on the qty side (was 6 + 6 = 12).
    assert gap >= 26, f"only {gap:.1f} pt between UNIT PRICE and QTY"


def _computed(page, selector, prop):
    return page.evaluate(
        "([s, p]) => getComputedStyle(document.querySelector(s))[p]", [selector, prop]
    )


def _rect(page, selector):
    return page.evaluate(
        "(s) => document.querySelector(s).getBoundingClientRect().toJSON()", selector
    )


def test_the_screen_document_matches():
    """The same restyle on the on-screen preview, which is what gets checked
    before a quote is sent."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.evaluate("cart = []; addProductToCart('C000 144-05'); renderAll();")
            page.wait_for_timeout(300)
            rule = _computed(page, "#docRoot .doc-header", "borderBottomWidth")
            logo = _rect(page, "#docRoot .doc-logo svg")
            title = _rect(page, "#docRoot .doc-title-bar h1")
            h1_font = _computed(page, "#docRoot .doc-title-bar h1", "fontFamily")
            sku_weight = _computed(page, "#docRoot table.quote-table .psku", "fontWeight")
            sku_color = _computed(page, "#docRoot table.quote-table .psku", "color")
            name_color = _computed(page, "#docRoot table.quote-table .pname", "color")
            # The TEXT extent of each heading (a Range), not the cell: adjacent
            # cells touch, so the cell boxes would always report a 0 gap.
            boxes = page.evaluate("""() => [...document.querySelectorAll('#docRoot table.quote-table th')].map(th => {
                const r = document.createRange(); r.selectNodeContents(th);
                return r.getBoundingClientRect().toJSON();
            })""")
    assert rule == "0px", f"the screen header still has a {rule} rule"
    assert abs(logo["height"] - 75) < 1, f"screen logo is {logo['height']}px tall, expected 75"
    assert "Poppins" not in h1_font, h1_font
    assert int(sku_weight) >= 700, f"part number weight {sku_weight}"
    assert sku_color == name_color, f"part number {sku_color} vs product name {name_color}"
    unit, qty = boxes[-3], boxes[-2]
    # PRODUCT is one line; a wrapped UNIT PRICE is a line taller than it.
    assert abs(unit["height"] - boxes[0]["height"]) < 2, "UNIT PRICE wraps on screen"
    assert qty["x"] - (unit["x"] + unit["width"]) >= 24, "UNIT PRICE and QTY are too close"
    assert title["y"] - (logo["y"] + logo["height"]) >= 36, "not enough room above the title"


@pytest.mark.skipif(not HAVE_WEASY, reason="weasyprint not usable in this process")
def test_the_weasyprint_pdf_matches(tmp_path):
    """The third surface. generate_pdf.py duplicates the CSS by hand (HANDOFF §6)."""
    json_path, pdf_path = tmp_path / "q.json", tmp_path / "q.pdf"
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.evaluate("cart = []; addProductToCart('C000 144-05'); renderAll();")
            offer = page.evaluate("buildExportObj()")
    json_path.write_text(json.dumps(offer), encoding="utf-8")
    r = subprocess.run([sys.executable, "generate_pdf.py", str(json_path), "-o", str(pdf_path)],
                       cwd=str(REPO), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    doc = fitz.open(pdf_path)
    names = {f[3] for pg in doc for f in pg.get_fonts()}
    assert not any("Poppins" in n for n in names), names
    pg = doc[0]
    rules = [d for d in pg.get_drawings()
             if d.get("fill") and all(abs(a - b) < 0.02 for a, b in zip(d["fill"], ORANGE))
             and d["rect"].width > 400 and d["rect"].y1 < 120]
    assert not rules, "the orange header rule is still drawn on the WeasyPrint path"
    unit = pg.search_for("UNIT PRICE")
    assert len(unit) == 1, "UNIT PRICE wraps on the WeasyPrint path"
    spans = _spans_containing(pg, "C000 144-05")
    assert spans and "Bold" in spans[0]["font"], "part number is not bold on the WeasyPrint path"

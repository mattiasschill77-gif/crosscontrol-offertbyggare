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

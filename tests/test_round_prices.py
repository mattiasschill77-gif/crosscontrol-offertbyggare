"""Round prices to whole units (v1.9.0).

Owner's rule, from the mockup: the UNIT price is rounded to a whole unit of the
display currency, and the line total is that rounded unit x qty. Rounding each
printed figure on its own gives 658.26 x 2 -> 658 and 1,317, which does not
multiply out (HANDOFF §27, §29).
"""
import json
import pathlib
import re
import subprocess
import sys

import pytest
from playwright.sync_api import sync_playwright

from harness import app_page, download_quote_pdf, page_texts, serve

VI = "C000 144-05"      # CCpilot VI - 2,929.34 kr at 11.4; 2,929 x 15 = 43,935
REPO = pathlib.Path(__file__).resolve().parents[1]

try:
    import weasyprint  # noqa: F401
    HAVE_WEASY = True
except Exception:  # OSError when Pango is missing, not ImportError
    HAVE_WEASY = False


def _money(text):
    return float(re.sub(r"[^0-9.\-]", "", text.replace(",", "")))


def _row(page):
    cells = page.locator("#docRoot table.quote-table tbody tr").first.locator("td.num")
    nums = [t.strip() for t in cells.all_inner_texts() if t.strip()]
    return nums[-3], int(nums[-2]), nums[-1]


def _sek_line(page, qty=15):
    page.fill("#custName", "Caudwell Marine Ltd")
    page.select_option("#currencySelect", "SEK")
    page.evaluate("(q) => { cart = []; addProductToCart(%r); cart[0].qty = q; renderAll(); }" % VI, qty)
    page.wait_for_timeout(300)


def test_off_by_default_and_prints_cents():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            assert page.is_checked("#roundPrices") is False
            _sek_line(page)
            unit, qty, total = _row(page)
    assert unit == "2,929.34 kr" and total == "43,940.10 kr", (unit, total)


def test_on_rounds_the_unit_and_the_total_multiplies_out():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _sek_line(page)
            page.check("#roundPrices")
            page.wait_for_timeout(300)
            unit, qty, total = _row(page)
            subtotal = page.locator("#docRoot .totals-row.final span").last.inner_text()
    assert unit == "2,929 kr", unit
    assert total == "43,935 kr", f"{total} - expected 2,929 x 15, not round(43,940.10)"
    assert _money(unit) * qty == _money(total)
    assert subtotal.strip() == "43,935 kr"


def test_the_choice_survives_the_archive():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _sek_line(page)
            page.check("#roundPrices")
            # Past the 500 ms debounce, and NOT autoSaveNow(): the question is
            # whether the app saves it, so the test must not save on its behalf.
            page.wait_for_timeout(700)
            qid = page.evaluate("QUOTE_ID")
            saved = page.evaluate("(id) => loadArchive()[id].round_prices", qid)
            assert saved is True, "the checkbox was not autosaved"
            page.evaluate("startNewQuote()")
            assert page.is_checked("#roundPrices") is False, "a new quote must start with it off"
            page.evaluate("(id) => openQuote(id)", qid)
            page.wait_for_timeout(300)
            assert page.is_checked("#roundPrices") is True
            unit, _q, _t = _row(page)
    assert unit == "2,929 kr"


def test_a_pre_v19_record_opens_with_it_off():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _sek_line(page)
            page.check("#roundPrices")
            page.wait_for_timeout(700)
            qid = page.evaluate("QUOTE_ID")
            page.evaluate(
                "(id) => { const s = loadArchive(); delete s[id].round_prices; saveArchiveStore(s); }", qid
            )
            page.evaluate("(id) => openQuote(id)", qid)
            page.wait_for_timeout(300)
            assert page.is_checked("#roundPrices") is False


def test_the_pdfmake_pdf_prints_whole_units_that_multiply_out(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            _sek_line(page)
            page.check("#roundPrices")
            page.wait_for_timeout(300)
            assert page.evaluate("buildExportObj().round_prices") is True
            pdf = download_quote_pdf(page, alerts, tmp_path / "whole.pdf")
    flat = re.sub(r"\s+", " ", " ".join(page_texts(pdf)))
    assert "2,929 kr" in flat and "43,935 kr" in flat, flat[:600]
    assert "2,929.34" not in flat and "43,940" not in flat


@pytest.mark.skipif(not HAVE_WEASY, reason="weasyprint not usable in this process")
def test_the_weasyprint_pdf_prints_whole_units_that_multiply_out(tmp_path):
    json_path, pdf_path = tmp_path / "w.json", tmp_path / "w.pdf"
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _sek_line(page)
            page.check("#roundPrices")
            page.wait_for_timeout(300)
            offer = page.evaluate("buildExportObj()")
    json_path.write_text(json.dumps(offer), encoding="utf-8")
    r = subprocess.run([sys.executable, "generate_pdf.py", str(json_path), "-o", str(pdf_path)],
                       cwd=str(REPO), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    flat = re.sub(r"\s+", " ", " ".join(page_texts(pdf_path)))
    assert "2,929 kr" in flat and "43,935 kr" in flat
    assert "2,929.34" not in flat and "43,940" not in flat

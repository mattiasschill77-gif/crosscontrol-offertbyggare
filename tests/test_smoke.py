# tests/test_smoke.py
from playwright.sync_api import sync_playwright

from harness import app_page, build_long_quote, download_quote_pdf, page_texts, serve

EXPECTED_PRODUCTS = 129


def test_app_loads_and_exports_a_multipage_pdf(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            assert page.evaluate("FLAT_PRODUCTS.length") == EXPECTED_PRODUCTS
            assert isinstance(page.evaluate("FLAT_PRODUCTS[0].part_number"), str)
            build_long_quote(page)
            assert page.evaluate("cart.length") == 17
            pdf = download_quote_pdf(page, alerts, tmp_path / "smoke.pdf")
    texts = page_texts(pdf)
    assert len(texts) >= 3, f"expected a quote of 3+ pages, got {len(texts)}"

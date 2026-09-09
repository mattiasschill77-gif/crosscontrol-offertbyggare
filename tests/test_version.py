from playwright.sync_api import sync_playwright

from harness import app_page, serve

# ⚠️ A FOURTH thing that must be updated by hand at release time, alongside the
# three HANDOFF.md §18.1 lists (the constant, the git tag, the delivered file
# names). These three tests pin the literal deliberately - they are what catches
# a bump that was made in one place and forgotten in another - so they go red on
# every release until this is updated. That is the point, not a defect.
VERSION = "1.8.3"
BUILD_DATE = "2026-09-09"


def test_version_constants_exist():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            assert page.evaluate("APP_VERSION") == VERSION
            assert page.evaluate("APP_BUILD_DATE") == BUILD_DATE


def test_version_is_visible_in_the_topbar():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            assert f"v{VERSION}" in page.inner_text(".topbar-sub")


def test_version_is_stamped_into_the_export_and_the_archive():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number)")
            export = page.evaluate("buildExportObj()")
            snapshot = page.evaluate("buildQuoteSnapshot()")
    assert export["app_version"] == VERSION
    assert export["app_build_date"] == BUILD_DATE
    assert snapshot["app_version"] == VERSION


def test_version_never_reaches_the_customer_document():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number)")
            page.wait_for_timeout(300)
            live_version = page.evaluate("APP_VERSION")
            doc_text = page.inner_text("#docRoot")
    assert live_version not in doc_text

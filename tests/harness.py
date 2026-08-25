# tests/harness.py
import contextlib
import functools
import http.server
import pathlib
import socketserver
import threading

ROOT = pathlib.Path(__file__).resolve().parents[1]
PORT = 8142
APP_PATH = "/crosscontrol-offertbyggare.html"

socketserver.TCPServer.allow_reuse_address = True


@contextlib.contextmanager
def serve():
    """Serve the repo root over localhost. file:// is refused by Playwright."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{PORT}{APP_PATH}"
    finally:
        httpd.shutdown()
        httpd.server_close()


@contextlib.contextmanager
def app_page(playwright, url):
    """Open the app and yield (page, alerts). Any alert() is captured, never swallowed."""
    browser = playwright.chromium.launch()
    page = browser.new_page()
    alerts = []
    page.on("dialog", lambda d: (alerts.append(d.message), d.accept()))
    page.goto(url)
    page.wait_for_function(
        "typeof addProductToCart === 'function'"
        " && typeof FLAT_PRODUCTS !== 'undefined' && FLAT_PRODUCTS.length > 0"
    )
    try:
        yield page, alerts
    finally:
        browser.close()


def build_long_quote(page, n_products=16):
    """Build a quote long enough to run past three pages."""
    page.fill("#custName", "Husco International")
    page.evaluate(
        "(n) => { FLAT_PRODUCTS.slice(0, n).forEach(p => addProductToCart(p.part_number)); }",
        n_products,
    )
    page.wait_for_timeout(400)


def download_quote_pdf(page, alerts, out_path):
    """Click the real export button and save the PDF. Asserts no alert fired:
    the button restores its own label in the failure path, so a restored label
    is not a pass signal — a download event and a silent page are."""
    with page.expect_download(timeout=30000) as dl:
        page.click("#downloadPdfBtn")
    dl.value.save_as(str(out_path))
    assert not alerts, f"alert fired during export: {alerts}"
    return out_path


def page_texts(pdf_path):
    """Text of each PDF page, newlines flattened, as a list."""
    import fitz

    with fitz.open(str(pdf_path)) as doc:
        return [p.get_text().replace("\n", " ") for p in doc]

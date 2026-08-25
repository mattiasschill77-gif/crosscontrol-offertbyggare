"""The WeasyPrint path: generate_pdf.py rendering an exported quote JSON.

Skipped when weasyprint cannot be imported. On Windows it needs the MSYS2
Pango stack reachable, which WeasyPrint finds through the user environment
variable WEASYPRINT_DLL_DIRECTORIES (set to C:\\msys64\\mingw64\\bin here).
A shell started before that variable existed will not see it - pass it inline:

    WEASYPRINT_DLL_DIRECTORIES="C:\\msys64\\mingw64\\bin" python -m pytest tests/ -v
"""
import json
import pathlib
import re
import subprocess
import sys

import pytest
from playwright.sync_api import sync_playwright

from harness import app_page, build_long_quote, page_texts, serve

try:
    # Not pytest.importorskip: a missing Pango raises OSError, not ImportError,
    # so importorskip lets it through and the whole module errors at collection.
    import weasyprint  # noqa: F401
except Exception as exc:  # pragma: no cover - depends on the machine
    pytest.skip(
        f"weasyprint is not usable in this process ({exc.__class__.__name__}): {exc}",
        allow_module_level=True,
    )

REPO = pathlib.Path(__file__).resolve().parents[1]

TC_HEAD = "This quote is subject to CrossControl"
TC_TAIL = "agrees to be bound by these terms."


@pytest.fixture(scope="module")
def weasy_pages(tmp_path_factory):
    """Export a real quote through the app, then render it with the real CLI."""
    work = tmp_path_factory.mktemp("weasy")
    json_path = work / "quote.json"
    pdf_path = work / "quote.pdf"

    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            build_long_quote(page)
            offer = page.evaluate("buildExportObj()")
    json_path.write_text(json.dumps(offer), encoding="utf-8")

    # The real command line, from the repo root: generate_pdf.py reads
    # cc-logo.svg and the Poppins base64 files by relative path.
    result = subprocess.run(
        [sys.executable, "generate_pdf.py", str(json_path), "-o", str(pdf_path)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"generate_pdf.py failed:\n{result.stderr}"

    # pdfmake and WeasyPrint both leave a space before their own line wrap,
    # which extraction turns into a double space. Normalise, or an assertion
    # fails for a reason that has nothing to do with page breaks.
    texts = [re.sub(r"\s+", " ", t) for t in page_texts(pdf_path)]
    assert len(texts) >= 3, f"expected a quote of 3+ pages, got {len(texts)}"
    return texts


def test_header_and_footer_on_every_page(weasy_pages):
    """generate_pdf.py repeats both through @page running elements. This is the
    one thing on this surface that can genuinely regress."""
    total = len(weasy_pages)
    for i, text in enumerate(weasy_pages, start=1):
        assert "QUOTE #CC-" in text, f"header missing on page {i} of {total}"
        assert "info@crosscontrol.com" in text, f"footer missing on page {i} of {total}"


def test_terms_and_conditions_block_is_not_split(weasy_pages):
    """A regression guard rather than a fix. Measured 2026-08-25: .tc-reference
    is display:flex and WeasyPrint never fragments a flex container, so this
    already held before break-inside:avoid was added. It starts earning its
    keep the moment that block stops being flex."""
    hits = [i for i, t in enumerate(weasy_pages) if TC_HEAD in t]
    assert len(hits) == 1, f"{TC_HEAD!r} found on pages {hits}, expected exactly one"
    assert TC_TAIL in weasy_pages[hits[0]], "the T&C block is split across a page break"

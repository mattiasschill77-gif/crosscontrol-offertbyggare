# tests/test_pagination.py
import re

import pytest
from playwright.sync_api import sync_playwright

from harness import app_page, build_long_quote, download_quote_pdf, page_texts, serve

FORECAST_HEAD = "This quotation is made subject to the customer having submitted"
FORECAST_TAIL = "conditional upon receipt of that forecast."
TC_HEAD = "This quote is subject to CrossControl"
TC_TAIL = "agrees to be bound by these terms."


@pytest.fixture(scope="module")
def quote_pages(tmp_path_factory):
    out = tmp_path_factory.mktemp("pdf") / "quote.pdf"
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            build_long_quote(page, 100)
            download_quote_pdf(page, alerts, out)
    texts = page_texts(out)
    # pdfmake's own paragraph wrapping leaves a trailing space before the line
    # break it wraps on (e.g. "...buyer agrees \nto be bound..."); page_texts()
    # turns that into a run of two spaces that has nothing to do with page
    # breaks. Collapse whitespace so the split-detection tests only fire on a
    # genuine page break, not this unrelated wrap artifact (verified directly
    # against the raw PDF text stream before adding this normalization).
    texts = [re.sub(r"\s+", " ", t) for t in texts]
    assert len(texts) >= 3, f"expected 3+ pages, got {len(texts)}"
    return texts


def _single_page_containing(texts, head, tail):
    hits = [i for i, t in enumerate(texts) if head in t]
    assert len(hits) == 1, f"{head!r} found on pages {hits}, expected exactly one"
    assert tail in texts[hits[0]], f"block starting {head!r} is split across a page break"


def test_forecast_condition_is_not_split(quote_pages):
    _single_page_containing(quote_pages, FORECAST_HEAD, FORECAST_TAIL)


def test_terms_and_conditions_block_is_not_split(quote_pages):
    _single_page_containing(quote_pages, TC_HEAD, TC_TAIL)


def test_terms_heading_stays_with_its_content(quote_pages):
    hits = [i for i, t in enumerate(quote_pages) if "TERMS" in t and "Payment" in t]
    assert hits, "the TERMS heading and its grid ended up on different pages"


def test_header_and_footer_on_every_page(quote_pages):
    total = len(quote_pages)
    for i, text in enumerate(quote_pages, start=1):
        assert "QUOTE #CC-" in text, f"header missing on page {i} of {total}"
        assert "info@crosscontrol.com" in text, f"footer missing on page {i} of {total}"
        assert f"Page {i} of {total}" in text, f"page number wrong or missing on page {i}"

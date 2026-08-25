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
            assert page.evaluate("cart.length") == 101
            download_quote_pdf(page, alerts, out)
    texts = page_texts(out)
    # pdfmake's own paragraph wrapping leaves a trailing space before the line
    # break it wraps on (e.g. "...buyer agrees \nto be bound..."); page_texts()
    # turns that into a run of two spaces that has nothing to do with page
    # breaks. Collapse whitespace so the split-detection tests only fire on a
    # genuine page break, not this unrelated wrap artifact (verified directly
    # against the raw PDF text stream before adding this normalization).
    texts = [re.sub(r"\s+", " ", t) for t in texts]
    # This fixture relies on a specific 12-page quote (100 products) for a
    # protected block to actually land on a page boundary. >= 3 would still
    # pass on a much shorter catalogue where nothing lands near a break and
    # every test below proves nothing. Assert what we actually depend on.
    assert len(texts) >= 10, f"expected 10+ pages, got {len(texts)}"
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
    # "Currency" is one of the grid's later fields, not its first ("Payment"),
    # so this actually catches the grid splitting after its first row instead
    # of passing regardless of where inside the grid a break would land.
    hits = [i for i, t in enumerate(quote_pages) if "TERMS" in t and "Currency" in t]
    assert len(hits) == 1, f"the TERMS heading and its grid ended up on different pages ({hits})"


def test_header_and_footer_on_every_page(quote_pages):
    total = len(quote_pages)
    for i, text in enumerate(quote_pages, start=1):
        assert "QUOTE #CC-" in text, f"header missing on page {i} of {total}"
        assert "info@crosscontrol.com" in text, f"footer missing on page {i} of {total}"
        assert f"Page {i} of {total}" in text, f"page number wrong or missing on page {i}"


# A per-line note is a plain <textarea> with no maxlength anywhere in the
# file, and its placeholder invites long text. If a product row is ever made
# unbreakable (directly, or via pdfmake's row-level dontBreakRows), a note
# long enough to push the row past one page body doesn't move the row to the
# next page or clip it — pdfmake's commitUnbreakableBlock keeps only the
# first page's fragment and discards the rest. A single unbroken run of one
# repeated character doesn't trigger this (pdfmake treats it as one
# unbreakable "word" and never reflows it across enough lines to overflow a
# page); realistic wrapped prose does. This fixture is intentionally
# separate from quote_pages: it needs a tiny cart, not a 12-page one.
# The note below is ~4,900 characters, about 1.5x the ~3,200 needed to push
# a row past the 618 pt page body at the current column width and 9.5 pt
# note size (measured: 3,115 survives, 3,279 is deleted). Do not shorten it
# without re-measuring - a shorter note leaves the test green while proving
# nothing. "The note spans a page break" is NOT a sufficient check either;
# that is already true at ~2,950 characters, well below the trigger.
LONG_NOTE = " ".join(
    f"Scope item {i:03d}: engineering deliverable with acceptance criteria and assumptions."
    for i in range(60)
)


@pytest.fixture
def longnote_pdf_texts(tmp_path):
    out = tmp_path / "longnote.pdf"
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            build_long_quote(page, 3)
            assert page.evaluate("cart.length") == 5
            note_field = page.locator('#productList textarea[data-action="note"]').nth(1)
            note_field.fill(LONG_NOTE)
            page.wait_for_timeout(400)
            assert page.evaluate("cart[1].note.length") == len(LONG_NOTE)
            part_number = page.evaluate("cart[1].partNumber")
            download_quote_pdf(page, alerts, out)
    return page_texts(out), part_number


def test_long_note_does_not_delete_its_product_line(longnote_pdf_texts):
    texts, part_number = longnote_pdf_texts
    full = " ".join(texts)
    assert part_number in full, (
        f"product line {part_number!r} is entirely missing from the PDF "
        "after a long note on it — the row was silently dropped instead of "
        "being moved or clipped"
    )


# The VAT / Tariff note and the Named place are free-text <input>s with no
# maxlength, and both feed the TERMS grid. A long paste is realistic: a customs
# or tariff clause for a US customer. Measured 2026-08-25: an unbreakable terms
# block exceeds one page body at ~2,100 characters, and pdfmake then deletes the
# whole block - heading, payment terms, validity, delivery terms and currency -
# while the on-screen preview still shows it. This note is ~2,600 characters, a
# little over that threshold. Do not shorten it without re-measuring.
LONG_VAT_NOTE = " ".join(
    f"Clause {i:02d}: prices exclude VAT, duties and tariffs applicable at import."
    for i in range(35)
)


@pytest.fixture
def longvat_pdf_texts(tmp_path):
    out = tmp_path / "longvat.pdf"
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            build_long_quote(page, 3)
            page.fill("#vatNote", LONG_VAT_NOTE)
            page.wait_for_timeout(400)
            assert page.evaluate("document.getElementById('vatNote').value.length") == len(
                LONG_VAT_NOTE
            )
            on_screen = page.inner_text("#docRoot")
            download_quote_pdf(page, alerts, out)
    return [re.sub(r"\s+", " ", t) for t in page_texts(out)], on_screen


def test_long_vat_note_does_not_delete_the_terms_block(longvat_pdf_texts):
    texts, on_screen = longvat_pdf_texts
    assert "Payment terms" in on_screen, "the screen lost the terms block - different bug"
    full = " ".join(texts)
    assert "Payment terms" in full, (
        "the TERMS block is entirely missing from the PDF after a long VAT note - "
        "the commercial terms were silently dropped while the screen still showed them"
    )
    assert "Validity" in full, "the TERMS block reached the PDF only partly"

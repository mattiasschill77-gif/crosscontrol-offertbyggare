"""Deleting a quote from the local archive.

The owner's rule for the customer folder was: the local copy is always kept,
"unless you deliberately remove it in the archive". That deliberate removal did
not exist - every row had only an Open button - so half the rule was
unfulfillable and the archive grew forever, carrying customer names with it.

The trap: autosave writes store[QUOTE_ID] on every change, so deleting the
quote you currently have open would resurrect it on the next keystroke.
"""
from playwright.sync_api import sync_playwright

from harness import app_page, build_long_quote, serve


def _delete(page, quote_id):
    page.click("#openArchiveBtn")
    page.wait_for_timeout(200)
    page.click(f'.archive-delete-btn[data-quote-id="{quote_id}"]')
    page.wait_for_timeout(400)


def test_deleting_removes_the_quote_from_the_archive():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            build_long_quote(page, 2)
            page.fill("#custName", "Doomed Customer")
            page.wait_for_timeout(700)
            doomed = page.evaluate("QUOTE_ID")
            page.evaluate("startNewQuote()")
            page.wait_for_timeout(500)
            _delete(page, doomed)
            store = page.evaluate("loadArchive()")
    assert doomed not in store


def test_cancelling_the_confirm_deletes_nothing():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            build_long_quote(page, 2)
            page.fill("#custName", "Spared Customer")
            page.wait_for_timeout(700)
            spared = page.evaluate("QUOTE_ID")
            page.evaluate("startNewQuote()")
            page.wait_for_timeout(500)
            page.evaluate("() => { window.confirm = () => false; }")
            _delete(page, spared)
            store = page.evaluate("loadArchive()")
    assert spared in store, "the quote was deleted even though the user cancelled"
    assert store[spared]["customer_name"] == "Spared Customer"


def test_deleting_the_open_quote_does_not_resurrect_it():
    """The trap. Autosave keys on QUOTE_ID, so unless the app moves off the
    deleted quote, the next edit writes it straight back."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            build_long_quote(page, 2)
            page.fill("#custName", "Open And Doomed")
            page.wait_for_timeout(700)
            doomed = page.evaluate("QUOTE_ID")
            _delete(page, doomed)
            # Type something: this is what used to bring it back.
            page.fill("#custName", "Typing after the delete")
            page.wait_for_timeout(900)
            store = page.evaluate("loadArchive()")
            now_open = page.evaluate("QUOTE_ID")
    assert doomed not in store, "the deleted quote came back on the next edit"
    assert now_open != doomed, "the app is still working on a quote it just deleted"


def test_deleting_one_quote_leaves_the_open_one_alone():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            build_long_quote(page, 2)
            page.fill("#custName", "Old Quote")
            page.wait_for_timeout(700)
            old = page.evaluate("QUOTE_ID")
            page.evaluate("startNewQuote()")
            page.wait_for_timeout(500)
            build_long_quote(page, 2)
            page.fill("#custName", "Current Quote")
            page.wait_for_timeout(700)
            current = page.evaluate("QUOTE_ID")
            _delete(page, old)
            store = page.evaluate("loadArchive()")
            still_open = page.evaluate("QUOTE_ID")
    assert old not in store
    assert current in store
    assert still_open == current, "deleting another quote moved the app off this one"


def test_the_delete_button_does_not_also_open_the_quote():
    """The whole row opens the quote, so the delete button must not fall through."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            build_long_quote(page, 2)
            page.fill("#custName", "Other Quote")
            page.wait_for_timeout(700)
            other = page.evaluate("QUOTE_ID")
            page.evaluate("startNewQuote()")
            page.wait_for_timeout(500)
            current = page.evaluate("QUOTE_ID")
            _delete(page, other)
            still_open = page.evaluate("QUOTE_ID")
    assert still_open == current, "clicking Delete also opened the quote"

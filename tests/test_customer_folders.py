"""The folder a customer's quotes are saved into, remembered between sessions.

A real FileSystemDirectoryHandle cannot be minted headlessly - it only comes
from a native picker - so these tests store a stand-in object. What is being
tested is the store's own behaviour: keying, isolation, and that an empty
customer name is never used as a key.
"""
from playwright.sync_api import sync_playwright

from harness import app_page, serve


def test_a_folder_is_remembered_under_the_customer_name():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            got = page.evaluate(
                "async (stub) => { await rememberFolder('Husco International', stub);"
                " const back = await recallFolder('Husco International');"
                " return back && back.name; }",
                {"kind": "directory", "name": "Husco"},
            )
    assert got == "Husco"


def test_customers_do_not_share_a_folder():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            got = page.evaluate(
                "async () => { await rememberFolder('A', {name:'folder-a'});"
                " await rememberFolder('B', {name:'folder-b'});"
                " const a = await recallFolder('A'); const b = await recallFolder('B');"
                " return [a && a.name, b && b.name]; }"
            )
    assert got == ["folder-a", "folder-b"]


def test_an_unknown_customer_has_no_folder():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            got = page.evaluate("async () => await recallFolder('Nobody')")
    assert got is None


def test_an_empty_customer_name_is_never_used_as_a_key():
    """Otherwise every nameless quote would share one folder under ''."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            got = page.evaluate(
                "async () => { await rememberFolder('   ', {name:'nope'});"
                " return [await recallFolder('   '), await recallFolder('')]; }"
            )
    assert got == [None, None]


def test_the_name_is_matched_after_trimming():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            got = page.evaluate(
                "async () => { await rememberFolder('Husco', {name:'f'});"
                " const back = await recallFolder('  Husco  '); return back && back.name; }"
            )
    assert got == "f"


def test_a_machine_without_indexeddb_does_not_break_the_app():
    """recallFolder must degrade to 'no folder remembered', not throw."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            got = page.evaluate(
                "async () => { const real = window.indexedDB;"
                " Object.defineProperty(window, 'indexedDB', { value: { open() { throw new Error('blocked'); } }, configurable: true });"
                " const back = await recallFolder('Husco');"
                " Object.defineProperty(window, 'indexedDB', { value: real, configurable: true });"
                " return back; }"
            )
    assert got is None

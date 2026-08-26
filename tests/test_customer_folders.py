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


# --- saving into the folder ---------------------------------------------------

FAKE_DIR = """
(existing) => {
  const opened = [];
  return {
    kind: 'directory',
    opened,
    queryPermission: async () => 'granted',
    requestPermission: async () => 'granted',
    getFileHandle: async (name, opts) => {
      opened.push({ name, create: !!(opts && opts.create) });
      if (!opts || !opts.create) {
        if (existing.includes(name)) return { name };
        throw new DOMException('missing', 'NotFoundError');
      }
      return { name, createWritable: async () => ({ write: async () => {}, close: async () => {} }) };
    },
  };
}
"""


def test_the_archive_copy_is_written_before_anything_leaves_the_app():
    """The owner's rule: the local backup is never optional. Even when the folder
    save fails outright, the quote must be in the archive."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.evaluate(
                "() => { window.showDirectoryPicker = () => { throw new DOMException('nope', 'SecurityError'); }; }"
            )
            page.fill("#custName", "Husco International")
            page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number)")
            page.wait_for_timeout(300)
            quote_id = page.evaluate("QUOTE_ID")
            try:
                page.evaluate("saveQuoteToCustomerFolder()")
            except Exception:
                pass
            page.wait_for_timeout(1200)
            store = page.evaluate("loadArchive()")
    assert quote_id in store, "the archive copy was not written"
    assert store[quote_id]["customer_name"] == "Husco International"


def test_a_machine_without_the_api_still_gets_its_pdf(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            page.evaluate("() => { delete window.showDirectoryPicker; }")
            page.fill("#custName", "No API Customer")
            page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number)")
            page.wait_for_timeout(300)
            with page.expect_download(timeout=30000) as dl:
                page.evaluate("saveQuoteToCustomerFolder()")
            dl.value.save_as(str(tmp_path / "fallback.pdf"))
    assert (tmp_path / "fallback.pdf").stat().st_size > 0
    assert any("download" in a.lower() for a in alerts), f"the user was not told why: {alerts}"


def test_a_blocked_api_falls_back_instead_of_losing_the_file(tmp_path):
    """An API can exist and still throw under corporate policy."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            page.evaluate(
                "() => { window.showDirectoryPicker = () => { throw new DOMException('blocked', 'SecurityError'); }; }"
            )
            page.fill("#custName", "Blocked Customer")
            page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number)")
            page.wait_for_timeout(300)
            with page.expect_download(timeout=30000) as dl:
                page.evaluate("saveQuoteToCustomerFolder()")
            dl.value.save_as(str(tmp_path / "blocked.pdf"))
    assert (tmp_path / "blocked.pdf").stat().st_size > 0


def test_cancelling_the_picker_is_quiet():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            page.evaluate(
                "() => { window.showDirectoryPicker = () => { throw new DOMException('user aborted', 'AbortError'); }; }"
            )
            page.fill("#custName", "Cancelled Customer")
            page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number)")
            page.wait_for_timeout(300)
            page.evaluate("saveQuoteToCustomerFolder()")
            page.wait_for_timeout(800)
    assert not alerts, f"cancelling should say nothing, got {alerts}"


def test_a_free_name_is_used_as_is():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            got = page.evaluate(
                "async (mk) => { const dir = eval('(' + mk + ')')([]);"
                " return await pickTargetName(dir, 'quote-CC-2026-0001.pdf'); }",
                FAKE_DIR,
            )
    assert got == "quote-CC-2026-0001.pdf"


def test_replacing_is_only_done_when_the_user_says_so():
    """The harness accepts every dialog, so confirm() is true here: OK = replace."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            got = page.evaluate(
                "async (mk) => { const dir = eval('(' + mk + ')')(['quote-CC-2026-0001.pdf']);"
                " return await pickTargetName(dir, 'quote-CC-2026-0001.pdf'); }",
                FAKE_DIR,
            )
    assert got == "quote-CC-2026-0001.pdf"


def test_declining_keeps_both_files():
    """The branch that protects an existing file. Cancel = keep both."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            got = page.evaluate(
                "async (mk) => { window.confirm = () => false;"
                " const dir = eval('(' + mk + ')')(['quote-CC-2026-0001.pdf']);"
                " const name = await pickTargetName(dir, 'quote-CC-2026-0001.pdf');"
                " return { name, opened: dir.opened.filter(o => o.create).map(o => o.name) }; }",
                FAKE_DIR,
            )
    assert got["name"] == "quote-CC-2026-0001-2.pdf", got
    assert "quote-CC-2026-0001.pdf" not in got["opened"], "the existing file was opened for writing"


def test_declining_twice_walks_past_both_files():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            got = page.evaluate(
                "async (mk) => { window.confirm = () => false;"
                " const dir = eval('(' + mk + ')')(['quote-CC-2026-0001.pdf', 'quote-CC-2026-0001-2.pdf']);"
                " return await pickTargetName(dir, 'quote-CC-2026-0001.pdf'); }",
                FAKE_DIR,
            )
    assert got == "quote-CC-2026-0001-3.pdf"

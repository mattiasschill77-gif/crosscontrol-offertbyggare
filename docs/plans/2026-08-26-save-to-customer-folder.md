# Save the quote into a customer folder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the owner write a quote straight into that customer's folder, remembered per customer, without ever weakening the local archive copy.

**Architecture:** File System Access API for the folder, IndexedDB for the remembered handle, `pdfMake…getBlob()` for the bytes. Spec: `docs/specs/2026-08-26-save-to-customer-folder.md`. Everything is additive — `Download quote as PDF` is untouched and its tests must keep passing.

**Tech stack:** vanilla JS in `crosscontrol-offertbyggare.html`; the Playwright + PyMuPDF suite in `tests/` (53 tests on `main`).

**Measured before planning, so nothing here rests on a guess:**
- `showDirectoryPicker`, `showSaveFilePicker` and `indexedDB` are all present **and callable** from `file://` in the owner's Chrome (`HANDOFF.md` §19).
- `pdfMake.createPdf(dd).getBlob()` returns a Promise resolving to an `application/pdf` Blob (57 KB for a two-line quote).
- `ccToast(msg)` and `autoSaveNow()` already exist and are the right helpers to reuse.

⚠️ **What cannot be tested automatically:** Playwright cannot drive a native folder picker. Tasks 1 and 2 cover the store, the ordering, the collision logic and the fallback. The picker itself is a **device gate** in Task 3, run by the owner. Do not fake a pass for it.

**Repo rules:** stage by name, never `git add -A` · the HTML has megabyte-long lines — never `grep -c` it (`grep -o … | wc -l`), never load it wholesale · `serve()` refuses to start if something already listens on 8142 · run the suite from the repo root.

---

## Task 1: Remember a folder per customer

**Files:** modify `crosscontrol-offertbyggare.html` · create `tests/test_customer_folders.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_customer_folders.py
"""The folder a customer's quotes are saved into, remembered between sessions.

A real FileSystemDirectoryHandle cannot be minted headlessly - it only comes
from a native picker - so these tests store a stand-in object. What is being
tested is the store's own behaviour: keying, isolation, and that an empty
customer name is never used as a key.
"""
from playwright.sync_api import sync_playwright

from harness import app_page, serve

STUB = "{ kind: 'directory', name: 'Husco' }"


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
```

- [ ] **Step 2: Run it and watch it fail.** `rememberFolder is not defined`. Report the output.

- [ ] **Step 3: Implement the store**, next to the other storage helpers:

```js
// ===== CUSTOMER FOLDERS =====
// Which folder this customer's quotes are written into. A directory handle is
// structured-cloneable, so IndexedDB can hold it and localStorage cannot.
const FOLDER_DB = 'cc_customer_folders_v1';
const FOLDER_STORE = 'folders';

function folderDb() {
  return new Promise((resolve, reject) => {
    let req;
    try { req = indexedDB.open(FOLDER_DB, 1); } catch (e) { reject(e); return; }
    req.onupgradeneeded = () => { req.result.createObjectStore(FOLDER_STORE); };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error || new Error('IndexedDB is not available'));
  });
}

async function rememberFolder(customer, handle) {
  const key = (customer || '').trim();
  if (!key) return;  // no customer name, nothing to remember it under
  const db = await folderDb();
  try {
    await new Promise((res, rej) => {
      const tx = db.transaction(FOLDER_STORE, 'readwrite');
      tx.objectStore(FOLDER_STORE).put(handle, key);
      tx.oncomplete = res;
      tx.onerror = () => rej(tx.error);
    });
  } finally { db.close(); }
}

async function recallFolder(customer) {
  const key = (customer || '').trim();
  if (!key) return null;
  try {
    const db = await folderDb();
    try {
      return await new Promise((res, rej) => {
        const tx = db.transaction(FOLDER_STORE, 'readonly');
        const req = tx.objectStore(FOLDER_STORE).get(key);
        req.onsuccess = () => res(req.result || null);
        req.onerror = () => rej(req.error);
      });
    } finally { db.close(); }
  } catch (e) {
    return null;  // no IndexedDB on this machine: ask for the folder each time
  }
}
```

- [ ] **Step 4: Run the new tests, then the whole suite.** 53 existing + 5 new.

- [ ] **Step 5: Commit.**

```bash
git add crosscontrol-offertbyggare.html tests/test_customer_folders.py
git commit -m "feat: remember which folder a customer's quotes are saved into"
```

---

## Task 2: Save into the folder, and never lose a file doing it

⚠️ **One commit.** A write path without the collision check can destroy a saved quote, and a save path without the archive-first ordering can lose one.

**Files:** modify `crosscontrol-offertbyggare.html` · modify `tests/test_customer_folders.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_the_archive_copy_is_written_before_anything_leaves_the_app():
    """The owner's rule: the local backup is never optional. Even when the
    folder save fails outright, the quote must be in the archive."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            page.evaluate("() => { window.showDirectoryPicker = () => { throw new DOMException('nope', 'SecurityError'); }; }")
            page.fill("#custName", "Husco International")
            page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number)")
            page.wait_for_timeout(300)
            quote_id = page.evaluate("QUOTE_ID")
            page.evaluate("saveQuoteToCustomerFolder()")
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
            page.evaluate("() => { window.showDirectoryPicker = () => { throw new DOMException('blocked', 'SecurityError'); }; }")
            page.fill("#custName", "Blocked Customer")
            page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number)")
            page.wait_for_timeout(300)
            with page.expect_download(timeout=30000) as dl:
                page.evaluate("saveQuoteToCustomerFolder()")
            dl.value.save_as(str(tmp_path / "blocked.pdf"))
    assert (tmp_path / "blocked.pdf").stat().st_size > 0


def test_cancelling_the_picker_is_quiet_and_writes_nothing(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            page.evaluate("() => { window.showDirectoryPicker = () => { throw new DOMException('user aborted', 'AbortError'); }; }")
            page.fill("#custName", "Cancelled Customer")
            page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number)")
            page.wait_for_timeout(300)
            page.evaluate("saveQuoteToCustomerFolder()")
            page.wait_for_timeout(1000)
    assert not alerts, f"cancelling should say nothing, got {alerts}"


def test_an_existing_file_is_never_replaced_without_asking():
    """A fake directory handle records what was asked for and what was written."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            written = page.evaluate("""async () => {
                const asked = [];
                const dir = {
                  kind: 'directory',
                  queryPermission: async () => 'granted',
                  requestPermission: async () => 'granted',
                  getFileHandle: async (name, opts) => {
                    asked.push(name);
                    if (!opts || !opts.create) {
                      if (name === 'quote-CC-2026-0001.pdf') return { name };
                      throw new DOMException('missing', 'NotFoundError');
                    }
                    return { name, createWritable: async () => ({ write: async () => {}, close: async () => {} }) };
                  },
                };
                const target = await pickTargetName(dir, 'quote-CC-2026-0001.pdf');
                return { target, asked };
            }""")
    # The dialog is auto-accepted by the harness, which means "replace it".
    assert written["target"] == "quote-CC-2026-0001.pdf"
    assert "quote-CC-2026-0001.pdf" in written["asked"]
```

⚠️ The harness accepts every dialog, so `confirm()` returns **true** in tests. Word the confirm so that **OK = replace** and **Cancel = keep both**, and add a second test that drives the keep-both branch by stubbing `window.confirm` to return false. Write that test too — the branch that protects a file is the one that must be proven.

- [ ] **Step 2: Run and watch them fail.** Report the output.

- [ ] **Step 3: Implement**

```js
function folderSaveSupported() {
  return typeof window.showDirectoryPicker === 'function';
}

async function ensureFolderPermission(handle) {
  if (!handle || typeof handle.queryPermission !== 'function') return false;
  const opts = { mode: 'readwrite' };
  if (await handle.queryPermission(opts) === 'granted') return true;
  return (await handle.requestPermission(opts)) === 'granted';
}

// Never replace a file without being told to. Rev A must not vanish because
// rev B was saved into the same folder.
async function pickTargetName(dir, fileName) {
  let exists = true;
  try { await dir.getFileHandle(fileName); } catch (e) { exists = false; }
  if (!exists) return fileName;
  if (confirm(`${fileName} is already in that folder.\n\nOK — replace it\nCancel — keep both, and save this one under a new name`)) {
    return fileName;
  }
  const base = fileName.replace(/\.pdf$/i, '');
  for (let n = 2; ; n += 1) {
    const candidate = `${base}-${n}.pdf`;
    try { await dir.getFileHandle(candidate); } catch (e) { return candidate; }
  }
}

async function saveQuoteToCustomerFolder() {
  // The local copy first, always, before anything can go wrong.
  autoSaveNow();

  const customer = (document.getElementById('custName').value || '').trim();
  const fileName = `quote-${QUOTE_ID}.pdf`;

  if (!folderSaveSupported()) {
    alert('This browser cannot write straight into a folder, so the quote will download instead. Your archive copy is saved either way.');
    document.getElementById('downloadPdfBtn').click();
    return;
  }

  try {
    let dir = await recallFolder(customer);
    if (dir && !(await ensureFolderPermission(dir))) dir = null;
    if (!dir) {
      dir = await window.showDirectoryPicker({ mode: 'readwrite' });
      await rememberFolder(customer, dir);
    }
    const target = await pickTargetName(dir, fileName);
    const blob = await pdfMake.createPdf(buildPdfDocDefinition(buildExportObj())).getBlob();
    const fileHandle = await dir.getFileHandle(target, { create: true });
    const writable = await fileHandle.createWritable();
    await writable.write(blob);
    await writable.close();
    ccToast(`Saved ${target} to ${customer || 'the chosen folder'}.`);
  } catch (err) {
    if (err && err.name === 'AbortError') return;  // the picker was cancelled; say nothing
    alert('Could not write to that folder (' + ((err && err.name) || 'unknown') + '). The quote will download instead. Your archive copy is untouched.');
    document.getElementById('downloadPdfBtn').click();
  }
}
```

- [ ] **Step 4: Add the button**, in `.generate-bar` immediately after `#downloadPdfBtn`, matching the existing markup:

```html
      <button class="generate-btn" id="saveToFolderBtn"><svg class="cc-ico" viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>Save to customer folder…</button>
```

Wire it: `document.getElementById('saveToFolderBtn').addEventListener('click', saveQuoteToCustomerFolder);`

⚠️ Check whether `.generate-btn` is styled as a single primary action. If two of them side by side looks wrong, use whatever secondary button class the panel already has rather than inventing one.

- [ ] **Step 5: Run the whole suite.** ⚠️ Every existing test must still pass — this task is additive and `Download quote as PDF` was not to change.

- [ ] **Step 6: Prove the collision guard.** Stub `window.confirm` to return `false` and assert `pickTargetName` returns `…-2.pdf` while the original name is never opened with `{create:true}`. Then remove the guard and watch the test fail. Report both outputs.

- [ ] **Step 7: Commit.**

```bash
git add crosscontrol-offertbyggare.html tests/test_customer_folders.py
git commit -m "feat: save a quote into the customer's folder, never over an existing file"
```

---

## Task 3: Device gate, documentation, release

- [ ] **Step 1: The device gate — the owner runs this, not an agent.**

Open the delivered build the normal way, then:
1. Build a quote for a customer, click **Save to customer folder…**, pick a real folder. → the PDF is in that folder.
2. Save the same quote again. → it asks before replacing; Cancel leaves the first file and writes `…-2.pdf`.
3. Close the browser completely, reopen the app, open the same quote, save again. → **report whether Chrome asks for permission a second time.** That is the one answer the spec deliberately left open.
4. Delete the quote from the Archive. → the folder copy stays; only the local copy goes.

- [ ] **Step 2: `HANDOFF.md` §21** — what was measured, the archive-first rule, the per-customer key, the collision rule, and the answer to step 1.3.

- [ ] **Step 3: Bump `APP_VERSION` to `1.7.0`** and `APP_BUILD_DATE`, and update `tests/test_version.py` to match — it asserts the literal on purpose.

- [ ] **Step 4: Merge, tag `v1.7.0`, push, deploy** the versioned file to the three copies, verify by md5, update `START HERE.txt`, remove the superseded versioned file, and do not touch `Current build - for comparison.html`.

⚠️ Ask the owner before merging and deploying. Production is always his call.

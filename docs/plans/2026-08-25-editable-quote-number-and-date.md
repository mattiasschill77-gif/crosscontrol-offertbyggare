# Editable quote number and issue date — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the KAM set the quote's issue date and its number by hand, defaulting to exactly today's behaviour — and stop archived quotes re-dating themselves to whenever they are reopened.

**Architecture:** Two small features in the single-file app, plus the archive record that has to carry the date for the fix to hold. Spec: `docs/specs/2026-08-25-editable-quote-number-and-date.md`.

**Tech stack:** vanilla JS in `crosscontrol-offertbyggare.html`, `generate_pdf.py` for the WeasyPrint surface, and the existing Playwright + PyMuPDF suite in `tests/` (27 tests on `main`).

**Order:** the date first — it is simpler and it fixes a live defect. The number last, because it touches the archive.

⚠️ **Task 3 must not be split.** An intermediate state where the number is editable but the archive guard is not in place can destroy an archived quote.

---

## File structure

| File | Responsibility |
|---|---|
| `crosscontrol-offertbyggare.html` | **Modify.** The two fields, the `issueDate()` source, validity derivation, the archive guard, the counter follow, filename sanitising. |
| `generate_pdf.py` | **Read only.** It already prints `offer.issued_date` and `offer.valid_until` from the export object; if it needs a change, something upstream is wrong. |
| `tests/test_issue_date.py` | **Create.** Task 1 and 2. |
| `tests/test_quote_number.py` | **Create.** Task 3. |
| `HANDOFF.md` | **Modify.** Task 4. |

**Repo rules:** stage by name, never `git add -A` · the HTML has megabyte-long lines, never `grep -c` it (use `grep -o … | wc -l`), never load it wholesale · run the suite from the repo root with `python -m pytest tests/ -v` · the harness refuses to start if something is already listening on port 8142.

---

## Task 1: The issue date drives the document

**Files:** modify `crosscontrol-offertbyggare.html` · create `tests/test_issue_date.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_issue_date.py
import re
from playwright.sync_api import sync_playwright

from harness import app_page, build_long_quote, download_quote_pdf, page_texts, serve


def _open(p, url):
    return app_page(p, url)


def test_issue_date_defaults_to_today():
    with serve() as url, sync_playwright() as p:
        with _open(p, url) as (page, _alerts):
            today = page.evaluate("new Date().toISOString().slice(0,10)")
            assert page.input_value("#issueDate") == today


def test_a_chosen_issue_date_reaches_the_screen_and_the_pdf(tmp_path):
    out = tmp_path / "dated.pdf"
    with serve() as url, sync_playwright() as p:
        with _open(p, url) as (page, alerts):
            build_long_quote(page, 2)
            page.fill("#issueDate", "2026-03-04")
            page.wait_for_timeout(400)
            on_screen = page.inner_text("#docRoot")
            export = page.evaluate("buildExportObj()")
            download_quote_pdf(page, alerts, out)
    in_pdf = " ".join(re.sub(r"\s+", " ", t) for t in page_texts(out))
    assert export["issued_date"] in on_screen, "screen and export disagree on the issue date"
    assert export["issued_date"] in in_pdf, "the PDF did not get the chosen issue date"
    assert "2026" in export["issued_date"]


def test_validity_is_counted_from_the_issue_date_not_from_today():
    with serve() as url, sync_playwright() as p:
        with _open(p, url) as (page, _alerts):
            page.select_option("#termValidity", "30")
            page.fill("#issueDate", "2026-03-04")
            page.wait_for_timeout(400)
            export = page.evaluate("buildExportObj()")
    assert "2026" in export["valid_until"]
    assert export["valid_until"] != export["issued_date"]
    # 2026-03-04 + 30 days = 2026-04-03, whatever the machine clock says today.
    assert "04" in export["valid_until"] and "03" in export["valid_until"]


def test_the_warning_is_internal_only(tmp_path):
    out = tmp_path / "future.pdf"
    with serve() as url, sync_playwright() as p:
        with _open(p, url) as (page, alerts):
            build_long_quote(page, 2)
            page.fill("#issueDate", "2027-12-31")
            page.wait_for_timeout(400)
            note = page.inner_text("#issueDateNote")
            doc = page.inner_text("#docRoot")
            download_quote_pdf(page, alerts, out)
    assert note.strip(), "no internal warning for a future issue date"
    assert note.strip() not in doc, "the warning leaked into the customer document"
    in_pdf = " ".join(page_texts(out))
    assert note.strip() not in in_pdf, "the warning leaked into the PDF"
```

- [ ] **Step 2: Run it and watch it fail**

`python -m pytest tests/test_issue_date.py -v` → FAIL, `#issueDate` does not exist. Report the output.

- [ ] **Step 3: Add the field**

Insert immediately **before** the `term-row` that holds `termValidity`, matching the surrounding markup exactly:

```html
        <div class="term-row">
          <label class="field-tiny-label" style="margin-top:0;" for="issueDate">Issue date</label>
          <input type="date" id="issueDate">
          <div id="issueDateNote" class="price-list-hint" style="margin-top:5px;"></div>
        </div>
```

- [ ] **Step 4: One source for the date**

Add next to the other date helpers:

```js
// The date the document is dated with. The field is authoritative once it exists,
// so the screen and both PDFs cannot disagree; TODAY is only the fallback.
function issueDate() {
  const el = document.getElementById('issueDate');
  if (el && el.value) {
    const d = new Date(el.value + 'T00:00:00');
    if (!isNaN(d.getTime())) return d;
  }
  return TODAY;
}

function todayInputValue() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
```

⚠️ Before wiring it, read `addDays()` and confirm it returns a **new** Date rather than mutating its argument. If it mutates, `TODAY` would drift every render. Say what you found.

- [ ] **Step 5: Wire all four call sites**

There are exactly four, and all must move together or the surfaces diverge:

| Old | New |
|---|---|
| `Issued ${fmtDate(TODAY)}` | `Issued ${fmtDate(issueDate())}` |
| `issued_date: fmtDate(TODAY)` | `issued_date: fmtDate(issueDate())` |
| `validUntil = fmtDate(addDays(TODAY, validityDays))` (×2) | `validUntil = fmtDate(addDays(issueDate(), validityDays))` |

Verify the count first: `grep -o "fmtDate(TODAY)" crosscontrol-offertbyggare.html | wc -l` must be 2, and `grep -o "addDays(TODAY" crosscontrol-offertbyggare.html | wc -l` must be 2. If either differs, stop and report.

- [ ] **Step 6: Default the field and re-render on change**

On init, set `document.getElementById('issueDate').value = todayInputValue();` and add an `input`/`change` listener that calls `renderAll()` and refreshes the note. Follow how `#termValidity` already does it rather than inventing a new pattern.

- [ ] **Step 7: The internal note**

```js
function renderIssueDateNote() {
  const el = document.getElementById('issueDateNote');
  if (!el) return;
  const d = issueDate();
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const days = Math.round((d - today) / 86400000);
  if (days > 0) {
    el.textContent = 'This quote is dated in the future. Intended?';
  } else if (days < -30) {
    el.textContent = `This quote is dated ${Math.abs(days)} days ago. Intended?`;
  } else {
    el.textContent = '';
  }
}
```

⚠️ It is a note, not an error: backdating is legitimate and only the owner can tell a deliberate one from a typo. It must never be rendered into the document — the fourth test guards that.

- [ ] **Step 8: Run the tests, then the whole suite**

`python -m pytest tests/ -v` → all pass, 27 existing + 4 new.

- [ ] **Step 9: Commit**

```bash
git add crosscontrol-offertbyggare.html tests/test_issue_date.py
git commit -m "feat: the issue date is editable and drives validity on every surface"
```

---

## Task 2: The archive remembers the date

Without this, the feature works until you reopen the quote — and the live defect stays: an August quote reopened in November re-dates itself to November.

**Files:** modify `crosscontrol-offertbyggare.html` · modify `tests/test_issue_date.py`

- [ ] **Step 1: Write the failing test**

```python
def test_an_archived_quote_keeps_the_date_it_was_issued():
    with serve() as url, sync_playwright() as p:
        with _open(p, url) as (page, _alerts):
            build_long_quote(page, 2)
            page.fill("#issueDate", "2026-03-04")
            page.wait_for_timeout(600)
            quote_id = page.evaluate("QUOTE_ID")
            saved = page.evaluate("buildQuoteSnapshot()")
            assert saved.get("issue_date") == "2026-03-04", "the archive record has no issue date"
            # Reopen it the way the archive panel does.
            page.evaluate("scheduleAutoSave(); ")
            page.wait_for_timeout(600)
            page.evaluate("(id) => openQuote(id)", quote_id)
            page.wait_for_timeout(400)
            assert page.input_value("#issueDate") == "2026-03-04"


def test_a_record_saved_before_this_release_still_opens():
    with serve() as url, sync_playwright() as p:
        with _open(p, url) as (page, _alerts):
            page.evaluate("""() => {
                const store = loadArchive();
                const rec = buildQuoteSnapshot();
                delete rec.issue_date;
                rec.quote_id = 'CC-2026-9999';
                store['CC-2026-9999'] = rec;
                saveArchiveStore(store);
            }""")
            page.evaluate("openQuote('CC-2026-9999')")
            page.wait_for_timeout(400)
            today = page.evaluate("new Date().toISOString().slice(0,10)")
            assert page.input_value("#issueDate") == today
```

⚠️ Read `loadArchive` / `saveArchiveStore` / `scheduleAutoSave` before using them and correct the calls to the real names and signatures. Do not invent an API.

- [ ] **Step 2: Run it and watch it fail.** Report the output.

- [ ] **Step 3: Store it**

In `buildQuoteSnapshot()`, next to `term_validity_days`:

```js
    issue_date: document.getElementById('issueDate').value,
```

⚠️ **Naming, deliberately different from the export.** The archive stores `issue_date`, the raw `yyyy-mm-dd` input value, because that is what restores a field. `buildExportObj()` keeps `issued_date`, the **formatted** string the document prints. Two names, two jobs — do not unify them.

- [ ] **Step 4: Restore it**

In `openQuote()`, alongside the other field restores:

```js
  document.getElementById('issueDate').value = rec.issue_date || todayInputValue();
```

- [ ] **Step 5: Run the tests and the whole suite. Commit.**

```bash
git add crosscontrol-offertbyggare.html tests/test_issue_date.py
git commit -m "fix: an archived quote keeps the date it was issued instead of re-dating itself"
```

---

## Task 3: The quote number is editable — and cannot destroy an archived quote

⚠️ **Do this as one commit.** Shipping the editable field without the archive guard puts a real quote at risk.

**Files:** modify `crosscontrol-offertbyggare.html` · create `tests/test_quote_number.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_quote_number.py
from playwright.sync_api import sync_playwright

from harness import app_page, build_long_quote, download_quote_pdf, page_texts, serve


def test_the_number_defaults_to_the_generated_one():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            assert page.input_value("#currentQuoteId").startswith("CC-")


def test_a_typed_number_reaches_the_document_and_the_export(tmp_path):
    out = tmp_path / "renamed.pdf"
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            build_long_quote(page, 2)
            page.fill("#currentQuoteId", "2026-03-HUSCO-247")
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(400)
            export = page.evaluate("buildExportObj()")
            doc = page.inner_text("#docRoot")
            download_quote_pdf(page, alerts, out)
    assert export["quote_id"] == "2026-03-HUSCO-247"
    assert "2026-03-HUSCO-247" in doc
    assert "2026-03-HUSCO-247" in " ".join(page_texts(out))


def test_renaming_moves_the_archive_record_instead_of_duplicating_it():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            build_long_quote(page, 2)
            page.wait_for_timeout(600)
            old_id = page.evaluate("QUOTE_ID")
            page.fill("#currentQuoteId", "CC-2026-0500")
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(600)
            store = page.evaluate("loadArchive()")
    assert "CC-2026-0500" in store
    assert old_id not in store, "the old record was left behind as a duplicate"


def test_an_existing_number_is_refused_and_nothing_is_lost():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            build_long_quote(page, 2)
            page.wait_for_timeout(600)
            first_id = page.evaluate("QUOTE_ID")
            first_customer = page.evaluate("loadArchive()[QUOTE_ID].customer_name")
            page.evaluate("newQuote()")
            page.wait_for_timeout(400)
            build_long_quote(page, 2)
            page.fill("#custName", "Someone Else")
            page.wait_for_timeout(600)
            page.fill("#currentQuoteId", first_id)
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(600)
            store = page.evaluate("loadArchive()")
            still_mine = page.evaluate("QUOTE_ID")
    assert store[first_id]["customer_name"] == first_customer, "an archived quote was overwritten"
    assert still_mine != first_id, "the duplicate id was accepted"


def test_a_higher_number_moves_the_counter():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            page.fill("#currentQuoteId", "CC-2026-0500")
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(400)
            page.evaluate("newQuote()")
            page.wait_for_timeout(400)
            assert page.evaluate("QUOTE_ID") == "CC-2026-0501"


def test_a_path_character_cannot_break_the_download(tmp_path):
    out = tmp_path / "slash.pdf"
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            build_long_quote(page, 2)
            page.fill("#currentQuoteId", "CC/2026/0007")
            page.press("#currentQuoteId", "Tab")
            page.wait_for_timeout(400)
            download_quote_pdf(page, alerts, out)
            doc = page.inner_text("#docRoot")
    assert "CC/2026/0007" in doc, "the document should show the id exactly as typed"
    assert out.exists() and out.stat().st_size > 0
```

⚠️ Check the real name of the "new quote" function (`newQuote()` is a guess from `#newQuoteBtn`) and correct the test before running it. Never assert against an API you have not read.

- [ ] **Step 2: Run it and watch it fail.** Report the output.

- [ ] **Step 3: Make the badge an input**

Replace the read-only span, keeping the badge's look — do not restyle the topbar:

```html
<span class="quote-id-badge">Quote <input type="text" id="currentQuoteId" class="quote-id-input" aria-label="Quote number" spellcheck="false"></span>
```

Add a minimal style so it reads as part of the badge rather than a form field: transparent background, no border until hover or focus, width sized to its content, inheriting font and colour. `updateQuoteIdDisplay()` sets `.value` instead of `.textContent`.

- [ ] **Step 4: Commit the edit on blur and Enter**

```js
function commitQuoteIdEdit() {
  const el = document.getElementById('currentQuoteId');
  const typed = el.value.trim();
  const previous = QUOTE_ID;
  if (!typed) { el.value = previous; return; }
  if (typed === previous) return;

  const store = loadArchive();
  if (Object.prototype.hasOwnProperty.call(store, typed)) {
    el.value = previous;
    alert(`Quote ${typed} already exists in the archive. The number was not changed.`);
    return;
  }
  if (Object.prototype.hasOwnProperty.call(store, previous)) {
    store[typed] = { ...store[previous], quote_id: typed };
    delete store[previous];
    saveArchiveStore(store);
  }
  QUOTE_ID = typed;
  localStorage.setItem(LAST_OPEN_KEY, QUOTE_ID);
  bumpCounterTo(typed);
  renderAll();
  renderArchiveList();
}
```

⚠️ Read `loadArchive`, `saveArchiveStore`, `LAST_OPEN_KEY`, `renderAll` and `renderArchiveList` first and correct the names to what the file actually uses.

- [ ] **Step 5: The counter follows an upward edit**

```js
// Zak's point: a number typed once should carry the series, not be retyped every time.
// Only an upward move counts, and only for the current year's counter.
function bumpCounterTo(id) {
  const m = String(id).match(/(\d+)\s*$/);
  if (!m) return;
  const typed = parseInt(m[1], 10);
  const year = new Date().getFullYear();
  let counters = {};
  try { counters = JSON.parse(localStorage.getItem(COUNTER_KEY) || '{}'); } catch (e) { counters = {}; }
  if (typed > (counters[year] || 0)) {
    counters[year] = typed;
    localStorage.setItem(COUNTER_KEY, JSON.stringify(counters));
  }
}
```

- [ ] **Step 6: Sanitise the file names only**

```js
// The document shows the id exactly as typed. Only the download name is cleaned,
// because a path character in a file name fails the download or mangles it.
function safeFileId(id) {
  return String(id).replace(/[\/\\:*?"<>|\x00-\x1f]/g, '-').replace(/\s+/g, ' ').trim() || 'quote';
}
```

Apply it at both download sites: `quote-${safeFileId(offer.quote_id)}.pdf` and `quote-${safeFileId(QUOTE_ID)}.json`. **Do not** apply it to what the document renders.

- [ ] **Step 7: Run the new tests, then the whole suite.**

- [ ] **Step 8: Prove the archive guard actually guards**

Temporarily remove the duplicate check from `commitQuoteIdEdit()`, run `test_an_existing_number_is_refused_and_nothing_is_lost`, and watch it FAIL with the archived quote overwritten. Restore it. Report the real output. A guard that has never failed is not evidence.

- [ ] **Step 9: Commit**

```bash
git add crosscontrol-offertbyggare.html tests/test_quote_number.py
git commit -m "feat: the quote number is editable, and cannot overwrite an archived quote"
```

---

## Task 4: Document and release

**Files:** modify `HANDOFF.md`

- [ ] **Step 1: Add a §20** covering: both fields default to the previous behaviour; the archive stores `issue_date` (raw input) while the export carries `issued_date` (formatted) and why they differ; validity derives from the issue date; the counter follows an upward edit only; an edit renames the archive record and a duplicate is refused; the id is sanitised for file names only; and the defect this fixed — archived quotes used to re-date themselves on reopen.

- [ ] **Step 2: Run the whole suite one last time.** Report the real output.

- [ ] **Step 3: Merge, tag `v1.6.0`, push.**

- [ ] **Step 4: Deploy** the versioned file to Delivery, Demo kit and the Prototypes mirror, **verify by md5**, update `START HERE.txt`, and do not touch `Current build - for comparison.html`.

⚠️ Ask the owner before merging and deploying. Production is always his call.

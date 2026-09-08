# Session handoff — 2026-09-08

**Read `HANDOFF.md` first** for architecture, the brand system and the standing contracts.
This file covers only this session: what shipped, what was decided, what is still open, and
the traps that cost time.

**Build: v1.8.0, 119 tests.** Branch A is merged and pushed (`9c0bf12`). Branch B
(`feat/v1.8-quote-changes`) is complete and unmerged, **pending the device gate in §6**.

---

## 0. Start here if you are picking this up cold

1. **Nothing has been delivered.** The three copies outside git are still v1.7.2. The device
   gate (§6) has not been run, and Branch B is not merged.
2. Four changes: one price list PDF defect and three colleague requests. All four were
   designed against a mockup and **approved before any code was written** —
   https://claude.ai/code/artifact/6f68afde-c37e-4d8c-af83-76a85fa538e5
3. **Four pre-existing defects were found by looking at output, not by tests** — blank
   column headers on every family but the first, **73 of 129 prices broken in half**,
   printed totals that did not multiply out, and a panel that kept the old currency after
   a currency change. All four were in the shipped v1.7.2 build, all four are fixed (§4),
   and **none was caused by the requested work**. Two of them shared one root cause: an
   array passed by reference to every family's table, which pdfmake mutates during layout.

---

## 1. What shipped

| Commit | What |
|---|---|
| `c7053ea` | Spec |
| `2d3859a` | Plan — 13 tasks, 82 steps |
| `451d868` | The stranded-heading guard, red first |
| `2f88efe` | **The price list family heading fix** |
| `72da31e` | Correction: the spec's "no threshold to tune" claim was wrong |
| `6cec132` | HANDOFF §24 |
| `9c0bf12` | **Merge Branch A → `main`, pushed** |
| `191c915` | Customer address on the quote |
| `b06d5b8` | The address in the WeasyPrint quote |
| `e8543b0` | **The price list's TO block** |
| `ed2a470` | **The optional List Price column** |
| `d8709cb` | **The typed unit price** |
| `9354758` | Two toothless probes, fixed |

---

## 2. Decisions taken (owner's calls — do not silently reverse)

All from 2026-09-08, against the mockup:

- **The address is one multi-line free-text box**, not structured street/postcode/city fields.
- **Both documents get it**, and the price list gets the quote's **full TO block** — its
  `Prepared for X · attn: Y` subtitle is replaced. `Prepared by` is a different field and stays.
- **The List Price checkbox defaults to ON.** A colleague who never finds it must see the build
  they had.
- **A typed unit price wins** over the tier price and clears Extra discount.
- **⚠ deviation shows on any difference from the tier price**, above it as well as below.
- **A tier chip click keeps a typed price.** A stray click must never destroy a negotiated
  number.
- **The repeating family band is fine** — a family spanning a page break now reprints its name
  above the column header on the continuation page. Explicitly approved before the change.

---

## 3. The fix that was wrong twice

Worth reading in full before touching `buildPricelistDocDefinition`.

The design said: merge the family band into its product table as `headerRows: 2`, and pdfmake
"cannot break between header rows and the body's first row", so the fix is **structural — no
threshold to tune**.

**That assumption was false.** pdfmake renders both header rows at the foot of a page and starts
the body on the next one. The fix passed its guard and the full suite (92 green) purely by luck
of layout, and only went red when an unrelated fix (§2 below) changed the row heights.

Had the second fix not been made, a broken fix would have shipped with a green suite behind it.

The working fix is three parts — the merge, a fresh header row per family, and a **measured**
`pageBreakBefore` — and `HANDOFF.md` §24 carries the measurements. The spec and plan were
corrected in `72da31e` rather than left claiming what they originally claimed.

---

## 4. Four pre-existing defects, all found by looking at the output

None was caused by this work; all were in the shipped v1.7.2 build. Every one was found
by rendering the document and looking at it, or by the owner reviewing a real quote on
screen — not one of them by a test.

**Fixed — the column header appeared on the first family only.** `cols` was one array of cell
objects pushed **by reference** into every family's table, and pdfmake writes layout state
(`_width`, `_calcWidth`) onto cells as it renders. Every family after the first got a blank row
of the right height and no column names, in a customer-facing document. Fixed with a
`makeCols()` factory. It was fixed here rather than deferred because `headerRows: 2` *repeats*
that row down every long family.

**Fixed on the owner's instruction — prices broke in half.** `€2,438.6` on one line and `0`
on the next. **73 of 129 prices, 57% of the list**, in the shipped v1.7.2 build.

⚠️ The cause was not the column width: `widths` was one array shared by reference across every
family's table, and pdfmake replaces its entries in place with annotated objects during layout.
Every family was sized from CCpilot VI's numbers. Same class of bug as the shared `cols` above.
`HANDOFF.md` §26.

**Fixed — the printed numbers did not multiply out.** A USD quote printed unit $1,042.29,
qty 15, total $15,634.30; 15 x 1,042.29 is $15,634.35. The unit price and the line total were
rounded to cents independently. Pre-existing, reproduced on the v1.7.2 tag, and found by the
owner looking at a real quote rather than by any test. `HANDOFF.md` §27.

Two smaller things from the same review, both fixed: the left panel kept the old currency when
the dropdown changed (the shared listener calls renderDoc() only, while the FX rate box called
renderAll()), and the Unit price box showed the tier price as a placeholder so an untouched
line looked like an overridden one.


---

## 5. Still open

- 🔴 **The device gate has not been run** (§6). Nothing is merged, tagged or delivered.
- 🟠 **No automated guard for the list-price flag in `generate_pdf.py`.** Verified by hand
  (both states exported, rendered PDF text read) but a regression there would not be caught.
  The break-pass script reports it as SKIP rather than omitting it.
- ✅ **`generate_pdf.py` escaping — FIXED** on `fix/weasyprint-escaping` after v1.8.0 was
  tagged. It escaped one value and interpolated 17 raw; all 17 are now escaped at the point
  of read. `HANDOFF.md` §28.
- 🟠 `C000082-26` is still duplicated in the 2024 workbook at €61.00 and €45.00
  (`HANDOFF.md` §12). The app warns; the fix belongs in the workbook.

---

## 6. The device gate — what the owner must run before delivery

Not the dev server. **Double-click the delivered file** and, in that build:

1. Build a quote with an address, a typed unit price and List Price **off**. Export the pdfmake
   PDF. Check the address sits under the company name and no list price appears anywhere.
2. `Export quote data (.json)`, then `python generate_pdf.py <file>.json` — the WeasyPrint PDF
   must match the screen.
3. Build a price list with an address. Export the PDF **and** the Excel. Check the TO block, and
   flick through the page breaks: no family name should be the last thing on a page.
4. Reopen a quote saved before today from the archive: it must still show its List Price column.

Two UI defects in v1.7.0 were found by looking at the screen and by nothing else.

---

## 7. Then, and only then

1. `git checkout main && git merge --no-ff feat/v1.8-quote-changes`
2. `git tag v1.8.0 && git push origin main --tags`
3. Copy `crosscontrol-offertbyggare.html` as **`crosscontrol-offertbyggare-v1.8.0.html`** to
   Delivery, the Demo kit and the Prototypes mirror, and **verify each by md5**.
4. Replace the previous versioned file in each folder — never leave two — and update
   `START HERE.txt` in the demo kit, because the file name it names has changed.

⚠️ `CC QB Prototypes\Current build - for comparison.html` is frozen on purpose as the "before"
half of the comparison. **Never refresh it.**

---

## 8. Traps from this session

- ⚠️ **`CLAUDE.md`'s heredoc warning is not advice.** A scripted edit written as a bash heredoc
  turned `split('\n')` into a real line break and broke the whole app script. **Write the script
  to a file, then run it**, and `node --check` the inline script afterwards.
- ⚠️ **Previously-green tests going red means the app is broken, not that the feature is wrong.**
  That signature is what pointed at a parse error instead of a day of debugging address logic.
- ⚠️ **A green suite proves nothing about a fix whose assumption is false** — §3. Render the PDF
  and look at it.
- ⚠️ **`inner_text()` does not include an `<input>`'s value.** A cost-leak scan that reads row
  text will never see a typed cost, and will report success.
- ⚠️ **A conversion tested at rate 1 is not tested.** Typing a price in EUR makes `/ fxOut()` a
  no-op; the test passed with the division deleted.
- ⚠️ **Autosave is debounced.** A `wait_for_timeout` before reading the archive is a race that
  will lie to you; call `autoSaveNow()`.
- ⚠️ **The app seeds `C000 144-05` into a fresh cart** and `addProductToCart` no-ops for a part
  already there. Key row lookups on `lineId`: `:has-text("CCpilot VI")` also matches
  "CCpilot VI, LinX-Base".
- ⚠️ **A `| tail` in a shell pipeline hides pytest's exit code.** The first baseline run reported
  exit 0 while pytest had errored on an unrecognised flag. Capture `PIPESTATUS`.
- ⚠️ This repo's HTML is **LF**, not CRLF. The CRLF rule belongs to the web repo.

# Session handoff — 2026-09-08

**Read `HANDOFF.md` first** for architecture, the brand system and the standing contracts.
This file covers only this session: what shipped, what was decided, what is still open, and
the traps that cost time.

**Build: v1.8.2, 125 tests.** Three releases went out today from a starting point of
v1.7.2 — **v1.8.0** (the three requests + four pre-existing document defects), **v1.8.1**
(escaping on the WeasyPrint path) and **v1.8.2** (the Unit price row spacing). All merged,
tagged and pushed; all three delivery folders carry v1.8.2.

🔴 **The device gate (§6) has still not been run.** It was skipped on the owner's decision at
each release, not forgotten.

---

## 0. Start here if you are picking this up cold

1. **Everything is delivered and tagged**, and the device gate has still not been run. The
   delivery folders now use one folder per release — `v1.8.2\` is current, with `v1.8.1\`,
   `v1.8.0\` and `v1.7.2\` kept beside it as fallbacks. Each is self-contained: the app plus
   everything `generate_pdf.py` reads by relative path.
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
| `de62927` | Bump to v1.8.0 |
| `64bd397` | HANDOFF §25 and the session handoff |
| `1688a2b` | **The NET PRICE column — 73 of 129 prices were breaking in half** |
| `d226eac` | HANDOFF §26, correcting the claim that caused it |
| `afc61a9` | **Three fixes from the owner's screenshot review** — the arithmetic, the stale panel, the placeholder |
| `f053a98` | HANDOFF §27 |
| `cf8fc57` | **Merge → `main`, tagged `v1.8.0`, pushed** |
| `f38e4f1` | **Escaping: 17 raw fields on the WeasyPrint path** |
| `c995fd2` | HANDOFF §28 |
| `c387cfb` | Bump to v1.8.1 |
| `c96bccf` | **Merge → `main`, tagged `v1.8.1`, pushed** |
| `8c073d9` | **The Unit price row collided with the tier chips** |
| `a1752b5` | **Merge → `main`, tagged `v1.8.2`, pushed** |

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


### 4b. One defect that was NOT pre-existing — I introduced it

**v1.8.2 — the Unit price row collided with the tier chips.** Reported by the owner from a
screenshot of the delivered build.

When the Unit price row was added in v1.8.0 I gave it `margin-bottom` but **no
`margin-top`**, making it the only control in the line card without separation above it.
Measured: the tier chips row ended at y=1270.6 and the Unit price row began at y=1270.6 — a
**zero-pixel gap**, where `.extra-discount-row` and `.mk-row` both use 10px. The input's 3px
focus ring then painted into the chip pills, which is why it read as an overlap rather than
as tight spacing, and why it was most visible with the field focused.

Fixed with `margin-top:10px` to match its siblings. ⚠️ **Deliberately no `border-top`** — the
unit price belongs *with* the tier it overrides, so it is spaced apart from the chips but not
divided from them the way Extra discount and Mfg. cost are.

⚠️ The guard asserts **geometry**: the gap must be at least the focus ring's 3px, at three
panel widths, with the field focused. No text or attribute assertion can see a collision.
Proven able to fail by removing the margin, which reproduces the screenshot exactly.

**Worth drawing the lesson out:** this shipped in v1.8.0 through a suite of 114 tests, a full
visual review of the line card, and a screenshot I looked at myself and described as matching
the mockup. It took the owner opening the real delivered build to see it.

---

## 5. Still open

- 🔴 **The device gate has not been run** (§6). Everything else IS merged, tagged and
  delivered — the gate is the only step of the release sequence still outstanding, and after
  a day in which five defects were found by looking at output and none by the suite, it is
  the step most likely to pay for itself.
- 🟠 **No automated guard for the list-price flag in `generate_pdf.py`.** Verified by hand
  (both states exported, rendered PDF text read) but a regression there would not be caught.
  The break-pass script reports it as SKIP rather than omitting it.
- ✅ **`generate_pdf.py` escaping — FIXED** on `fix/weasyprint-escaping` after v1.8.0 was
  tagged. It escaped one value and interpolated 17 raw; all 17 are now escaped at the point
  of read. `HANDOFF.md` §28.
- 🟠 `C000082-26` is still duplicated in the 2024 workbook at €61.00 and €45.00
  (`HANDOFF.md` §12). The app warns; the fix belongs in the workbook.

---

## 6. The device gate — still outstanding, now against v1.8.2

Delivery went ahead without it on the owner's decision, so this is now a check on a build
that is already in the delivery folders rather than a gate before it gets there.

Not the dev server. **Double-click**
`Desktop\CC Quote Builder (QB)\v1.8.2\crosscontrol-offertbyggare-v1.8.2.html`
and in that build:

1. **A quote in USD or SEK.** Check that the printed unit price times the quantity equals the
   printed total. This is the defect the owner caught by eye in v1.8.0 and it had been wrong
   in every converted-currency quote ever sent — the arithmetic changed in `afc61a9`, so it
   is the single most valuable thing to confirm on real hardware.
2. Build a quote with an address, a typed unit price and List Price **off**. Export the
   pdfmake PDF: the address sits under the company name and no list price appears anywhere.
3. `Export quote data (.json)`, then `python generate_pdf.py <file>.json` from inside the
   v1.8.2 folder — the WeasyPrint PDF must match the screen. A customer name containing `&`
   is worth testing here; that path was escaping only the quote number until v1.8.1.
4. Build a price list with an address. Export the PDF **and** the Excel. Check the TO block,
   then flick through every page: no family name may be the last thing on a page, and every
   price must read whole — 73 of 129 were breaking mid-number before `1688a2b`.
5. Reopen a quote saved before today from the archive: it must still show its List Price
   column, because records written before v1.8.0 carry no such field.

⚠️ **Why this matters more than the test count.** The suite went from 91 to 125 today. **Five**
customer-facing defects were found in the same period — four pre-existing, one mine — and
**every one was found by looking at rendered output or by the owner reviewing a screen. None
by a test.** Two UI defects in v1.7.0 were found the same way. The suite is good at holding
fixes in place and has never once been the thing that found a problem here.

---

## 7. The release, as it actually went

All three releases are merged, tagged, pushed and delivered. `main` is at `a1752b5`,
tagged **v1.8.2**, and every copy outside git carries md5 `e42d2e53…`.

⚠️ **The delivery layout changed today, at the owner's request: one folder per release.**

    Delivery  /  Demo kit
    ├── v1.8.2\   <- current; START HERE.txt points here
    ├── v1.8.1\
    ├── v1.8.0\
    └── v1.7.2\

Each folder holds the app **and** `generate_pdf.py`, `cc-logo.svg` and both Poppins files,
because `generate_pdf.py` reads those by relative path — a version folder without them
renders using whatever sits beside the *parent* copy instead.

⚠️ **`v1.7.2\` deliberately holds v1.7.2's OWN `generate_pdf.py`**, taken from the git tag.
Today's version knows about `customer.address` and `show_list_price`; shipping it beside the
1.7.2 build would be shipping a mismatched pair.

⚠️ The Prototypes mirror keeps its fixed `Live build (mirror).html` name on purpose — it is
the moving half of a pair with `Current build - for comparison.html`, which is **frozen and
must never be refreshed** (verified untouched at md5 `b34b1ecf…` after every copy today).

**For the next release:** bump `APP_VERSION`, tag, then create `v<version>\` with the app and
those four companions, verify by md5, and repoint `START HERE.txt`. Do not delete the previous
folders; they are the fallback.

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

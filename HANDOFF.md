# Handoff — CrossControl Offertbyggare

**Person:** Mattias Schill, Key Account Manager, CrossControl AB (mattias.schill@crosscontrol.com)
**Repo owner (GitHub):** mattiasschill77-gif
**Project:** "Offertbyggare" — a single-file HTML quote-builder tool for CrossControl's CCpilot HMI displays. Runs entirely client-side, normally opened directly from disk (`file://...crosscontrol-offertbyggare.html`) from a OneDrive-synced folder on a Windows PC. No server, no build step for the person using it — the HTML file *is* the app.

Read this whole file before touching code. It replaces having to re-read the full chat transcript.

**Interactive infrastructure map:** https://claude.ai/code/artifact/52091bb2-a6cb-41c1-b0b1-5395368ba548

A clickable companion to this file, built 2026-08-21 and measured from the files rather
than from these notes: the single HTML file in cross-section (click a band, toggle lines
vs bytes), the data flow from workbook to customer document with traceable paths, the four
copies and their md5s, the six `localStorage` keys, the traps, and the open items.
A standalone copy sits beside this file as `INFRASTRUCTURE_MAP.html` — open it in any
browser; it needs no server. Two figures in it correct this document: the launch config
defines one server (`cc-offert`, 8142), not three, and the July 7 build now survives in
three places rather than one.

---

## 1. What this tool does (product overview)

A Key Account Manager tool for building customer price quotes from CrossControl's CCpilot product catalog, and exporting them as branded PDFs. Feature list:

- Product search + cart, with tiered volume pricing (price breaks by quantity)
- Per-line extra discount field with an "off-list deviation" warning flag
- Margin (GM%) calculation per line, with a manual cost (MK) override and a source tag (from price list vs. manually entered)
- Sender-office selector (Alfta HQ / Västerås / Uppsala) — drives the quote header address and a 3-column footer with the active office highlighted
- In-browser Excel upload to replace the embedded price list for a session
- Incoterms 2020 selector with a live plain-English explainer + free-text named-place field
- Currency selector (EUR/USD/SEK) with editable exchange rates, applied live
- Per-line free-text notes
- Custom/unique line items (free text description, optional part ref, manual price) — for things not in the catalog, e.g. bespoke engineering work
- Toggleable signature block ("Acceptance") with editable signer name/title
- Live A4 page-break indicator in the on-screen preview
- **Manufacturing cost is imported** (2026-08-20) — the flexible parser now
  recognises a cost column so margins work the moment the price list carries
  one. Before this, BOTH parsers hardcoded `mk_sek: null`, so importing any
  price list silently wiped the only cost in the file.
  Matched by `PL_MK_RE` on the **start** of the normalised header, not by exact
  synonym, because real cost headers carry qualifiers ("Cost (CMBF ONLY)",
  "MK (SEK)"). `PL_MK_NOT` excludes look-alikes such as "Cost center".
  Currency comes from the header: EUR if it says so, otherwise **SEK**, which
  matches TG-kalkyl. A SEK column lands in `mk_sek`, a EUR column in `mk_eur`,
  and `productMkSek()` converts EUR at the **live** rate — never frozen at
  import (see §15 for why that matters).
  The import status names the column and the coverage, and an import that
  arrives with no cost column **alerts** rather than quietly zeroing margins.
- **Gross margin (TG) on the price list** (2026-08-20) — a "Margin (TG)" card in
  the price list panel, implementing TG_kalkyl_och_valuta.xlsx exactly:
  `TG = (SP-MK)/SP` (B12), `TB = SP-MK` (B13) and `SP* = MK/(1-target)` (B14,
  the unit price needed to reach the target). Shows cost coverage, blended TG,
  total gross profit, and a per-product table sorted worst-margin-first.
  ⚠️ **INTERNAL ONLY.** It is badged "never printed" and lives in the panel.
  Nothing about cost or margin may ever reach `plRenderDoc()`, the PDF or the
  Excel export — verified by scanning the decompressed PDF streams and the
  exported workbook XML, not just the on-screen document.
  MK is entered per product in the picker (`PL.mkByPart`), because the price
  list itself carries MK for only 1 of 86 products; the workbook says the rest
  must come from Monitor.
- **Accessories in the price list** (2026-08-18) — the two accessory sections
  ("Accessories", "Cables" — 43 items) now appear in the price list picker below
  a divider and can be included or excluded per section or per item, so a
  customer who orders accessories gets them on the same document.
  ⚠️ **Accessories are stored in a different shape from products**: they live in
  `PRICE_DATA.accessories[].items` as `{part_number, description, price_eur}`
  with **no `tiers` and no `list_price_eur`**. `plSections(priceData)` is the one
  adapter that normalises both into the product shape — picker, pricing engine,
  preview, PDF and Excel all go through it, so none of them needs to know
  accessories exist. Add accessory handling there, not in five places.
  Because accessories have no volume tiers they always price from `price_eur`,
  whatever basis column is chosen; the panel note counts them separately so a
  volume column does not look broken. "Select all" now covers accessories too
  (86 products → 129 items).
- **Price list basis column** (2026-08-17) — "Calculate from" in the Discount
  card chooses which price column the list is built on: List price (default) or
  any volume tier found in the loaded catalogue. Options are derived from
  `PRICE_DATA` at runtime, so an imported price list with different bands works
  without a code change, and partial columns are flagged in the option text
  ("1k-3k — 70/86 products").
  Three decisions worth preserving, all Mattias's calls on 2026-08-17:
  1. **The discount stacks on top of the chosen column**, with a visible warning
     in the panel whenever it does — tier prices are already ~50% below list
     (CCpilot VI: €526.76 list vs €256.96 at 100-249), so stacking silently
     would give away margin.
  2. **A product with no price in the chosen column falls back to its own list
     price** rather than disappearing, and the panel reports how many did.
  3. **The customer-facing document says nothing about which column was used.**
     All basis feedback is panel-only — do not add it to `plRenderDoc`.
  `line.listEur` still carries the TRUE list price so the "show list price &
  discount" column keeps meaning what it always did; `line.basisEur` is the new
  calculation base and `line.usedFallback` marks the fallbacks.
- **Price list tab** (restored 2026-08-17, see §10) — a second tool alongside the
  quote builder, producing a customer-facing fixed price list: pick products,
  families or everything; default discount with per-family overrides; a
  "show list price & discount" toggle (off = the customer sees net price only);
  optional MOQ and status columns (Active / New / End-of-life / Last-time-buy);
  revision, valid-until, prepared-by, price basis, VAT, lead time and
  confidentiality lines; its own archive. **Exports to both PDF and Excel.**
- **UI polish pass "Tier A"** (2026-08-17, see §11) — app chrome only; the
  customer-facing document is untouched. Left-panel sections are cards on a
  tinted panel, headings carry an orange accent bar over a hairline rule, inputs
  have consistent heights and a real focus ring, buttons have a hierarchy, the
  emoji are inline SVG, and "saved to archive" is a toast rather than an alert.
  ⚠️ **Implemented as an appended override block, not by editing the original
  rules.** It is fenced with a `TIER A` banner comment and sits **before**
  `@media print`, so print still wins. Deleting the block restores the previous
  look exactly. The trade-off: a few properties (`.panel`, `.panel-label`,
  `.archive-item`…) are now declared twice — once in the original rule, once in
  the override. Deliberate; reversibility mattered more than tidiness three days
  before a demo. To consolidate later, fold the overrides into the originals and
  delete the block — do not keep both.
- **Bill-to block** (2026-08-17) — the customer used to be a muted grey sub-line
  reading "To **Name**, attn: … · Issued …". It is now a proper addressee block:
  a small orange "TO" label, the customer name at 16px Poppins bold, contact and
  country beneath, and the issue date on its own line. Changed in all three
  surfaces (screen, pdfmake, `generate_pdf.py`) so the outputs still match.
- **Resizable control panel** (added 2026-08-14) — the left panel was a hard-coded
  420px and felt cramped. It is now a drag handle between panel and preview:
  drag, double-click to reset, arrow keys to nudge (Shift = bigger steps). Width
  is clamped to 340px–min(760px, 55vw) and remembered per machine in
  `localStorage` under `cc_panel_width_v1`. Implemented as a CSS variable on the
  existing grid (`grid-template-columns:var(--panel-w,420px) 6px 1fr`) — no
  layout rewrite, no library. Hidden below 1000px and when printing.
  ⚠️ The move/up listeners are bound on `window`, not on the handle — binding them
  to the handle leaves the drag stuck on when the pointer leaves the 6px strip,
  which is the normal case. This was caught in testing, not in review.
- Full quote archive: every quote auto-saves to `localStorage` under a sequential ID (`CC-2026-0001`, etc.), with a slide-in panel to browse/reopen past quotes, plus JSON export/import of the whole archive as a backup mechanism
- Standard Terms & Conditions reference block shown on every quote (§ box), with an upload control to update which T&C document filename it references
- Three ways to get a PDF out of a quote:
  1. **"Download quote as PDF"** button — generates a real PDF client-side using pdfmake, no server/Python needed. **Working — fixed and click-verified, see §4.**
  2. **"Print via browser"** — just calls `window.print()`, uses the page's own print CSS.
  3. **Export quote as `.json`**, then run `generate_pdf.py <file.json>` locally with Python — produces a pixel-precise PDF via WeasyPrint. **Fully working**; needed as the only route while §4 was broken, now a secondary path for when you want pixel-exact output.

---

## 2. How it all fits together (architecture)

**Everything lives in one HTML file**, `crosscontrol-offertbyggare.html`. During development it's assembled from source pieces via a small Python build step (see §5), but the *delivered* file has everything already inlined — there is no separate build step for the end user.

### Data flow

```
PRICE_DATA (embedded product catalog, JSON, baked into the HTML)
        │
        ▼
   cart[]  ← array of line items, built by addProductToCart() / addCustomLine()
        │
        ├──► renderDoc()          → live HTML preview shown on screen (right-hand pane)
        │
        ├──► buildExportObj()     → the canonical "offer" object — single source of truth
        │         │                 for a quote: customer, terms, currency, all line items,
        │         │                 totals, signature info, T&C filename, etc.
        │         │
        │         ├──► generatePdfInBrowser()  → pdf_export.js → pdfMake.createPdf(...).download(...)
        │         │                               (client-side PDF, no Python needed)
        │         │
        │         └──► "Export quote data (.json)" → downloads buildExportObj() as JSON
        │                                              → feed this file into generate_pdf.py
        │                                                 on the command line for a WeasyPrint PDF
        │
        └──► scheduleAutoSave() → writes into localStorage under key `cc_quote_archive_v1`,
                                    keyed by sequential quote ID
```

So **`buildExportObj()`'s output shape is the contract** between the web app and `generate_pdf.py` — if you change what fields go into a line item or the offer object, both `pdf_export.js` (pdfmake) and `generate_pdf.py` need matching updates, or the PDFs will be missing data or throw.

### File-by-file

| File | Role |
|---|---|
| `crosscontrol-offertbyggare.html` | The whole app. Structure: `<style>` (all CSS), body markup (topbar, left control panel, right live-preview pane, archive slide-in panel), then a big inline `<script>` at the end containing (in order) the Excel parser, the pdfmake PDF builder, and the main app logic. **No external dependencies:** SheetJS (`xlsx`), `pdfmake` 0.3.11 and `vfs_fonts` are all inlined into the file — there are no `<script src>` tags and the app needs no network at all. It used to load those three from cdnjs; see §4 for why that was removed. |
| `generate_pdf.py` | Standalone Python script. Takes an exported quote JSON, renders an HTML string with the same CSS/layout logic as the web app (duplicated, not shared — see §6), and rasterizes it to PDF via WeasyPrint. Needs `cc-logo.svg`, `poppins-700-b64.txt`, `poppins-800-b64.txt` in the same folder (reads them by relative path). |
| `cc-logo.svg` | CrossControl logo, vector, brand-correct colors baked in. Used by both the web app (inlined) and `generate_pdf.py` (read from disk). |
| `poppins-700-b64.txt` / `poppins-800-b64.txt` | Base64-encoded Poppins TTF (Bold / ExtraBold), used to embed the brand's headline font into both the web app's CSS (`@font-face`) and the PDF outputs, so nothing depends on Google Fonts being reachable. |
| `xlsx_parser.js` | Reference copy of the in-browser Excel-parsing logic. Already inlined into the HTML — this standalone file is just kept for reference/editing convenience, not loaded separately. |
| `parse_pricelist.py` | Optional local script to regenerate the embedded `PRICE_DATA` JSON from a master Excel price list, for when you want to bake a new catalog into the HTML at build time rather than have the person upload it every session. |
| `CrossControl_Standard_terms___conditions_2023.docx` | The actual T&C document referenced by every quote. Ships alongside the tool so it can be attached to customer emails. |
| `README.txt` | End-user-facing instructions (English), written as the handoff note to Zak — what to double-click, how to get a PDF, and what the three new features in §9 do. This is the file that ships in the delivery folder. |
| `README.sv.txt` | The earlier Swedish end-user instructions, kept because they document things the English rewrite dropped: `parse_pricelist.py`, `xlsx_parser.js`, how to refresh the price list, and the T&C update flow. |

---

## 3. Brand system (CrossControl graphical profile)

Extracted from CrossControl's official brand guide PDF, applied across all three surfaces (web app, pdfmake PDF, WeasyPrint PDF) this past session:

```
Orange (fills/lines/buttons): #F7971C   (PANTONE 144C)
Orange (text on white):       #c9760f   (darker, for legibility — bright orange is reserved for
                                          graphic elements, never body text)
Grey:                         #646363   (PANTONE Cool Grey 10C)
Blue accent (sparing use):    #5390B5 / text variant #2c5872
Green accent (sparing use):   #9BAD50 / text variant #5c6f2e
```

- **Headlines / uppercase labels:** Poppins, 700/800 weight, uppercase, letter-tracked. This is a stand-in for **Century Gothic**, which is the brand guide's own explicitly-stated fallback for when Decima Pro (their real headline font) isn't available — which it never is on the open web. Century Gothic itself isn't freely distributable, so Poppins was used as a close geometric-sans substitute.
- **Body / data text:** Arial, per the guide's explicit rule ("long texts should be written with Arial").
- **Style:** "Less is more" — the guide's own words. Spacious, minimal color, one big clear visual per idea, avoid clutter. Blue/green are described in the guide as complementary colors "to be used as a complement in small areas" — respected by using them only for a couple of small status indicators (margin-health dot, Incoterms tag), never as a primary color.

If brand work needs to happen again, the source PDF was `CrossControl_Graphical_profile_-_Guidelines__1_.pdf` (uploaded by Mattias) — worth asking him to re-upload it if it's not attached to the new session.

---

## 4. ✅ FIXED — PDF download button ("Download quote as PDF")

**Status: FIXED via Option A on 2026-07-17, verified by real click test on 2026-08-14.**
The rest of this section is kept as the historical record of the bug and, more
importantly, of how to test this properly — the testing discipline in it still applies.

### What was actually done (2026-07-17, ~1h after commit `1aba3ee`)

**Option A was taken: the CDN dependency was removed entirely.** The shipped
`crosscontrol-offertbyggare.html` now has **zero `<script src>` tags** — pdfmake,
`vfs_fonts` (Roboto) and SheetJS are all inlined directly into the file. The
inlined pdfmake is **0.3.11**, i.e. the same version the calling code was written
and tested against, so the version mismatch that caused the bug cannot recur.
File size went 328 KB → 3.1 MB, in line with the estimate below.

This work sat only in the OneDrive delivery folder and was **not committed until
2026-08-14** — which is why this section said "broken" for four weeks after it
was fixed. If you are reading a §4 that claims something is broken, check the
shipped file before believing it.

### Verification (2026-08-14, the §4 recipe, adapted)

Served the shipped file over `http://localhost` (Playwright and the preview tool
both refuse `file://`) and clicked `#downloadPdfBtn` for real, 4 times:

- runtime check: `pdfMake.createPdf(...).download` is an **`AsyncFunction`** → returns
  a Promise → the existing `.then()/.catch()` chain resolves correctly
- 4/4 clicks produced a real download, `quote-CC-2026-0001.pdf`, valid `%PDF-1.3`,
  59,457 bytes, `/Count 2` (two pages)
- 0 alerts, 0 console errors (other than a `favicon.ico` 404, an artifact of
  serving over http rather than `file://`)

**The probe was proven able to fail**, which matters more than the pass: the same
harness was pointed at the pre-fix build in this repo (`1aba3ee`, CDN pdfmake
0.2.10, where `.download` is a plain `Function`) and it reproduced the original
error exactly — `Could not generate the PDF: Cannot read properties of undefined
(reading 'then')`, with no download event.

⚠️ **One trap found while doing this:** "the button label was restored" is **NOT**
a valid pass signal. The `.catch()` block also restores the button, so it reads as
restored in the failing case too. The signals that actually discriminate are
**(a) a download event firing** and **(b) no alert**. Do not build a future test
harness on the button state alone.

---

### Historical record of the bug (kept for context)

**Symptom (confirmed via the person's own screenshot of the real error):**
```
Could not generate the PDF: Cannot read properties of undefined (reading 'then')
```

**Root cause:** `pdf_export.js`'s `generatePdfInBrowser()` does:
```js
pdfMake.createPdf(docDef)
  .download(`quote-${offer.quote_id}.pdf`)
  .then(() => { ... })
  .catch((err) => { ... });
```
This assumes `.download()` returns a Promise. It does **not**, in the exact pdfmake build the app actually loads:
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.10/pdfmake.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.10/vfs_fonts.js"></script>
```
pdfmake **0.2.10** is pinned in the HTML. But all local testing during development was done against pdfmake **0.3.11** (whatever `npm install pdfmake` resolves to today) — a materially different version with a different (Promise-based) `.download()` contract — because the dev sandbox cannot reach `cdnjs.cloudflare.com` to test against the *actual* pinned version. That version mismatch is *why* the bug shipped without being caught, not a one-off fluke.

### How to fix it (pick one)

**Option A — recommended: remove the CDN dependency entirely.** Bundle `pdfmake.min.js`, `vfs_fonts.js`, and `xlsx.full.min.js` directly into the HTML as inline `<script>` blocks (base64 or raw, same pattern already used for the Poppins fonts). Benefits: eliminates the version-mismatch class of bug permanently, and also removes any risk of CrossControl's corporate network blocking `cdnjs.cloudflare.com` (a live hypothesis earlier in the debugging process, before the real error message was captured — network blocking turned out not to be the actual cause this time, but it's still a real risk for a tool that's supposed to work reliably on a corporate laptop). Cost: HTML file grows by roughly 2–3 MB (pdfmake ~1MB, vfs_fonts ~850KB, xlsx ~880KB) — trivial for a local desktop tool.

**Option B — faster: just match versions.** Change the two `pdfmake` CDN URLs in `crosscontrol-offertbyggare.html` from `0.2.10` to `0.3.11` (matching what's already been tested locally). Before shipping, confirm cdnjs actually mirrors `0.3.11` (check via a browser or `web_fetch`, not `bash` — cdnjs isn't in the sandbox's bash network allowlist). After changing the version, **re-verify `registerPdfFonts()` still works** — it already uses feature-detection (tries `pdfMake.addVirtualFileSystem`/`addFonts`, falls back to a plain `.vfs` object) specifically because this API has changed across pdfmake versions before; that defensiveness should carry over, but must be re-tested against whatever version actually ships.

### How to test it properly (learned the hard way — don't skip this)

Do **not** trust:
- Static code review alone.
- An isolated Node `vm`-sandbox test against a pdfmake version that might not match what's pinned in the HTML.
- A Playwright test where the CDN URLs were swapped for local npm files, unless that npm install was explicitly pinned to the *exact* version number in the `<script src>` tag (`npm install pdfmake@0.2.10 --no-save`, not just `npm install pdfmake`).

Do trust: building the file exactly as shipped, substituting version-matched local copies of the CDN libraries only because the sandbox can't reach cdnjs directly, loading it in a real Playwright Chromium, and actually clicking the button:

```python
from playwright.sync_api import sync_playwright
import pathlib

path = pathlib.Path("crosscontrol-offertbyggare.html").resolve()  # with CDN urls swapped for
                                                                     # local, VERSION-MATCHED copies
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.on("dialog", lambda d: (print("ALERT:", d.message), d.accept()))  # catches any alert()
    page.goto(f"file://{path}")
    page.wait_for_timeout(1000)
    page.evaluate("addProductToCart('C000 156-50')")  # any real part number from PRICE_DATA
    page.wait_for_timeout(300)
    with page.expect_download(timeout=15000) as dl_info:
        page.click("#downloadPdfBtn")
    dl_info.value.save_as("test_output.pdf")
    browser.close()
# then: pdftoppm -png -r 100 test_output.pdf preview   (visually inspect preview-1.png)
```

Run this **at least 3–4 times** before declaring it fixed — a self-inflicted test-harness bug earlier in development (passing callback arguments to a method that only returns a Promise, silently never resolving) looked exactly like a real ~25-second hang until re-tested cleanly, and cost real time to untangle.

**Everything else about the PDF pipeline is confirmed solid:**
- `generate_pdf.py` (the Python/WeasyPrint path) is fully tested and working, including correct running header/footer repetition across multiple pages, and correct Poppins font embedding.
- The `registerPdfFonts()` fix (using `addVirtualFileSystem`/`addFonts` instead of assuming a writable `.vfs` object) is real and correct, independent of the version issue above.
- The `.then()/.catch()` error handling added to `generatePdfInBrowser()` is real and correct — it's *because* of this fix that the true error message became visible at all (previously, any failure here was completely silent — "nothing happens," no console output, nothing). Keep this error handling regardless of how the version issue gets resolved.

---

## 5. Rebuilding the HTML from source pieces (if working from source rather than the shipped file)

During development the HTML is assembled from separate source files via a placeholder-substitution Python script, so individual pieces (CSS, JS logic, PDF logic) can be edited in isolation before being reassembled:

```python
with open('shell.html', encoding='utf-8') as f: shell = f.read()
with open('pricelist.json', encoding='utf-8') as f: pj = f.read()
with open('logo_inline.svg', encoding='utf-8') as f: lsvg = f.read()
with open('app.js', encoding='utf-8') as f: aj = f.read()
with open('xlsx_parser.js', encoding='utf-8') as f: xj = f.read()
with open('pdf_export.js', encoding='utf-8') as f: pe = f.read()
with open('cc-logo-b64.txt', encoding='utf-8') as f: logopng = f.read().strip()
with open('poppins-700-b64.txt', encoding='utf-8') as f: p700 = f.read().strip()
with open('poppins-800-b64.txt', encoding='utf-8') as f: p800 = f.read().strip()

shell = shell.replace('<!--LOGO_SVG_PLACEHOLDER-->', lsvg)
shell = shell.replace('<!--PRICELIST_JSON_PLACEHOLDER-->', pj)
shell = shell.replace('<!--LOGO_PNG_PLACEHOLDER-->', logopng)
shell = shell.replace('<!--POPPINS_700_PLACEHOLDER-->', p700)
shell = shell.replace('<!--POPPINS_800_PLACEHOLDER-->', p800)
shell = shell.replace('<!--XLSX_PARSER_PLACEHOLDER-->', xj)
shell = shell.replace('<!--PDF_EXPORT_PLACEHOLDER-->', pe)
shell = shell.replace('<!--APP_JS_PLACEHOLDER-->', aj)

with open('crosscontrol-offertbyggare.html', 'w', encoding='utf-8') as f:
    f.write(shell)
```

**This repo currently contains only the already-assembled `crosscontrol-offertbyggare.html`, not the separate source pieces** (`shell.html`, `app.js`, `pdf_export.js`, `pricelist.json`, `logo_inline.svg`, `cc-logo-b64.txt`) — those existed only in the sandbox from prior sessions and were not carried forward into this repo. If you need to edit CSS/JS in isolation again rather than editing the big combined file directly, you'll need to either:
- split `crosscontrol-offertbyggare.html` back into pieces yourself (the `<style>` block, the inline `<script>` block's three logical sections, are all clearly delimited), or
- just edit the combined HTML file directly (it's what ships anyway) and skip the placeholder-rebuild step entirely.

---

## 6. Known duplication / tech debt worth knowing about

- **CSS/layout logic is duplicated three times**, by necessity: once in the web app's `<style>` block, once in `pdf_export.js`'s pdfmake style objects (a completely different styling API, JS objects not CSS), and once in `generate_pdf.py`'s Python f-string CSS. There is no shared source of truth for visual styling — a brand or layout tweak has to be applied in three places by hand. This was true before this session and remains true after it; not something introduced, but worth knowing before making visual changes.
- **`buildExportObj()`'s shape is an implicit contract** with `generate_pdf.py` (see §2) — no schema/type-checking ties them together, just convention.
- Class names in `app.js`'s HTML-generation strings (e.g. `.product-row`, `.tier-chip`, `.doc-header`) are shared between what CSS targets and what the JS constructs — when doing brand/visual work, this made it possible to reskin the entire app via CSS alone without touching `app.js`'s markup-generation logic at all (confirmed and relied on this past session). Worth preserving that discipline going forward.

---

## 7. What's already in `/mnt/user-data/outputs/` from the last session (in case this sandbox resets again)

- `crosscontrol-quote-builder-rebrand.zip` — the package as it stood at commit `1aba3ee`, i.e. it **still contains the §4 bug**. Superseded; do not ship it. A stale copy also sits in `OneDrive\WEB offert\files\` alongside a `files.zip` from 2026-07-07 — both predate the fix.
- `crosscontrol-offertbyggare.html` — same file standalone.
- A few PNG screenshots from testing (`brand_weasy_page-1.png`, `fixed_page-1.png`, `render_clean_full.png`) — visual proof-of-work from the brand rebuild, not needed for continuing the work.

`/mnt/user-data/uploads/` still has the original brand guide PDF, the T&C docx, the master Excel price list, and a few of the person's screenshots from earlier debugging — useful if any of that context is needed again and isn't re-uploaded.

---

## 8. Quick-reference: what to say to pick this up cleanly in a new session

*"Continue work on the CrossControl Offertbyggare — read HANDOFF.md, then
SESSION_HANDOFF_2026-09-08.md, both in the repo."*

**`SESSION_HANDOFF_2026-09-08.md` is the newest** and the one to read: v1.8.0, what
is still undelivered, and the device gate that has to run before it is. Read
`SESSION_HANDOFF_2026-08-20.md` too if you need the 08-14 → 08-20 stretch, which is
where the price list tab, the TG card and the cost importer came from. This file
(HANDOFF.md) stays the durable architecture reference.

**Current status (2026-09-08): v1.8.0, 114 tests — BUILT, NOT DELIVERED.**
`fix/pricelist-pdf-pagination` is merged (`9c0bf12`); `feat/v1.8-quote-changes` is
complete and **unmerged, pending the device gate**. The three copies outside git are
still v1.7.2. See `SESSION_HANDOFF_2026-09-08.md` §6 for the gate and §7 for the
release steps.

Open: manufacturing cost exists for 1 of 86 products; the 2024 workbook has a
duplicate part number at two prices (§12); the price list's NET PRICE column is too
narrow and wraps four-digit prices (§25.4, owner decision); and `generate_pdf.py`
escapes only the quote number, leaving the other interpolated fields raw.

⚠️ Two earlier versions of this line went stale — one claimed `c5000ac` three
releases later, one claimed v1.7.2 after v1.8.0 was built. A status line in a handoff
goes stale silently. **Update it or delete it.**

**(2026-08-14, historical): there was no known open bug.** The §4 PDF-download
bug is fixed and click-verified, and the three features Zak asked for (§9) are
shipped. The repo and the OneDrive delivery folder are in sync as of this commit.

**Zak reviewed the July 17 package and was happy with the changes** (confirmed by
Mattias 2026-08-14). That loop is closed.

**Next milestone: Mattias presents the builder to colleagues in the week of
2026-08-17.** Which makes §10 worth reading before then.

---

## 9. Zak's three requested features (shipped 2026-07-17)

Delivered in both the web app and `generate_pdf.py`, so the WeasyPrint path stayed
in sync with `buildExportObj()`'s contract (§2):

1. **Renameable quantity column** — a "Quantity column heading" field under Terms
   (`qtyHeading`, with presets MOQ / EAU / Order Qty). Flows through to `qty_heading`
   in the export object and the PDF table header.
2. **Per-product custom volume-tier matrix** (`custom_tiers` / `volume_tiers`) — a
   per-product checkbox turns that line into its own price matrix, one column per
   tier with label + sub-label, pre-filled from the price list and then freely
   editable. **Prices are typed verbatim in the selected currency with no FX
   conversion** (`fmtRaw` in the app, `fmt_raw()` in `generate_pdf.py`), and matrix
   products are deliberately **excluded from the quote total**. Modelled on the
   V1200 quote format.
3. **VAT / Tariff note** (`vat_note`) — a Terms field with EU ("Prices are given
   excluding VAT") and US ("Prices are given without VAT or Tariff") presets,
   rendered as its own line under Terms.

Note this means `generate_pdf.py` now splits lines into `standard_lines` (normal
table, counted in the total) and `matrix_lines` (own matrix block, not counted) —
if you touch either PDF path, keep that split consistent with the web app.

---

## 10. ✅ RESOLVED — the "Price list" tab is back, and now in git

**Found 2026-08-14 while about to delete "stale duplicates" — the feature existed
only in files that were minutes from being deleted. Ported back into the shipped
build on 2026-08-17 at Mattias's request, and it is now committed, so the
OneDrive copies are no longer load-bearing.**

### Restored 2026-08-17

Ported from the 2026-07-07 build into the current one, ~1,115 lines: the tab bar,
the price list panel and preview, the pricelist CSS, the pdfmake + xlsx export,
and the flexible Excel parser. Nothing was removed — Zak's three features (§9),
the §4 PDF fix and the resizer all survive, verified after the port.

Merge notes worth keeping:
- The two views are sibling `.workspace.view` blocks toggled by `switchView()`.
  `.view.active` is **`display:grid`**, not the old build's `display:flex` — the
  resizer lives in a grid column, so flex would break the layout.
- **Each view has its own drag handle**, and `--panel-w` is set on `:root` rather
  than on one workspace, so both tabs stay the same width. Switching tabs must
  never change the layout.
- `onMove` measures the workspace **the active handle is in** — the hidden view
  reports a zero-width rect, which would make the panel jump.
- The importer now calls `parsePriceListFlexible(workbook, { legacyFallback:
  parsePriceListWorkbook })`, so the old "Aktuell prislista" layout still imports.
  `.csv` is accepted and read with `raw:true` for European decimals.
- Zero identifier collisions between the two builds (checked before porting) —
  every price list symbol is `pl`/`PL`-prefixed.

Verified: both tabs render, 86 products across 16 families, price list PDF
(7 pages) and Excel (94 rows, discount correctly applied: 526.76 − 12% = 463.55),
quote PDF still 2 pages with no alerts, drag handle works on both views, no
console errors.

### The original finding, kept for the record

An **earlier build dated 2026-07-07** contains a whole second tab that the shipped
July 17 build does not have, and that **no commit in this repo has ever contained**:

| Marker | 2026-07-07 build | shipped build |
|---|---|---|
| `data-view="pricelist"` | 1 | **0** |
| `tabPricelist` | 1 | **0** |
| `End-of-life` / `Last-time-buy` | 2 / 2 | **0 / 0** |
| `Artikelnr` (Swedish import header) | 2 | **0** |

The three remaining "Price list" strings in the shipped build are just the upload
control and a currency hint — the tab is **gone, not renamed**.

### What the missing feature was

Per its own README (preserved in the same zip): a customer-facing **fixed price
list generator** alongside the quote builder — select individual products, whole
families, or all; a default discount % with per-family overrides; a "show list
price & discount" toggle so the customer can be shown net price only; toggleable
MOQ and product-status columns (Active / New / End-of-life / Last-time-buy);
customer/prepared-by/revision/valid-until fields; its own archive store
(`cc_pricelist…`); **export to both PDF and Excel**.

It also had a **substantially better Excel importer** than the shipped build:
header-*name* matching with Swedish/English synonyms (Artikelnr / Part number /
SKU, Benämning / Description, Listpris / List price…), sheet scoring to pick the
best sheet, multi-sheet merge with US$/duplicate-part removal, specific repair for
the 2024 workbook's V1090/V1290 block whose headers don't match its data, and a
legacy positional parser as automatic fallback.

### Where it survives (⚠️ unversioned, single point of failure)

- `OneDrive\WEB offert\files\crosscontrol-offertbyggare.html`
- the same file nested inside `files.zip` → `crosscontrol-quote-builder-rebrand.zip`

That is **all**. It is in no commit and no other copy. If OneDrive loses those,
the feature is gone.

### What is NOT known

**Whether the drop was deliberate.** Mattias does not remember (asked 2026-08-14).
The July 17 build may have branched from a copy predating the price-list work, or
the tab may have been cut on purpose. Both readings fit the evidence. **Do not
"restore" it without asking him first** — and equally, do not delete the July 7
copies on the assumption it was intentional.

Note the July 7 build was **already fully inlined** (no CDN, no `<script src>`),
which means the CDN regression in `1aba3ee` was itself a step backwards from it.
So July 17 is not a strict successor of July 7 in any dimension except Zak's three
features and the brand rebuild.

---

## 11. Labelling / accessibility contract (2026-08-17)

Every form control in both tabs and the archive drawer has an accessible name.
It was 5 of 30 before this pass. **Three treatments, chosen per field — do not
"simplify" this into one:**

1. **`for=`** on labels that were already visible but never linked. The Price
   list tab alone had 9 of these.
2. **A new visible label** where the field had none and the section heading did
   not disambiguate it — Payment terms, Named place and Quote validity were
   three bare dropdowns stacked under "Terms". That one is a real on-screen
   improvement, not just an accessibility fix.
3. **`aria-label`** only where visible text already sits beside the control: the
   sender office and currency selects, the FX rates (which read
   "1 EUR = [ ] USD"), the search boxes, and every per-line generated control.
   A second visible label there would only add clutter.

⚠️ **Per-line controls carry the product name** —
`aria-label="Quantity for ${escapeAttr(item.description)}"` — so a screen reader
can tell one row's Qty box from another's. Preserve that when editing templates.

⚠️ **The extra-discount input exists in TWO templates** (standard line and
custom line). Patching one silently misses the other. This was caught only
because the audit was re-run with a custom line on screen.

⚠️ **Auditing needs the UI in a non-default state.** Controls that only exist
after you add a line or enable custom volume tiers are invisible to a scan of
the freshly-loaded page, so a naive audit reports "all labelled" and is wrong.
Add a custom line and switch on volume tiers first: the control count goes from
30 to 62.

---

## 12. ⚠️ Known data defect in the 2024 price list: duplicate part number

`C000082-26` appears **twice in the Cables section** of
*CrossControl Standard product price list 2024*, as two different products at
two different prices:

| Source row | Description | Price |
|---|---|---|
| "Price list - Euro" row 159 | Straight M12 to RJ45 male, 2m | €61.00 |
| "Price list - Euro" row 180 | Ethernet cable adapter V700. DIN M12 to RJ45 male. | €45.00 |

**This is in the source workbook, not a parser bug** — verified by reading the
xlsx directly. It surfaced on 2026-08-18 when accessories became selectable,
because the row can now reach a customer-facing document.

Consequences:
- A price list including Cables shows the same part number twice at two prices.
- Selection is keyed by part number, so the two **cannot be selected apart**.

**The app deliberately does not dedupe.** Silently dropping one would mean
picking a price at random and hiding a real commercial problem. Instead
`plRenderBasisNote()` raises a panel warning naming the part and both prices
whenever a duplicate is among the selected items — which also catches any future
duplicate introduced by an imported price list.

**The fix belongs in the workbook**, not in the code.

---

## 13. Archive: the row is clickable (fixed 2026-08-18)

**Reported as "opening a file from the Archive fails and doesn't open".**

Root cause: `#archiveList`'s click handler only matched `.archive-open-btn`, so
clicking anywhere else on a quote row did nothing. That gap was harmless while
the row was visually inert — but the Tier A pass added
`.archive-item:hover{border-color:var(--cc-orange)}`, which makes the row light
up and advertise itself as clickable. The polish turned a dormant gap into an
active trap: the row looks clickable, so people click it, and nothing happens.

Fix: the handler now falls through to `e.target.closest('.archive-item')` and
opens that quote, while ignoring clicks that land on a real control
(`button, input, select, textarea, a, label`). `.archive-item` also gets
`cursor:pointer` so the affordance matches the behaviour.

⚠️ **Lesson worth keeping:** adding hover feedback to something makes a promise.
If you give an element a hover state, wire its click — or don't give it one.

## 14. ✅ FIXED 2026-08-31 (v1.7.2) — the price list archive was write-only

**Fixed in §23.** The section below is the historical record of the defect.

`plSaveToArchive()` writes to `localStorage` under `cc_pricelist_archive_v1`,
mints an id (`PL-2026-0001`) and confirms with a toast. **Nothing ever reads it
back.** All three references to `PL_ARCHIVE_KEY` are inside that one function
(a read-modify-write of its own store), and there is no list, no loader and no
UI anywhere for saved price lists — grep for any price list archive UI returns
zero matches.

So "Save to archive" on the Price list tab looks like it works and the data is
unreachable forever. The Archive drawer in the top bar is the QUOTE archive only.

Fixing it needs a price list archive UI (list + open + delete), mirroring
`renderArchiveList` / `openQuote`. Note the saved record also does **not**
include `basisColumn`, so that field has to be added to the record before a
loader would restore the price list correctly.

---

## 15. The SEK/EUR rate used for margin (fixed 2026-08-20)

**There were three different SEK/EUR rates in play**, and margin used the wrong one:

| Source | Rate |
|---|---|
| `TG_kalkyl_och_valuta.xlsx` C9 | 11.07 SEK/EUR |
| `PRICE_DATA.meta.tg_assumptions.fx_sek_eur` (0.0949) | **10.54** — what `computeTG` used |
| The Currency card the KAM edits (`fxRateSEK`) | 11.40 |

`computeTG` multiplied MK by the meta value, which is **frozen into the price
list at import and cannot be edited**. So quote margins silently drifted from
every other price in the app as the real rate moved: the same product read
66.2% on the Quote tab and 68.7% in the price list.

Fixed by introducing **one shared `sekPerEur()`** used by both tabs, reading the
Currency card. `meta.tg_assumptions.fx_sek_eur` survives only as a last-resort
fallback if that field is unusable. `setCurrencyRate()` already calls
`renderAll()`, so editing the rate updates margins live.

Verified: both tabs return bit-identical TG at 9.50, 11.40 and 12.00 SEK/EUR,
all three matching a from-first-principles calculation, and the value moves with
the rate (68.73% → 62.47% → 70.29%).

⚠️ **Do not reintroduce `meta.tg_assumptions.fx_sek_eur` as the working rate.**
It is a snapshot of the import, not a live rate.

## 16. Label audits must expand the price list families

The 2026-08-17 claim of "77 of 77 controls labelled" was **measured with the
price list families collapsed**, so it never saw the controls inside them. With
every family expanded the picker renders ~576 controls, and the family-discount,
MOQ, status and both selection checkboxes were all unlabelled the whole time.

Now genuinely complete: **611 of 611** across both tabs and the archive drawer,
audited with every family expanded, everything selected, and a custom line added.

⚠️ Same trap as §11: a control that has not been rendered yet audits as absent,
and the audit then reports success. Expand everything first.

---

## 17. Adding a cost column to the price list — what the importer accepts

Written up for Mattias to take into a meeting requesting the column:
`Desktop\CC Quote Builder (QB)\Price list - manufacturing cost column (spec for the meeting).txt`

Recognised headers (start-of-header match, case and punctuation insensitive):
`Tillverkningskostnad`, `Tillverkningskostnad (MK)`, `MK`, `MK (SEK)`,
`MK (EUR)`, `Manufacturing cost`, `Mfg. cost`, `Production cost`,
`Standardkostnad`, `Självkostnad`, `Kostpris`, `Unit cost`, `Cost price`, `Cost`.

Deliberately NOT matched: `Cost center` / `Cost centre` / `Cost code` /
`Cost type` / `Cost group`, and `MK nr` / `MK no` / `MK id`. Also note
`Margin` / `Marginal` already belong to `negotiation_margin` — do not add cost
synonyms that collide with them.

Verified against ten header spellings plus two decoys by building workbooks
in-browser with SheetJS and running the real `parsePriceListFlexible` over them,
then end-to-end through the actual file input with a semicolon CSV using
European decimals (`2043,50` → 2043.5).

⚠️ The **legacy** positional parser still hardcodes `mk_sek: null`. It only runs
when no header row is recognisable, so the flexible path covers the real file —
but a cost column added to a headerless sheet would not be read.

---

## 18. Version scheme, the pagination contract, and the test suite (2026-08-25)

### 18.1 Version

`APP_VERSION` and `APP_BUILD_DATE` near the top of the app script are the **single
source of truth**. The version literal appears exactly once in the file; the topbar
label, the export JSON and both archive records all read the constant.

At release time three things must be made to agree **by hand** — nothing enforces it:

| | |
|---|---|
| the constant | `APP_VERSION` in the app script |
| the git tag | `v1.5.0` on the merge commit |
| the delivered file names | `crosscontrol-offertbyggare-v1.5.0.html` in Delivery, Demo kit and the Prototypes mirror |

⚠️ **The file in the repo deliberately keeps its unversioned name.** Renaming a
3.2 MB file every release makes the history unreadable. Only the copies outside git
carry the version. Keep exactly one versioned file per delivery folder — replace the
previous one, never leave two — and update `START HERE.txt` in the demo kit, because
the file name it names changes every release.

The version is stamped into `buildExportObj()`, `buildQuoteSnapshot()` and
`plSaveToArchive()`, and is **never rendered in the customer document**. A test guards
that, and it reads the live `APP_VERSION` from the page rather than a hardcoded string,
so it keeps guarding the invariant after the next bump.

### 18.2 The pagination contract

**The rule: a text block moves whole to the next page — but only a block whose height
is bounded by fixed content.** Anything fed by a free-text field stays breakable.

Protected in the pdfmake builder with `unbreakable: true`: the T&C block (which carries
the forecast-condition sentence, all fixed prose plus a file name), the totals block
(three fixed rows), and the signature block (which already was). In the print CSS and in
`generate_pdf.py`: `break-inside: avoid` on `.tc-reference`, `.terms-grid`, `.totals`,
`.appendix-note`, plus `break-after: avoid` on `.section-eyebrow`.

⚠️ **The TERMS grid is deliberately NOT unbreakable, and was reverted once.** It is fed
by `#vatNote` and `#termIncotermLocation`, two free-text inputs with no `maxlength`.
Measured 2026-08-25: at **~2,100 pasted characters** an unbreakable terms block exceeds
one page body, and pdfmake deletes it — heading, payment terms, validity, delivery terms
and currency all gone from the PDF, **while the on-screen preview still shows them**. A
quote reaches the customer priced but with no payment terms and no validity period. That
threshold is *lower* than the product-note one below. A split terms block is ugly; a
missing one is not survivable.
`tests/test_pagination.py::test_long_vat_note_does_not_delete_the_terms_block` guards it
and was proven to fail with `unbreakable` re-applied.

⚠️ **"A table breaks between rows" is only true on one surface.** `table.quote-table tr
{ break-inside: avoid }` exists in the print CSS only. pdfmake and WeasyPrint both
fragment *inside* a row. That is lossless — no content disappears — but a row can be cut
across the page edge.

⚠️ **The price list PDF was left out of this work on purpose.** `buildPricelistDocDefinition`
has no `unbreakable` anywhere. Giving its blocks the same treatment needs the same
per-block height measurement first, and the TERMS defect above is exactly what happens
when that step is skipped. `.appendix-note` is likewise protected in the print CSS and in
`generate_pdf.py` but not in the pdfmake builder — a known, recorded divergence.

⚠️ **Never mark a block unbreakable if it can be taller than one page body.** pdfmake
does not move such a block and does not clip it — `commitUnbreakableBlock` keeps only
`context.pages[0]` and **discards the rest**.

⚠️ **`dontBreakRows: true` on the product table is FORBIDDEN, and was reverted once.**
It is row-level `unbreakable`, so it inherits exactly that behaviour. Measured
2026-08-25: with a per-line note of 3,115 characters the row survives; at 3,279 the
**entire product row is deleted** from the PDF — description, part number, unit price,
quantity, line total — with no alert and no visual cue, **while the totals block still
counts it**. In the reproduction the visible lines summed to €28,959.05 and the document
printed €32,813.45. `tests/test_pagination.py::test_long_note_does_not_delete_its_product_line`
exists solely to catch a reintroduction; it was proven to fail with the flag re-applied.

**The underlying exposure — unbounded input — was closed on 2026-08-25** at the owner's
decision. The four free-text fields that reach the customer document now carry a
`maxlength` and a small character counter: the per-line note 1000 (in **both** the
standard-line and custom-line templates), the custom-line description 400, `#vatNote`
400, `#termIncotermLocation` 120. Every limit sits well under the measured overflow
thresholds, so no bounded field can push a block past a page body.

⚠️ **Playwright's `fill()` respects `maxlength`** in this Chromium build — it truncates
exactly like typing. A test that needs more text into a bounded field than a user could
type must go through `harness.set_value_bypassing_maxlength()`, which assigns `el.value`
and dispatches an `input` event. Both deletion guards use it, and both were re-proven to
fail with their defects reintroduced *after* the change.

⚠️ **`orphans` and `widows` are a dead end.** Their CSS initial value is already `2`
in both Chrome and WeasyPrint — measured: a bare `<div>` with no rules computes
`orphans: 2, widows: 2`, identical to `.doc-body`. Declaring `2` does nothing. Only a
value of 3 or more would mean anything, and that shifts existing layout.

**WeasyPrint, measured 2026-08-25:** a plain block **does** fragment across a page
break, and `break-inside: avoid` moves it whole instead. A `display: flex` container
**never** fragments, with or without the rule. `.tc-reference`, `.terms-grid` and
`.totals` are all flex, so for those three the rule is insurance for the day someone
changes `display` — only `.appendix-note` is load-bearing today.

### 18.3 Browser print still has a page-1-only header — known and accepted

`Print via browser` repeats the footer (`position: fixed`) but **not** the header. The
`@page { margin: 0 }` that would normally be relaxed to reserve space for a running
header is load-bearing: it is what removes Chrome's own URL, date and page-number lines
from a customer document.

The `<thead>` wrapper approach was implemented and abandoned on 2026-08-25. Three
findings worth keeping:

1. Playwright's `page.pdf()` **does** fire `beforeprint` and `afterprint` in Chromium 145,
   contrary to what is often written. A test that dispatches them manually gets four
   events, not two.
2. Mutating the header's inline `style` in those handlers races Chromium's own print
   teardown — the restored element intermittently keeps a stray `style=""`. Toggling a
   class instead is reliable.
3. The real blocker: for a 16-product quote this document already produces a **trailing
   page containing nothing but the footer**, both before and after the change. A repeated
   `<thead>` can only appear on a page that receives at least one table row, so a
   footer-only page can never carry the header by that technique. Fixing it means tuning
   the spacing around `.doc-body` / `.doc-footer`, which risks the two paths that already
   work.

**Open decision for the owner:** keep the button with this limitation, or remove it —
the pdfmake button produces a correct PDF and is the path in daily use.

### 18.4 The test suite

`tests/` — the first automated tests this repo has had. Run from the repo root:

```
python -m pytest tests/ -v
```

27 tests: `test_smoke.py` (the harness works end to end), `test_version.py` (4),
`test_pagination.py` (6, the pdfmake surface), `test_weasyprint.py` (2, skipped when
Pango is unreachable), `test_input_limits.py` (14, the field bounds and counters).
They drive the real UI in Chromium over `http://localhost:8142`
— `file://` is refused by Playwright — click the real export button, and read the real
PDF page by page with PyMuPDF.

⚠️ **The harness refuses to run if something is already listening on 8142.** On Windows
`SO_REUSEADDR` lets a bind succeed against a port already in use: the existing server
keeps answering, the suite tests *that* build, and it all reports green. Since
`CLAUDE.md` and `.claude/launch.json` both put a dev server on 8142, a leftover one is
the normal case. `serve()` probes the port first and raises rather than lying.

⚠️ **Every guard in this suite was proven able to fail before it was trusted**, by
breaking the thing it protects and watching it go red. Keep that discipline: a green
test that has never failed is not evidence. Two traps that produced false results while
writing them: PDF text extraction turns a line wrap into a double space, so page text
must be normalised with `re.sub(r"\s+", " ", t)` before asserting; and a note made of
one repeated character never reproduces an over-tall row, because pdfmake treats it as
a single unbreakable word — realistic wrapped prose is required.

⚠️ The app **seeds three demo cart lines** on a fresh browser profile (2 products and a
custom line, when `localStorage` holds no archive), and `addProductToCart` no-ops for a
part number already in the cart. Every cart-length assertion in the suite accounts for
this. `FLAT_PRODUCTS.length` is **129** — 86 products plus 43 accessories.

**WeasyPrint on this machine** (installed 2026-08-25): `pip install weasyprint` (69.0)
plus the MSYS2 Pango stack (`winget install MSYS2.MSYS2`, then
`pacman -S mingw-w64-x86_64-pango mingw-w64-x86_64-fontconfig`). WeasyPrint finds the
libraries through the user environment variable
`WEASYPRINT_DLL_DIRECTORIES=C:\msys64\mingw64\bin`. A shell opened before that variable
existed will not see it; pass it inline. ⚠️ `pytest.importorskip("weasyprint")` is **not**
enough to skip on a machine without Pango — the failure is an `OSError`, not an
`ImportError`, so collection crashes. The module catches `Exception` and skips.

---

## 19. Save location — the browser capability is measured, not assumed (2026-08-25)

The planned "save into a customer folder" feature depends on the File System Access
API, and the assumption going in was that it would be **blocked** on `file://`. That
assumption was wrong. Measured in the owner's own Chrome, with the app opened the normal
way by double-clicking the delivered file:

```
{"url":"file:","save":true,"dir":true,"idb":true,"secure":true}
CC PROBE: {"idb":"ok","picker":"OPENED and cancelled = PASS"}
```

⚠️ The first line only proves the APIs **exist**. `!!window.indexedDB` is true even on
origins where `open()` throws, and `showSaveFilePicker` can sit on `window` and still
refuse when called. The second line is the one that counts: `indexedDB.open()` really
succeeded, and `showSaveFilePicker()` really put a dialog on screen — proven by the
`AbortError` that comes back when the user cancels it. **Presence is not function; call
the API before believing in it.**

What this settles for the design:

- The quote can be written **straight into a chosen customer folder** from `file://`.
  No download-folder detour, no "copy this path" choreography.
- A directory handle can be stored in IndexedDB, so the folder can be remembered **per
  customer between sessions** rather than only for the current one.
- Still unmeasured, and deliberately so because it does not change the architecture:
  whether Chrome keeps the folder **permission** across a restart. The handle is stored
  either way and `requestPermission()` is called when needed; the only difference is
  whether the owner clicks "allow" once per customer folder or once per session.

⚠️ Unchanged regardless: the copy in the `localStorage` archive is written **first and
unconditionally**, before any file leaves the app. The customer folder is an addition,
never a replacement, and the archive checkbox is rendered checked and disabled.

---

## 20. The editable quote number and issue date (v1.6.0, 2026-08-26)

Zak asked for both. His own suggestion was the design that got built: *default to
what you have now, but allow the box to be editable, just like the VAT box.* A free
text field also gives his `year-month-customer-#` idea without a format system.

### 20.1 The issue date

`issueDate()` is the single reader — the screen heading, the screen validity,
`issued_date` and `valid_until` all go through it, so the three surfaces cannot
disagree. `TODAY` survives only as its fallback. **Validity is counted from the issue
date**, not the machine clock, so moving the date moves the valid-until with it.

A future date, or one more than 30 days back, raises a note in the panel. It is a
**note, not an error**: backdating is legitimate and only the owner can tell a
deliberate one from a typo. It is tested to reach neither the screen document nor
either PDF.

**This fixed a live defect.** The archive stored `term_validity_days` but no date, and
`openQuote()` restored none, so a quote issued in August and reopened in November
**re-dated itself to November** with a fresh validity window — the document disagreed
with the quote that was actually sent. The record now carries `issue_date`.

⚠️ **Two names on purpose.** The archive stores `issue_date`, the raw `yyyy-mm-dd`
input value, because that is what restores a field. `buildExportObj()` carries
`issued_date`, the **formatted** string the document prints. Do not unify them.

### 20.2 The quote number

The topbar badge is an input, defaulting to the generated `CC-YYYY-NNNN`. The archive
is keyed on the number, so the edit is careful: a number already in the archive is
**refused** and the field reverts; otherwise the existing record is **moved** to the new
key, never copied. A higher trailing number moves the year counter so the series is set
once rather than retyped.

⚠️ **`bumpCounterTo()` must stay bounded.** `parseInt` on 23 trailing digits reaches
`1e+23`, where `n + 1 === n`: `nextQuoteId()` would then return the same id forever and
every new quote would overwrite the previous one in the archive — permanently, with no
UI to reset the counter. ~320 digits reach `Infinity`, which `JSON.stringify` writes as
`null`, restarting the series at `0001` on top of real quotes. It refuses anything that
is not a positive safe integer, and the field carries a `maxlength`.

⚠️ **`nextQuoteId()` skips numbers the archive already holds.** Importing a colleague's
archive does not move the counter, so without this the series walks into an imported
quote and autosave overwrites it. Only safe because the counter is bounded — otherwise
the skip loop would never terminate.

⚠️ **The number is user text now, so it must be escaped.** It is interpolated into HTML
in `renderDoc()` (twice) and in `generate_pdf.py`. Unescaped, `2026-08-<b>HUSCO</b>-14`
rendered as `2026-08-HUSCO-14` on screen while the pdfmake PDF printed the tags
literally — the screen is what gets checked before sending. An archived `quote_id` of
`<img src=x onerror=…>` also executed on open, and archives move between colleagues.

⚠️ **`generate_pdf.py` imports `from html import escape as html_escape`**, not
`import html`. `build_html()` has a local variable named `html` that shadows the module
for the whole function; `import html` raises `UnboundLocalError` and breaks the
WeasyPrint path outright.

**No file-name sanitiser, measured rather than assumed.** With the number set to
`CC/2026/0007`, Chrome already produces `quote-CC_2026_0007.pdf` and the export
completes with no alert; a review confirmed `/ \ : * ? < > |` and `../../` all collapse,
on both download paths. The document keeps the number exactly as typed, and a test
asserts on `suggested_filename` so the claim stays checked.

### 20.3 Archive export and import

The exported file used to be the bare store object with no marker at all. It now carries
`format`, `format_version`, `exported_at` and `app_version`, with the records under
`quotes`. `readArchiveFile()` still accepts the **old bare-store shape** — those files
are on disks and in email threads — and a file from a **newer** `format_version` is
still read for its quotes rather than refused.

⚠️ **An import never overwrites.** It used to be `{...existing, ...incoming}`, so
imported records won every collision. Every machine starts its series at `CC-YYYY-0001`,
so two colleagues almost certainly hold **different** quotes under the **same** number,
and one OK click destroyed a real one. Now: an identical record is skipped (so
re-importing your own backup is a no-op), a differing one is kept alongside under
`<id>-imported`, and the dialog names what will happen before you commit to it.
Identity is compared on **sorted keys**, because two versions need not write a record's
keys in the same order.

### 20.4 Tests

53 in `tests/`. The guards that matter were each proven to fail with their protection
removed: the duplicate-number refusal, the collision-safe merge, and the counter bound.
⚠️ One test was found to be **toothless** while writing this: the file-name test could
never fail, because Playwright saves a download to a path the test itself chooses, so
the suggested name was never exercised. It was only noticed because eight tests passed
against code that had never been written to disk. Assert on what the browser actually
produced, not on what you handed it.

---

## 21. Saving into a customer folder, and deleting from the archive (v1.7.0, 2026-08-26)

### 21.1 What the owner asked for

> *"användaren så få välja var offerterna sparas utöver det som finns idag … Men ska
> alltid finnas en lokal backup att falla tillbaka på (om man inte avsiktligt tar bort
> den i arkivet)"*

Both halves are now true. They were not before: the deliberate removal did not exist.

### 21.2 The save

`Save to customer folder…` sits under the download button as a secondary action.
`Download quote as PDF` is untouched — this was additive, and every pre-existing test
still passes.

The order is the contract: **`autoSaveNow()` writes the archive copy first**, before the
picker is even opened, so a cancelled or failed save still leaves the quote in the
archive. A test asserts it by making the picker throw.

The folder is remembered **per customer**, keyed on the trimmed customer name, in
IndexedDB (`cc_customer_folders_v1`) — a directory handle is structured-cloneable, so
`localStorage` cannot hold one. An empty customer name is never used as a key, or every
nameless quote would share one folder under `""`.

⚠️ **Never overwrites.** If `quote-<id>.pdf` is already in the folder: OK replaces it,
Cancel keeps both and this one becomes `-2`, then `-3`. Revision A must not vanish
because revision B was saved.

**Degrades in four directions rather than failing:** no API at all → ordinary download
with an explanation · API present but blocked by policy → the same, caught at the call
rather than guessed from feature detection · picker cancelled (`AbortError`) → silence,
because that is not an error · IndexedDB blocked → ask for the folder every time.

### 21.3 Measured on the owner's machine, 2026-08-26

The device gate, run by the owner on the real build opened by double-click:

| | |
|---|---|
| Writing into a real folder from `file://` | ✅ the PDF landed in `OneDrive\…\Android` |
| Collision | ✅ asked first; Cancel kept both — `quote-CC-2026-1002.pdf` and `-2.pdf` |
| **After closing Chrome completely** | ✅ **the folder was still remembered** — it never asked which folder |
| Permission after that restart | ⚠️ **Chrome asks again**, offering *Tillåt den här gången* / **Tillåt vid varje besök** / *Tillåt inte* |
| Deleting the quote from the archive | ✅ both PDFs stayed in the customer folder |

So the handle survives a restart but the **grant** does not, unless the owner picks
*allow on every visit*. That is a per-user choice, and `ensureFolderPermission()` handles
both by calling `requestPermission()` when `queryPermission()` is not already `granted`.

⚠️ Two UI defects were found by that device test and by nothing else: the new button was
inserted between the download button and *its* hint, so the hint read as a description of
the wrong control; and it used the `+ Add custom item` class, which is dashed precisely to
say "add something". Both fixed. **Look at the screen — a green suite says nothing about
whether a control sits where its label belongs.**

### 21.4 Deleting from the archive

Every archive row now has `Delete` beside `Open`. It confirms first, naming the quote and
its customer, and says that only the local copy goes.

⚠️ **The trap that made this a real task rather than three lines:** autosave writes
`store[QUOTE_ID]` on every change, so deleting the quote that is **currently open**
resurrects it on the next keystroke. Deleting the open quote therefore moves the app onto
a fresh one and reopens the archive, so several can be cleared in a row. Proven by
removing that branch and watching the quote come back as soon as anything was typed.

The delete branch sits **before** the open branch in the row's click handler, so Delete
does not fall through to the row's own open-on-click (see §13 for why that row is
clickable at all).

### 21.5 Tests

72. The guards were each proven to fail with their protection removed: the collision
keep-both, the archive-first ordering, and the resurrection guard.

⚠️ **What the suite cannot cover:** Playwright cannot drive a native folder picker. The
store, the ordering, the collision logic and every fallback are automated; the picker
itself is a device gate the owner runs. Do not let a green suite imply that path was
tested.

---

## 22. The app on a phone (v1.7.1, 2026-08-26)

Scope, set by the owner: **readable on a phone, not usable with a thumb.** Opening a
quote and showing it to someone works. Building a whole quote with a thumb was
explicitly not asked for and is not there.

**What was actually wrong.** Measured at 390x844 before any change, the page was 798px
wide. Everything below the top bar already fitted — the `max-width:1000px` rule collapses
the grid correctly — and the whole overflow came from the top bar, one flex row that
refused to wrap. It wraps now, and `#productCountPill` is dropped as the first thing not
worth its width.

⚠️ **The trap: fixing that revealed the real problem, and the test stayed green through
it.** `.doc` is `width:780px; max-width:100%`, so on a phone it was squeezed to ~316px
and the five-column price table collapsed until the header cells collided and the totals
ran into the page edge. **Nothing overflowed in DOM terms** — columns crush rather than
overflow — so the overflow assertion passed while a screenshot showed a broken document.
The document now keeps its real 780px and the whole thing is scaled down in bands, the
way a PDF looks on a phone. `tests/test_mobile_layout.py` asserts the document is **not
squeezed**, which is the invariant a geometric test can actually check.

⚠️ **A media query adds no specificity.** The narrow-screen block sits earlier in the
stylesheet than the rules it overrides, so plain selectors lost on source order and the
rules silently did nothing. They are written as `#docRoot, #plDocRoot, .workspace
.doc-wrap` for that reason. This cost two rounds; check the computed value, not the
source.

⚠️ Everything here is inside `@media screen and (...)`, so it cannot leak into the print
path or either PDF.

⚠️ **An interim version stacked the acceptance block into one column.** That was only
needed because of the squeeze, and once the real width was restored it made the preview
disagree with the PDF. It is gone, and a test asserts the block stays two columns — the
preview must show what the customer gets.

**Confirmed on the owner's own iPhone**, which is what settles the one thing the emulator
could not: Safari honours the `zoom` used for the scaling. Chromium with an iPhone
viewport is not Safari; keep using a real phone as the gate for anything visual here.

---

## 23. The export block folds, and the price list archive is real (v1.7.2, 2026-08-31)

Two owner requests, taken together as one release.

### 23.1 The export block folds

`.generate-bar` sits **outside** `.panel-scroll`, so it is a fixed footer of the
control panel: 331px that could never be scrolled away, permanently crowding out
the controls above it. It folds now. Collapsed keeps the saved-status line and the
primary Download button and hides the four secondary actions with their hints:
**381px → 129px measured, 252px recovered.**

`aria-expanded` on the toggle is the single source of state — the CSS reads the
attribute directly (`.generate-bar-toggle[aria-expanded="false"] ~ .generate-bar-extras`),
so there is no class that can disagree with it. Remembered per machine in
`cc_export_expanded_v1`, the same pattern as `cc_panel_width_v1`.

⚠️ **The default is expanded**, which is why all 77 pre-existing tests stayed valid.
Keep it that way: a colleague who never touches the toggle must see the build they
had before.

The new CSS sits beside the original `.generate-bar` rules, **not** in the Tier A
override block — it declares a new component rather than overriding an old one, so
the "delete the block to revert the look" contract (§10/CLAUDE.md) still holds.

### 23.2 The price list archive

The store existed since 2026-08-17 and **nothing ever read it back** (§14). It is a
real archive now: the drawer has **Quotes / Price lists** tabs, rows Open and Delete
exactly like quote rows, and price lists ride in `Export full archive (.json)`.

The record gained two fields it could not restore without:

- `basisColumn` — without it a reopened list silently fell back to List price. It
  would look right and be **priced wrong**, which is the worst kind of defect this
  tool can have.
- `mkByPart` — so the Margin (TG) card survives a reopen. ⚠️ **INTERNAL.** This is the
  newest path by which cost could reach a customer document;
  `test_cost_never_reaches_the_price_list_pdf_or_the_excel` scans the decompressed
  PDF text and the workbook XML, and proves itself non-vacuous first by asserting
  the cost really is on the internal card.

**Saving a bound list updates it in place** rather than piling up near-identical
entries. `PL_ID` holds the binding, and it is **released** in two places, because
silently overwriting one customer's list with another's is the only way this could
lose real work: retyping the customer name, and `Clear all`. `PL_ID` is in memory
only, so a reload also unbinds — deliberately, the safe direction.

Import reuses `mergeArchives`, which now takes an id field (`quote_id` for quotes,
`id` for price lists). Price lists collide exactly the way quotes do — every machine
starts at `PL-YYYY-0001` — so the never-overwrite rule of §20.3 applies unchanged.
`ARCHIVE_FORMAT_VERSION` is **2**; a v1 file simply has no `pricelists` key, which is
not an error, and a v1 file still imports.

### 23.3 The trap, and it is a general one

⚠️ **`.archive-list` is `display:flex`, and an author `display` rule beats the UA
stylesheet's `[hidden]{display:none}`.** Setting `.hidden` on the list therefore did
nothing and **both archives rendered stacked in the same tab** — a quote sitting in
the Price lists tab. Every scripted check was green, including the one that had just
confirmed the tab switch ran, because the switch *did* run; only the hiding failed.
A screenshot caught it. Fixed with an explicit `.archive-list[hidden]{display:none;}`.

This is the same lesson as §22: **look at the screen.** A geometric or attribute-level
assertion cannot see a layout that is wrong but well-formed.

### 23.4 Tests

**91**, up from 77. Every new guard was proven to go red with the thing it protects
broken — fourteen deliberate breaks in total.

⚠️ Two honest limits, recorded rather than papered over:

1. The cost-leak breaks prove the **scanners detect a cost value** in the PDF and in
   the workbook. They do not enumerate every conceivable leak path.
2. `plOpenFromArchive`'s `basisColumn || 'list'` **cannot be broken independently** —
   `plPopulateBasisOptions()` already defaults an unknown basis to `list`. It is kept
   as belt-and-braces so the state does not depend on another function's side effect,
   but do not read the passing test as proof that *that* line is load-bearing. The
   pre-1.7.2 test's real teeth are `mkByPart`, which was proven failable.

⚠️ **Bumping `APP_VERSION` turns three tests red on purpose.** `test_version.py` pins
the version deliberately, so a bump is a conscious act; `test_archive_transfer.py`
pins `format_version`. Update the pins, do not loosen the assertions.

## 24. The price list PDF's family heading (v1.8.0, 2026-09-08)

`buildPricelistDocDefinition` pushed each family as **two independent content nodes** — a
one-row table holding the grey band, then the product table with `headerRows: 1`. Nothing
tied them, so a page break could fall between them: the band printed at the foot of one page
and its products opened the next with no heading above them. Reproduced before the fix on
page 3 of a full price list — band at y=721.6, last product row at y=684.2.

The fix has **three** parts, and the first is not sufficient on its own.

**1. One table per family with `headerRows: 2`** — row 0 the band with `colSpan` across every
column, row 1 the column header, products after.

⚠️ Header rows repeat, so a family spanning a break now reprints its name at the top of the
continuation page, above the column header. Deliberate, and approved by the owner
2026-09-08 before the change.

**2. A fresh header row per family.** `cols` was ONE array of cell objects pushed **by
reference** into every family's table. pdfmake writes layout state (`_width`, `_calcWidth`)
onto cells as it renders, so the column labels appeared on the **first family only** and
every family after it got a blank row of the right height. This was in the shipped v1.7.2
PDF and was found by *looking at the render*, not by any assertion. `makeCols()` returns
fresh objects now.

⚠️ **And so does `makeWidths()`.** This paragraph originally ended "only `widths` is
shared, and those are plain strings". **That was wrong.** They are strings on the way
in and pdfmake REPLACES them in place with annotated objects on the way out, so every
family table was laid out with the FIRST family's column widths. See §26.

**3. A measured `pageBreakBefore`.** ⚠️ **`headerRows: 2` does NOT keep the header with the
body's first row.** pdfmake renders both header rows at a page foot and starts the body on
the next page, leaving a band *and* a column header dangling under nothing. That was
**assumed rather than measured**, passed the guard once by luck of layout, and went red the
moment part 2 changed the row heights. A family table is tagged
`headlineLevel: 'plFamily'` and moves whole when the page has too little room left.

`PL_FAMILY_MIN_BLOCK` is **120pt**, measured from a generated PDF rather than estimated:
`startPosition` carries `pageInnerHeight` and `verticalRatio`, so room left is
`pageInnerHeight * (1 - verticalRatio)`. In a full 129-item list the four dangling families
had **2.4, 60.9, 74.9 and 76.1pt** left; the closest legitimate multi-page family had
**148.8pt**; band + column header is 77.7pt and one product row 36.3pt. 120 sits in the
middle of a clean 77–148pt separation.

⚠️ **Re-measure the threshold if the band, the column header or the row padding changes.**

⚠️ **Still not `unbreakable`, still not `dontBreakRows`.** Both discard content that outgrows
a page body (§18.2). `pageBreakBefore` relocates a node and never holds or clips one.

⚠️ The guard locates the band by **font**, not by string. Product descriptions contain the
family name ("CCpilot V1200, LinX Base") in Roboto; only the band is Poppins. A text-only
search matches the descriptions and passes vacuously. It is proven able to fail by
neutralising `PL_FAMILY_MIN_BLOCK` to 0.

**Lesson, and it is the same one as §22 and §23.3: look at the render.** The suite went green
on a fix whose central assumption was false. What exposed it was rendering the PDF to PNG and
looking — which is also the only thing that found the blank column headers that had been
shipping since August.

⚠️ **Reported, not fixed — the NET PRICE column is too narrow.** Four-digit prices break
mid-number (`€1,002.8` then `0` on the next line) and the "NET PRICE" header wraps. Identical
in v1.7.2, so not caused by this work. Widening it reflows every price list already sent, so
it is an owner decision.

The three exclusions of §18.2 stand: rows fragmenting across a page edge, the `§` T&C block
splitting, and the trailing footer-only page are all untouched.

## 25. The address, the optional list price and the typed unit price (v1.8.0, 2026-09-08)

Three colleague requests, relayed by the owner, designed against a mockup and approved before
any code was written. The mockup is at
https://claude.ai/code/artifact/6f68afde-c37e-4d8c-af83-76a85fa538e5 and the spec and plan are
in `docs/specs/` and `docs/plans/` under `2026-09-08-v1.8-…`.

### 25.1 The customer address

One multi-line box under Company on **both** tabs (`#custAddress`, `#plCustAddress`), bounded
at **300 characters** with the existing counter, printing as typed.

- Carried as `customer.address` in the export object, `customer_address` in the quote archive
  record and `customerAddress` in the price list meta. ⚠️ **Three names on purpose**, the same
  split §20.1 already documents: the record stores what restores a field, the export carries
  what the document prints.
- Rendered on **four** surfaces: `renderDoc()`, the pdfmake quote, `generate_pdf.py`, and the
  price list (screen + pdfmake). Escaped on every one — an archived record carrying markup
  executes on open, and archives move between colleagues (§20.2).
- An empty address renders nothing at all, so a blank field leaves all four surfaces identical
  to v1.7.2.

⚠️ **The price list's `Prepared for X · attn: Y` subtitle is GONE**, replaced by the quote's TO
block — the owner's call on 2026-09-08 was that both documents get the same treatment.
`Prepared by` is a different field (the KAM) and did not move. The `.billto` rules are widened
to `#plDocRoot` in the **original** CSS, not in the Tier A override block, because this is a new
surface for an existing component and "delete the block to revert the look" must keep holding.

### 25.2 The optional List Price column

`#showListPrice` in the Terms section, **checked by default** — a colleague who never finds it
sees the build they had. Off removes the column *and* the `+ N% negotiated discount` tag on the
screen and in both PDF paths: a discount advertised off a price the customer can no longer see
is worse than either alone.

- `show_list_price` in the export and the archive record. `openQuote` restores it with
  `rec.show_list_price !== false`, so a record written before v1.8.0 reopens as ON, which is how
  it was sent.
- ⚠️ **The pdfmake `widths` array must shrink with the column** or pdfmake throws.
- ⚠️ It sits beside `#includeForecast` in Terms, **not** in the "Document options" card the
  mockup drew. There is no such section — `#includeSignature` lives in the signature block and
  `#includeForecast` in Terms — and inventing one would have moved two working controls.

### 25.3 A typed unit price over a volume tier

`unitPriceOverride` on a cart line — a number in **EUR**, or `null`. `computeLine()` returns it
as `finalUnitPrice` when set, so margin, the line total and both PDFs follow with no further
change. Four owner decisions, all from 2026-09-08:

1. **The typed price wins.** Extra discount is cleared and `disabled` while an override is set,
   so one number decides the price. `Use tier price` restores both.
2. **⚠ deviation shows on ANY difference from the tier price**, above it as well as below, with
   the signed percentage. One `deviationState()` serves the template and the computed-only path
   so the two cannot drift.
3. **A tier chip click keeps the typed price.** ⚠️ `setTier` deliberately does not touch
   `unitPriceOverride` — a stray click must never destroy a negotiated number. It carries a
   comment saying so; do not "tidy" it into clearing the override.
4. The customer document is unchanged in shape and says nothing about an override.

⚠️ **The price is typed in the DISPLAYED currency and stored in EUR**, divided by `fxOut()` on
the way in — a new one-line accessor for the multiplier `fmtMoney` already applies on the way
out. Without it, 245 typed under SEK would be stored as 245 EUR. A currency switch therefore
*converts* an override rather than reinterpreting it.

⚠️ **Do not re-render the row on input.** The controls are always in the markup and toggled by
class, and `updateProductRowComputed` keeps them in step. The plan originally called for
`renderAll()` so the disabled state and the button could appear; that rebuilds the row's
`<input>` elements and loses the caret after one character, which is the exact thing
`updateProductRowComputed` exists to prevent (its own comment says so). Verified by typing
`245.00` one character at a time and asserting focus, value and caret — no `fill()`-based test
can see this.

### 25.4 Tests — 114, and every new guard proven able to fail

Ten protections were broken on purpose and the guard that should catch each one was run.
**Eight went red immediately. Two stayed green, and both were the test's fault:**

1. The currency test typed the price while **EUR** was selected, where `fxOut()` is 1 and the
   division is a no-op — it passed with the conversion deleted. It types in **SEK** now.
2. The cost-leak probe searched the row's `inner_text()` for the cost. ⚠️ **`inner_text()` does
   not include an `<input>`'s value**, so the cost was never in the string and the non-vacuity
   assertion failed against correct code. It reads the field's value directly.

The second matters beyond itself: a cost scan that cannot see the cost on the internal card
would report "cost never reaches the PDF" about a page that never had a cost on it.

⚠️ **One gap, named rather than hidden: there is no automated guard for the list-price flag in
`generate_pdf.py`.** It was verified by hand — both states exported and the rendered PDF text
read, `LIST PRICE` and `526.76` present when on and both absent when off — but nothing in the
suite would catch a regression. The break-pass script reports it as SKIP with the reason.

### 25.5 The trap that cost the most time

⚠️ **`CLAUDE.md` says "Bash heredocs mangle edit scripts here. Write the script to a file, then
run it." That is not advice.** A scripted edit written as a heredoc turned `split('\n')` into a
real line break and broke the entire app script — every test failed, including four that had
passed minutes earlier.

The failure signature is worth remembering: **previously-green tests going red is "the app is
broken", not "this feature is wrong".** That pointed at a page error rather than at the feature
being built, and `node --check` on the inline script found it in one step. Syntax-check the app
script after any scripted edit; the suite reports a parse error as a wall of unrelated failures.

## 26. The price list's NET PRICE column broke prices in half (v1.8.0, 2026-09-08)

Four-figure prices printed as `€2,438.6` on one line and `0` on the next. **Measured on the
shipped v1.7.2 build: 73 of 129 prices were broken — 57% of a customer-facing price list.**

⚠️ **The cause was not the column width. It was a shared array**, the same class of bug as the
shared `cols` in §24 and found the same way — by rendering the PDF and looking at it.

`widths` was built once and passed by reference to every family's table. **pdfmake REPLACES
the entries of that array in place with annotated objects** (`_minWidth`, `_maxWidth`,
`_calcWidth`) during layout. Probed across 18 family tables, every one reported *identical*
widths to twelve decimal places — they were the same objects, computed once from CCpilot VI.

CCpilot VI's prices are ~40pt wide. CCpilot V1200's are wider. So every family after the first
was laid out with a NET PRICE column sized for someone else's numbers, and its prices
overflowed and broke mid-number. The NET PRICE column measured `_calcWidth` 43.64 against a
`_maxWidth` of 44.35 — **short by 0.71pt.**

Fixed by `makeWidths()`, a factory called once per family, exactly like `makeCols()`.
`columnCount` is taken once for the band's `colSpan`, which is safe because the column *count*
is stable even though the width *objects* are not.

⚠️ **Do not fold either factory back into a shared constant**, and do not "fix" this class of
symptom by hardcoding a width — the width was never the problem.

The guard (`tests/test_pricelist_columns.py`) asserts on the symptom a customer sees: no line
of the extracted PDF text may be nothing but one or two digits, which is what a mid-number
break leaves behind. It first asserts the document contains at least 20 four-figure prices, so
it cannot pass on a fixture that never exercises the wide families. Proven to fail by sharing
the widths array again.

## 27. The printed numbers did not multiply out (v1.8.0, 2026-09-08)

Found by the owner reviewing a real quote on screen, not by any test.

A quote in USD printed:

    CCpilot V1000, 2CAN    UNIT $1,042.29    QTY 15    TOTAL $15,634.30

**15 x 1,042.29 is $15,634.35.** A customer checking the multiplication got a different
number from the one they were being invoiced for.

⚠️ **Pre-existing — reproduced on the v1.7.2 tag**, so every converted-currency quote ever
sent carried it. EUR quotes were always exact, which is why it survived so long.

**Cause.** Prices are held in EUR and converted at display time by `fmtMoney`. The unit
price and the line total were each rounded to cents **independently**: 965.08 EUR at 1.08
is 1042.2864, which prints as $1,042.29 (rounded up), while the total printed
15 x 1042.2864 = $15,634.296 -> $15,634.30. Two correct roundings that contradict each other.

**Fix.** `computeLine` now derives the line total from the unit price **as the customer sees
it** — converted, rounded to cents, then carried back to EUR — via
`lineTotalFromDisplayedUnit()`. The document's own figures multiply out. In EUR the rate is
1, so a EUR quote is byte-identical to before; a test pins that.

⚠️ **Do not "simplify" `lineTotal` back to `finalUnitPrice * item.qty`.** That is the defect.
`tests/test_money_consistency.py` parses the printed figures back out of the screen document
and the PDF and multiplies them; it goes red in USD and SEK with the old expression, and
stays green in EUR, which is how you know the guard is discriminating rather than lucky.

### 27.1 Two smaller things from the same review

**The left panel went stale on a currency change.** The row still read `@ €965.08` and held a
Unit price figure in euros while the document said $1,042.29. The shared field listener calls
`renderDoc()` only, so the panel was never rebuilt — yet editing the **FX rate** box called
`renderAll()`, so the two halves of the Currency card behaved differently. `#currencySelect`
now has its own `renderAll()` listener. Pre-existing; the new Unit price input made it visible,
because a stale number in an editable box reads as a value someone typed.

**The Unit price box looked pre-filled.** Its placeholder was the tier price, duplicating the
`@ price` label directly above it, so a line with nothing typed looked like a line with an
override. The placeholder now reads `tier price`, and the label above says `tier @ ...` so it
names itself. The box is empty unless a price was actually typed.

## 28. Escaping on the WeasyPrint path (2026-09-08, after v1.8.0)

`generate_pdf.py` escaped **one** value — the quote number — and interpolated **17 others
raw** into the HTML it hands WeasyPrint: the customer name, contact and country, every
product description, part number and line note, the volume-tier labels and sublabels,
appendix names, the T&C file name, the signer's name and title, the payment and delivery
terms, the VAT note and the dates.

Every one of those is free text a colleague can type, and archives move between colleagues.
§20.2 already recorded that an archived `quote_id` of `<img src=x onerror=…>` executes on
open; that hole was closed for the quote number in v1.6.0 and left open for the rest of the
document.

⚠️ **Escaping is applied AT THE POINT OF READ, not at each interpolation.** `cust_name`,
`qty_heading`, `terms` and the rest come out of `offer` already escaped, so every f-string
below them is safe by construction. Patch the 17 call sites instead and the next person to
write `{cust_name}` in a new block silently reopens it.

⚠️ **An HTML fallback must be applied AFTER escaping.** `sig.get('signer_name') or '&nbsp;'`
escaped as a unit prints a literal `&amp;nbsp;` on an empty signer line. Same for the
volume-tier `label or "&nbsp;"`. Both are covered by a test.

⚠️ **`html_escape`, never `html.escape`** — `build_html` has a local variable named `html`
that shadows the module for the whole function (§20.2). `import html` inside it raises
`UnboundLocalError` and breaks the whole WeasyPrint path.

**The guards assert on `build_html`'s output, not on a rendered PDF.** A PDF cannot
distinguish `<b>x</b>` printed as text from `<b>x</b>` interpreted as markup — by the time
it is a PDF the evidence is gone. One test does go to a real PDF, to prove the payload
survives as *visible* text. Proven able to fail: reverting a single field's escaping turns
three of the five guards red.

**The case that matters more day to day than injection does:** `Wilson & Sons Ltd` is an
ordinary customer name. It must reach the page with a real ampersand and no `&amp;` visible,
which is a correctness requirement, not a security one — and it is tested.

⚠️ **The in-browser app was already safe** — `renderDoc()` and `plRenderDoc()` escape through
`escapeHtml`, and the pdfmake builder passes strings as text nodes rather than markup. This
was the WeasyPrint path only.

## 29. The device gate found two defects the suite could not (v1.8.3, 2026-09-09)

The v1.8.2 device gate (`SESSION_HANDOFF_2026-09-08.md` §6) was finally run, against the
delivered build rather than the working tree. **Five of its seven checks passed. Step 1
failed, and writing the guard for it uncovered a second, unrelated defect.**

Both had shipped. Neither was found by 125 passing tests.

### 29.1 Both PDF paths rounded EUR money before converting it

`buildExportObj()` stored `final_unit_price_eur`, `line_total_eur` and `subtotal_eur`
through `round2()` — snapping them to cents **while still in EUR**. Both PDF renderers
(pdfmake `:4550`, `generate_pdf.py:172`) then multiply those figures by the exchange rate,
so the cent lost in EUR came back **magnified by the rate**. The screen prints the
full-precision value, so screen and document disagreed and the document stopped
multiplying out.

Measured over 1161 product/quantity combinations per currency on the delivered v1.8.2:

| currency | rate | screen wrong | **PDF wrong** | worst error |
|---|---|---|---|---|
| EUR | 1 | 0 | **0** | — |
| USD | 1.08 | 0 | **40** | 1 cent |
| SEK | 11.4 | 0 | **552 (47.6%)** | **5 öre** |

⚠️ **EUR is clean because at rate 1 the rounding is a no-op.** That is the whole reason
this survived: the defect is invisible in the currency most quotes are written in.

**Worst case is a typed price.** A price typed in kronor is stored as `typed / rate` and is
therefore never a 2-decimal EUR number, so `round2()` moved it furthest: **2,750.00 kr typed
printed as 2,750.02 kr** — a negotiated number altered in the customer's document.

⚠️ **`afc61a9` (§27) fixed `computeLine`, which fixed the SCREEN only.** The `round2()` calls
are older — `git show v1.7.2` has them, and no `lineTotalFromDisplayedUnit` at all, so in
v1.7.2 screen and PDF were both wrong and agreed with each other. §27's "the document's own
figures multiply out" was true of the screen and false of the document for three releases.

⚠️ **Why §27's own PDF guard stayed green.** It uses 965.08 EUR × 15 at 1.08, and
`round(1042.29 × 15, 2) / 1.08` lands on exactly 14,476.25 EUR — the rounding is a no-op for
that one fixture. **A guard on the right surface, asserting the right thing, that cannot
fail.** The new guard uses CCpilot VI × 15 in SEK, which does not round-trip, and says so in
its docstring so nobody re-uses the old fixture and concludes the path is covered.

⚠️ **Do not restore `round2()` on any EUR field a renderer converts.** `tier_price_eur`
keeps its rounding (no document reads it) and `volume_tiers[].price` keeps its rounding
(entered verbatim in the display currency, never fx-converted). Those two are correct.

### 29.2 A typed unit price reached neither the document nor the archive

Found because the rounding guard's own **non-vacuity check** failed: the document did not
show the price the test had just typed.

`setUnitPriceOverride()` mutated the cart and returned. Its siblings do not:

```
setExtraDiscount      -> updateProductRowComputed(); renderDoc();
setQty                -> updateProductRowComputed(); renderDoc(); scheduleAutoSave();
setUnitPriceOverride  -> (nothing)
```

1. **The live document kept printing the tier price.** Typing 2,750.00 left the preview at
   2,929.34 until some unrelated control happened to call `renderDoc()`. The preview is what
   gets checked before a quote is sent.
2. **The price was never autosaved.** 2000 ms after typing — 4× the 500 ms debounce — the
   archive record still held `null` while the cart held the price. Touching qty flushed it.
   **Type a negotiated price, close the tab, and it is gone.**

⚠️ **`renderDoc()`, never `renderAll()`** here — `renderAll` rebuilds the row's `<input>`
elements and loses the caret after one character, which is exactly what §25.3 exists to
prevent. That is why the fix is not simply "call renderAll like `setTier` does".

⚠️ **The existing archive guard could not see this, and its blindness came from this file's
own advice.** `test_the_override_survives_the_archive` calls `autoSaveNow()` explicitly,
because §18.4 and the 09-08 handoff both say autosave is debounced and forcing it beats
racing a timer. That is correct for a timing race — and it bypassed the missing
`scheduleAutoSave()` completely. **A guard that forces the save cannot tell you whether
anything would have saved.** Where the question is *does the app persist this*, the test
must not persist it on the app's behalf.

### 29.3 What the gate is for

Five of the seven checks passed and would have passed in any release. The two that mattered
were found by **rendering the document and comparing it against the screen**, and by a
**non-vacuity assertion failing** — never by an outcome assertion going red.

That is now four consecutive releases in which every customer-facing defect was found by
looking at output and none by the suite. The suite went 125 → 130 here; it holds these fixes
in place, and it did not find either of them.

⚠️ **One caveat on this run, recorded because it is not the gate as written.** Playwright
refuses `file://`, so the gate drove the delivered bytes over `http://127.0.0.1:8142` rather
than by double-clicking the file. Everything about content and arithmetic is covered by that;
**opening standalone from disk with no network, and the real Windows save dialogs, are not.**

# Handoff — CrossControl Offertbyggare

**Person:** Mattias Schill, Key Account Manager, CrossControl AB (mattias.schill@crosscontrol.com)
**Repo owner (GitHub):** mattiasschill77-gif
**Project:** "Offertbyggare" — a single-file HTML quote-builder tool for CrossControl's CCpilot HMI displays. Runs entirely client-side, normally opened directly from disk (`file://...crosscontrol-offertbyggare.html`) from a OneDrive-synced folder on a Windows PC. No server, no build step for the person using it — the HTML file *is* the app.

Read this whole file before touching code. It replaces having to re-read the full chat transcript.

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

*"Continue work on the CrossControl Offertbyggare — read HANDOFF.md in the repo first."*

**Current status (2026-08-14): there is no known open bug.** The §4 PDF-download
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

# Session handoff — 2026-08-14 → 2026-08-20

**Read `HANDOFF.md` first** for architecture, the brand system and the standing
contracts. This file covers only what changed in this stretch, what was decided,
and what is still open.

**Live build: `c5000ac`.** Pushed, working tree clean, 0 unpushed on every branch.

---

## 0. Start here if you are picking this up cold

1. The tool is now **two tools in one file**: a quote builder and a customer
   price list, switched by tabs in the top bar.
2. **Gross margin (TG) is live but starved of data** — manufacturing cost is
   known for **1 of 86 products**. That is the single biggest open item, and it
   is a data problem, not a code problem. See §4.
3. Two real bugs are still open, both described in §4: the **price list archive
   is write-only**, and the 2024 workbook contains a **duplicate part number at
   two different prices**.

---

## 1. What shipped

Chronological, newest last. Every one is merged to `main` and pushed.

| Commit | What |
|---|---|
| `7682507` | Committed the July 17 delivery build that had never been pushed — inlined libraries (fixing the PDF download) plus Zak's three features |
| `3323889` | Resizable control panel (drag handle, persists per machine) |
| `d05887a` | **Price list tab restored** + bill-to block on the quote |
| `a5c1f93` | **Tier A UI polish** + form labelling |
| `f340496` | Price list **"Calculate from"** basis column |
| `597c501` | **Accessories & Cables** in the price list + duplicate part warning |
| `41bb93e` | Fix: **archive rows are clickable** |
| `913cdd6` | **Margin (TG) card** + one live SEK/EUR rate for both tabs |
| `c5000ac` | **Manufacturing cost imported** from the price list |

### The two recoveries worth knowing about

**The price list tab existed only outside git.** It was found in a 2026-07-07
build sitting in `OneDrive\WEB offert\files\`, minutes from being deleted as a
"stale duplicate". No commit had ever contained it. It is now committed and
live. Detail in `HANDOFF.md` §10.

**The delivered build was never pushed.** On 2026-08-14 the OneDrive delivery
folder was an hour newer than the only commit, so `HANDOFF.md` described the PDF
bug as open four weeks after it had been fixed. Trust the shipped file over the
docs, and check both locations before believing any status claim.

---

## 2. Decisions taken (owner's calls — do not silently reverse)

- **Discount stacks on top of a chosen volume column**, with a visible warning
  whenever it does. Tier prices are already ~50% under list, so stacking
  silently would give away margin.
- **A product with no price in the chosen column falls back to its list price**
  rather than disappearing from the customer's document.
- **The customer document never states which volume column was used.** All basis
  feedback is panel-only.
- **Margin is internal.** The Margin (TG) card is badged "never printed". Cost
  and margin must never reach the document, either PDF, or the Excel export.
- **Duplicate part numbers are reported, never deduped.** Silently dropping one
  would mean picking a price at random and hiding a commercial problem.

---

## 3. Gross margin — the model

Mirrors `TG_kalkyl_och_valuta.xlsx` exactly:

```
TG  = (SP - MK) / SP            (sheet B12)
TB  = SP - MK                   (sheet B13, gross profit)
SP* = MK / (1 - target TG)      (sheet B14, price needed to hit the target)
```

MK is quoted in **SEK**, prices are in **EUR**.

⚠️ **One `sekPerEur()` serves both tabs, reading the Currency card.** `computeTG`
used to multiply by `meta.tg_assumptions.fx_sek_eur` — a rate frozen into the
price list at import (10.54 SEK/EUR) that nobody could edit — so the same
product read **66.2%** on the quote and **68.7%** on the price list. Never
reinstate the meta value as the working rate; it is a snapshot, not a rate.

One oddity in the source workbook, for information: `B12` reads
`1 - ABS((E5-B6)/B5)` and references **E5, which is empty**. It gives the right
answer only because empty evaluates to zero. If anyone types into E5 the sheet
silently starts computing something else.

---

## 4. Still open

### 🔴 Manufacturing cost barely exists — 1 of 86 products

Margin works, but there is almost nothing to calculate from. The workbook itself
says MK must come from **Monitor**. Until then MK is typed per product.

**The importer is already prepared** (`c5000ac`), so the day the column appears
it is read with no code change. Accepted headers, currency handling and the
exclusion list are documented in `HANDOFF.md` §17. A one-page spec written for
requesting the column lives in the demo kit:
`Desktop\CC Quote Builder (QB)\Price list - manufacturing cost column (spec for the meeting).txt`

Two questions that spec asks the business to answer: **how current** the cost
will be, and **who owns the refresh**. A silently stale cost is worse than none.

⚠️ If cost lands in the master price list, that workbook becomes an **internal**
document and must not be forwarded to customers as-is.

### 🔴 The price list archive is write-only

`plSaveToArchive()` writes `cc_pricelist_archive_v1`, mints an id (`PL-2026-0001`)
and confirms with a toast. **Nothing ever reads it back** — no list, no loader,
no UI. Every saved price list is unreachable. The Archive drawer in the top bar
is the *quote* archive only.

Fixing it needs a price list archive UI mirroring `renderArchiveList` /
`openQuote`. Note the saved record also omits `basisColumn`, which must be added
before a loader could restore a price list correctly.

### 🟠 Duplicate part number in the 2024 workbook

`C000082-26` appears twice in the Cables section as two different products:

| Row in "Price list - Euro" | Description | Price |
|---|---|---|
| 159 | Straight M12 to RJ45 male, 2m | €61.00 |
| 180 | Ethernet cable adapter V700. DIN M12 to RJ45 male. | €45.00 |

Verified by reading the xlsx directly — not a parser bug. A price list including
Cables shows the same part number twice at two prices, and because selection is
keyed by part number the two cannot be picked apart. The app warns; **the fix
belongs in the workbook**.

### Smaller / deferred

- The **legacy positional parser** still sets `mk_sek: null`. It only runs when
  no header row is recognisable, so the real file is covered — but a cost column
  on a headerless sheet would not be read.
- **Tier B/C UI work** from the redesign brief was deliberately not done: the
  archive drawer row treatment, responsive behaviour below 1280px, and the empty
  band between panel and document at wide widths.
- The redesign brief's **product-card grid and configurator grouping were
  declined** — they assume a CPQ model this tool does not have. Variants are
  baked into the SKU, so cards would be worse than search. Reasoning is in the
  chat record, not repeated here.

---

## 5. Where everything lives — four copies, keep them identical

| Copy | Path |
|---|---|
| Repo | `github.com/mattiasschill77-gif/crosscontrol-offertbyggare` |
| Delivery | `OneDrive\WEB offert\New\CrossControl-Offertbyggare` |
| Demo kit | `Desktop\CC Quote Builder (QB)` |
| Prototypes | `Desktop\CC QB Prototypes` |

After every merge, copy to all three non-repo locations and **verify by md5** —
do not assume the copy ran.

- The demo kit holds `START HERE.txt` (a ~10 minute demo script) and a
  `Fallback\` copy of the previous build as live-demo insurance.
- The prototypes folder holds `Live build (mirror).html` and
  **`Current build - for comparison.html`, frozen at `d05887a` on purpose** —
  never refresh it; it is the "before" half of the before/after.

---

## 6. Traps — all of these cost real time this week

- ⚠️ **Verification needs the UI in a non-default state.** Controls that have not
  rendered yet audit as absent, and the audit then reports success. A claim of
  "77 of 77 controls labelled" was measured with the price list families
  collapsed; the real figure once expanded was **611 of 611**. Expand every
  family, select all, add a custom line and enable volume tiers *first*.
- ⚠️ **A hover state is a promise.** Tier A gave archive rows an orange hover
  while only the small Open button was wired, which read as "the archive won't
  open". Wire the click or do not add the hover.
- ⚠️ **Do not compare formatted strings in assertions.** `68.73%` vs `68.7%` is
  the same number at two precisions; it produced a false "the tabs disagree"
  failure. Compare numbers.
- ⚠️ **A half-applied edit passes unit-level checks.** A script that asserted and
  aborted left a consumer without its declarations (`mkAfter is not defined`);
  only driving the real file input caught it. Test end to end.
- ⚠️ **`grep -c` counts matching LINES, not occurrences** — this HTML has single
  lines megabytes long. Use `grep -o … | wc -l`.
- ⚠️ **Button-label restoration is not a pass signal** — the `.catch()` restores
  it too, so a failure reads as a pass. Assert on a download event and no alert.
- ⚠️ **`file://` is blocked** by both the preview tool and Playwright. Serve over
  `http://localhost` (`.claude/launch.json` has `cc-offert` 8140, `cc-offert-dev`
  8142, `cc-proto` 8143). `npx` fails there on the space in `C:\Program Files`;
  use python's `http.server`.
- ⚠️ **CSS/layout is duplicated three times** — the app's `<style>`, the pdfmake
  style objects, and `generate_pdf.py`'s f-string CSS. A document change must be
  made in all three or the PDFs silently diverge from the screen.
- ⚠️ **Tier A is an appended CSS override block** placed before `@media print`.
  Deleting the block reverts the look. To consolidate later, fold the overrides
  into the originals **and** delete the block — never keep both.

---

## 7. Suggested next actions

1. **Take the cost-column spec to the meeting.** Everything else about margin is
   already built and waiting on that data.
2. **Fix `C000082-26` in the master workbook** before sending any price list that
   includes Cables.
3. **Decide on the price list archive**: build the loader, or remove the "Save to
   archive" button so it stops implying something it does not do.
4. Optional: the deferred Tier B UI work in §4.

# CLAUDE.md — CrossControl Offertbyggare

Guidance for Claude Code working in this repository.

**This is day-job work for CrossControl AB. It is not WhiskeyVault.** If a session
mentions Room, Firestore, Gradle, Play Console or whisky, it is in the wrong project.

**Read `HANDOFF.md` first, then the newest `SESSION_HANDOFF_*.md`.** Between them they
carry the architecture, the standing contracts and every trap that has cost time. They
replace re-reading chat history.

## What this is

A single-file HTML tool for CrossControl's CCpilot HMI displays, used by Mattias Schill
as Key Account Manager. **Two tools in one file**, switched by tabs:

- **Quote builder** — customer quotes from the CCpilot catalogue, exported as branded PDF
- **Price list** — a customer-facing fixed price list, exported as PDF *and* Excel

Entirely client-side. No server, no build step, no framework. `crosscontrol-offertbyggare.html`
*is* the app: CSS, markup, the product catalogue, pdfmake, SheetJS and the fonts are all
inlined. It runs from `file://` on a corporate laptop with no network.

## Running it

`file://` is blocked by both the preview tool and Playwright, so serve it:

```
python -m http.server 8142 --directory .
```

`.claude/launch.json` has `cc-offert` (this repo, 8142). Do not use `npx serve` — it fails
on the space in `C:\Program Files`.

## Before claiming anything works

- **Drive the real UI**, not just the functions. A half-applied edit passes unit-level
  checks; only clicking the actual control catches it.
- **Expand everything first.** Controls that have not rendered yet audit as absent, and
  the audit then reports success. Expand every price list family, select all, add a
  custom line, enable volume tiers.
- **Assert on outcomes, not labels.** A button returning to its normal caption is not
  proof: the `.catch()` restores it too. Assert a download fired and no alert appeared.
- **Compare numbers, not formatted strings.** `68.73%` and `68.7%` are the same number.
- `grep -c` counts matching LINES. This file has single lines megabytes long — use
  `grep -o … | wc -l`.
- Bash heredocs mangle edit scripts here. Write the script to a file, then run it.

## Hard rules

- **Cost and margin never reach the customer.** The Margin (TG) card is internal. Nothing
  about cost may appear in `plRenderDoc()`, either PDF, or the Excel export. Verify by
  decompressing the PDF streams and scanning the xlsx XML — not by reading the screen.
- **One `sekPerEur()`** reading the Currency card, for both tabs. Never go back to
  `meta.tg_assumptions.fx_sek_eur`; it is a snapshot frozen at import, not a rate.
- **The quote document is a customer document.** Its styling is duplicated in three
  places — the app's `<style>`, the pdfmake style objects and `generate_pdf.py`'s CSS.
  A change to one must be made in all three or the PDFs silently diverge from the screen.
- **Tier A CSS is an appended override block** placed before `@media print`. Deleting the
  block reverts the look. To consolidate, fold the overrides in *and* delete the block.
- Work on a branch, verify, merge to `main`, push.

## Deploying

After every merge the build goes to three places outside git. **Verify by md5** — do not
assume the copy ran.

| Copy | Path |
|---|---|
| Delivery | `C:\Users\Schill\OneDrive\WEB offert\New\CrossControl-Offertbyggare` |
| Demo kit | `C:\Users\Schill\Desktop\CC Quote Builder (QB)` |
| Prototypes | `C:\Users\Schill\Desktop\CC QB Prototypes\Live build (mirror).html` |

⚠️ `CC QB Prototypes\Current build - for comparison.html` is **frozen on purpose** at the
pre-polish build. Never refresh it — it is the "before" half of the comparison.

## Source data

The product catalogue is inlined as JSON. It comes from CrossControl's standard price
list workbook, imported through the app's own flexible Excel/CSV importer. Manufacturing
cost (MK) is quoted in SEK while prices are in EUR — see `HANDOFF.md` §15 and §17.

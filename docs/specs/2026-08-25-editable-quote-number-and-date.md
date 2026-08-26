# Design spec — editable quote number and issue date

**Date:** 2026-08-25 · **Requested by:** Zak Paulus, relayed by Mattias Schill
**Branch:** `feat/editable-quote-number-and-date` · **Base:** `main` (`8c55b36`, v1.5.0)

Two asks in one message, plus a defect found while reading the code for them.

---

## 1. Where this came from

Zak's original note: *"The only thing I noticed was having the ability to manually change
the quote date. i like to make the number look bigger than it really is."*

Asked to disambiguate, he confirmed it was the quote **number**: `-0001` *"making it look
like they are the first"*. He floated `year-month-customer-#` as a format but said
*"not really sure"*, and then landed on the design that actually gets built:

> *"if you made it default to what you have now but allow the box to be editable that
> could solve it (just like you did for the VAT box, where it defaults to VAT but can add
> 'or Tariffs' when I do a US quote)"*

**That is the design.** A free-text box with today's value as the default gives him the
`year-month-customer-#` format for free, without a format system nobody was sure about.

## 2. The defect this also fixes

`buildQuoteSnapshot()` stores `term_validity_days` but **no issue date**, `openQuote()`
restores none, and both renderers compute from `TODAY = new Date()` at page load:

- `renderDoc()` prints `Issued ${fmtDate(TODAY)}`
- `buildExportObj()` sets `issued_date: fmtDate(TODAY)`
- both compute `validUntil = fmtDate(addDays(TODAY, validityDays))`

So a quote issued in August and reopened from the archive in November **re-dates itself
to November**, with a fresh validity window. The customer document silently disagrees
with the quote that was actually sent. Storing the issue date fixes it as a side effect
of the feature.

## 3. Decisions — do not silently reverse

1. **Both fields default to exactly today's behaviour.** Nothing changes for someone who
   never touches them.
2. **The quote number is free text.** No format validation, no template picker.
3. **The running counter follows an upward edit**, so the number is set once rather than
   on every quote.
4. **Editing the number renames the archive record.** It never creates a second one and
   never overwrites an existing quote.
5. **Validity is computed from the issue date**, not from the machine clock.
6. **No hard limit on backdating.** The date is the owner's judgement. The tool warns
   internally; it does not refuse.
7. **Neither field's warnings ever reach the customer document.**

## 4. A — Editable quote number

The topbar badge `<span id="currentQuoteId">` becomes an editable input, keeping its
place and its styling. `QUOTE_ID` is already a plain `let`, so the value flows unchanged
into `buildExportObj()`, `buildQuoteSnapshot()`, the PDF and the archive.

- **Default:** `nextQuoteId()` exactly as today — `CC-{year}-{0001}`.
- **Free text.** Empty is refused (it keys the archive); the field reverts to the last
  good value with a panel note.
- **Counter follows upward edits.** If the edited value ends in a number **higher** than
  the current counter for the current year, the counter is set to it, so the next quote
  continues the series. A lower number, or no trailing number at all, leaves the counter
  untouched. Storage stays `cc_quote_counter_v1`, unchanged in shape.
- ⚠️ **Archive safety.** Autosave writes `store[QUOTE_ID]`. On an edit:
  - if the new id already exists in the archive → **refuse**, restore the previous value,
    and say so. Never overwrite another quote.
  - otherwise → **move** the existing record to the new key and delete the old one, so
    one quote stays one record. `LAST_OPEN_KEY` follows.
- ~~**File name.** Free text must be sanitised before it reaches a download name.~~
  **WITHDRAWN 2026-08-26 — measured, not needed.** With the number set to
  `CC/2026/0007`, Chrome's own download handling already produces
  `quote-CC_2026_0007.pdf`, and the export completes with no alert. A review confirmed
  it independently and found the sanitisation broader still: `/ \ : * ? < > |` and even
  `../../` all collapse, on both the pdfmake path and the JSON download. A sanitiser of
  ours would sit in the file looking like a protection nothing needs. The document keeps
  the id **as typed**, and a test asserts on `suggested_filename` so the claim stays
  checked.
- ⚠️ **Escaping, added 2026-08-26 after review.** Turning a machine-generated value into
  free text made two raw interpolations unsafe: `<span class="doc-id">QUOTE #${QUOTE_ID}`
  in `renderDoc()` (twice) and the same line in `generate_pdf.py`. Unescaped, a number
  containing markup renders **differently on screen than in the pdfmake PDF**, and an
  imported archive can execute script on open. Both are escaped, and a test asserts the
  three surfaces render a markup-bearing number identically.
- ⚠️ **The counter must be bounded.** `parseInt` on 23 trailing digits reaches `1e+23`,
  where `n + 1 === n`: `nextQuoteId()` then returns the same id forever and every new
  quote overwrites the previous one in the archive, permanently, with no UI to reset it.
  `bumpCounterTo()` refuses anything that is not a positive safe integer, and the field
  carries a `maxlength` like every other free-text field in the app.
- ⚠️ **Minting must skip numbers the archive already holds.** Importing a colleague's
  archive does not move the counter, so the series could walk straight into an imported
  quote and autosave over it. `nextQuoteId()` now skips occupied keys — safe from looping
  because the counter is bounded.

**Acceptance:** the default is unchanged for an untouched quote · a typed id appears on
screen, in the PDF, in the export JSON and in the archive list · typing an existing id is
refused with the old value restored and no archive record lost · a higher trailing number
moves the counter so the next new quote continues from it · an id containing `/` still
downloads, with a sanitised file name and the typed id inside the document.

## 5. B — Editable issue date

A date field in the Terms card, defaulting to today.

- Feeds `renderDoc()`, `buildExportObj().issued_date` and therefore `generate_pdf.py`.
  ⚠️ `renderDoc()` currently prints `fmtDate(TODAY)` directly and must read the field
  instead, or the screen and the PDF will disagree — the standing three-surface rule.
- **Validity derives from it:** `addDays(issueDate, validityDays)` in both places that
  compute `validUntil`. Changing the issue date moves the validity date with it.
- **Stored in the archive record and restored by `openQuote()`.** A record saved before
  this release has no date; those fall back to today, exactly as they behave now.
- **Internal warning only**, in the panel, never in the document: the date is in the
  future, or more than 30 days in the past. Worded as a note, not an error — a backdated
  quote is legitimate, a typo is not, and only the owner can tell them apart.

**Acceptance:** the default is today · a chosen date appears identically on screen, in the
pdfmake PDF and in the WeasyPrint PDF · validity moves with it · an archived quote
reopened later shows the date it was issued, not today's · the warning appears in the
panel and appears nowhere in either PDF · a pre-release archive record still opens.

## 6. Out of scope

The `year-month-customer-#` format as a built-in template · any hard block on backdating ·
changing the counter's storage shape or making it editable directly · the price list's own
numbering (`PL-YYYY-NNNN`), which is a separate store and a separate document.

## 7. Risks

| Risk | Mitigation |
|---|---|
| An edited id overwrites an archived quote | Refuse duplicates; move, never copy. Guarded by a test that must fail without the guard. |
| An id with a path character breaks the download | Sanitise the file name only, keep the document text as typed. |
| Screen and PDF disagree on the date | `renderDoc()` reads the same source as `buildExportObj()`; a test asserts all three surfaces agree. |
| A pre-release archive record has no date | Falls back to today — current behaviour, explicitly tested. |

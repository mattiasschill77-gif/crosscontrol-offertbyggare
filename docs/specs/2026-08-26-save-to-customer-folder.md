# Design spec — save the quote into a customer folder

**Date:** 2026-08-26 · **Owner:** Mattias Schill
**Branch:** `feat/save-to-customer-folder` · **Base:** `main` (`857957a`, v1.6.0)

Workstream E from `docs/specs/2026-08-25-v1.5-design.md`, now that the browser capability
has been measured instead of guessed.

---

## 1. What was asked

> *"användaren så få välja var offerterna sparas utöver det som finns idag. Vill användaren
> spara i en specifik kundmapp så ska han få göra det. Men ska alltid finnas en lokal backup
> att falla tillbaka på (om man inte avsiktligt tar bort den i arkivet)"*

Two halves, and the second one is the constraint: **the local archive copy is never
optional.** The customer folder is an addition to what exists today, not a replacement.

## 2. What is measured, not assumed

Run in the owner's own Chrome, with the app opened the normal way by double-clicking the
delivered file (`HANDOFF.md` §19):

```
{"url":"file:","save":true,"dir":true,"idb":true,"secure":true}
CC PROBE: {"idb":"ok","picker":"OPENED and cancelled = PASS"}
```

`indexedDB.open()` really succeeds and `showSaveFilePicker()` really puts a dialog on
screen — proven by the `AbortError` that comes back when it is cancelled. Presence alone
would have proved nothing; both APIs were called.

Also measured today, because the whole design depends on it:
`pdfMake.createPdf(dd).getBlob()` returns a **Promise** resolving to a 57 KB
`application/pdf` Blob. The PDF can therefore be handed to a folder instead of to a
download.

## 3. Decisions

1. **Additive.** `Download quote as PDF` is untouched, and every existing test around it
   must keep passing. A second action, `Save to customer folder…`, sits beside it.
2. **The archive copy is written first, unconditionally**, before anything leaves the app.
   It disappears only if the owner deletes it in the archive.
3. **The folder is remembered per customer**, keyed on the trimmed customer name, in
   IndexedDB (`cc_customer_folders_v1`). Directory handles are structured-cloneable, so
   they survive there; a plain `localStorage` cannot hold them.
4. ⚠️ **Never overwrite silently.** If `quote-<id>.pdf` already exists in the chosen
   folder, ask: replace it, or keep both. Rev A must not vanish because rev B was saved.
   This is the same rule the archive import and the quote-number edit already follow.
5. **Permission is re-checked every save** — `queryPermission({mode:'readwrite'})`, then
   `requestPermission()` if needed. Whether Chrome keeps the grant across a restart is
   deliberately not predicted; the code asks when it must.
6. **Degrade, never fail.** Where the API is missing or blocked, the ordinary download
   runs and the dialog says plainly that the browser chose the destination.
7. **PDF only.** Not the JSON export, not the price list tab. Both are easy to add later
   and neither was asked for.

## 4. The flow

```
Save to customer folder…
        │
        ├─ 1. write the archive copy            ← always, first, unconditional
        │
        ├─ 2. remembered folder for this customer?
        │        ├─ yes → still permitted? ── no → ask for permission
        │        └─ no  → showDirectoryPicker(), remember it
        │
        ├─ 3. quote-<id>.pdf already there? → ask: replace, or keep both
        │
        └─ 4. write the blob from pdfMake.createPdf(dd).getBlob()
                 │
                 └─ any failure at 2-4 → fall back to the ordinary download,
                    say why, and leave the archive copy standing
```

⚠️ **Capability detection must be feature-based** — `typeof window.showDirectoryPicker
=== 'function'`, plus a `try/catch` around the first real call. An API blocked by
corporate policy can exist and still throw. The catch falls through to the download and
**must not lose the file**.

⚠️ **An empty customer name has no folder key.** Saving with no customer set asks for the
folder every time rather than remembering it under `""`.

## 5. What can and cannot be tested automatically

Playwright cannot drive a native file picker, so the honest split is:

**Automated** — the archive copy is written before anything else and survives a failed
save · the fallback path runs when the API is absent · a name collision asks rather than
overwrites · the handle store round-trips (with a stub handle injected, since a real one
cannot be minted headlessly) · detection is feature-based and survives a throwing API.

**A device gate, by the owner** — pick a real folder once, confirm the PDF lands in it,
close the app, reopen it, save again to the same customer, and report whether Chrome
asked for permission a second time. That last answer is the only thing this spec
deliberately leaves open, and it changes nothing structural.

## 6. Acceptance

The archive copy exists after every save, including one the user cancels at the folder
picker · a machine without the API still gets its PDF, with a clear message · a second
save of the same quote to the same folder never destroys the first file without asking ·
an empty customer name does not create a `""` folder key · `Download quote as PDF`
behaves exactly as it does today, proven by the existing tests still passing.

## 7. Out of scope

The price list tab · the JSON export · syncing the archive itself to a folder · anything
that reads files back from the folder.

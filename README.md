# CrossControl Offertbyggare

Internal quote-builder tool for CrossControl AB's CCpilot product line. Single-file HTML app (no server, no build step to run it) plus a Python/WeasyPrint fallback for pixel-precise PDF export.

**Start here:** [`HANDOFF.md`](./HANDOFF.md) — full architecture and current status. There is no known open bug; the PDF-download bug described in §4 is fixed and click-verified.

## Quick start

1. Open `crosscontrol-offertbyggare.html` directly in a browser (double-click it).
2. Build a quote: add products, set customer/terms/currency, etc. Everything autosaves.
3. Get a PDF:
   - **"Download quote as PDF"** button — works, no Python needed. This is the normal route.
   - **"Print via browser"** — works, uses browser print.
   - **Export `.json`**, then `python3 generate_pdf.py quote-CC-2026-XXXX.json` — works, produces a pixel-exact branded PDF. Requires `cc-logo.svg`, `poppins-700-b64.txt`, and `poppins-800-b64.txt` in the same folder (`pip install weasyprint` first).

The app is fully self-contained — every library is inlined, so it needs no network.

See `README.txt` for the end-user instructions that ship with the tool, and `README.sv.txt` for the earlier Swedish version (which also covers refreshing the price list and updating the T&C document).

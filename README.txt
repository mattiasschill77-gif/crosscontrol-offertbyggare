CrossControl Quote Builder (Offertbyggare)
==========================================
Updated July 2026 with the changes you suggested, Zak.

WHAT'S IN THIS FOLDER
---------------------
crosscontrol-offertbyggare.html   The app. Double-click to open in a browser (Chrome or Edge).
generate_pdf.py                   Optional: makes a pixel-perfect PDF from an exported quote .json.
cc-logo.svg                       Logo. Must sit next to generate_pdf.py.
poppins-700-b64.txt               Heading font for generate_pdf.py. Must sit next to it.
poppins-800-b64.txt               Heading font for generate_pdf.py. Must sit next to it.
CrossControl_Standard_terms___conditions_2023.docx   The T&C doc to email with the quote.

Everything runs locally in your browser - no server, nothing to install to use it.
Keep all files together in one folder.

QUICK START
-----------
1. Double-click crosscontrol-offertbyggare.html.
2. Add products, set the customer, terms, currency, etc. Everything autosaves under a
   running quote number (CC-2026-0001, etc.). Use "Archive" to reopen past quotes.
3. Get a PDF the fast way: click "Download quote as PDF" - a vector PDF is created right
   in the browser, header/footer repeated on every page. No Python needed.
   (Exact path if you prefer: "Export quote data (.json)" then
    python3 generate_pdf.py quote-CC-2026-XXXX.json  - needs: pip install weasyprint)

WHAT'S NEW (your three suggestions)
-----------------------------------
1. Rename the quantity column.
   Left panel, under "Terms": a "Quantity column heading" field. Type or pick MOQ, EAU,
   Order Qty, etc. It changes the column header on the quote.

2. Custom volume-based tier matrix (per product).
   Every product now has a checkbox: "Custom volume tiers (price matrix)".
   - Leave it UNCHECKED for the normal List / Unit / Qty / Total row.
   - CHECK it and that product shows as its own price matrix, one column per tier
     (e.g. "Samples / MOQ 1-5" and "EAU 100-249 / MOQ 20"), like your V1200 quote.
   It pre-fills tier columns from the price list as a starting point - edit the labels,
   sub-labels and prices, add or delete columns. Prices are typed EXACTLY as they should
   appear (in the currency you've selected - no conversion), and matrix products are not
   rolled into the quote total. Put specific quantities in the note field if you like.

3. VAT / Tariff line.
   Under "Terms": a "VAT / Tariff note" field with presets - EU ("Prices are given
   excluding VAT") and US ("Prices are given without VAT or Tariff"). Shows as its own
   line under Terms on the quote.

Questions or anything off - let me know.
Mattias

CrossControl Quote Builder — Offertbyggare
==========================================

Uppdaterad enligt CrossControl grafiska profil (juli 2026): Poppins för
rubriker (Century Gothic-ersättning eftersom Decima Pro inte är
webbtillgängligt), Arial för brödtext, exakta varumärkesfärger
(orange #F7971C, grå #646363), och "less is more"-känslan från profilen
rakt igenom — webbappen, "Download PDF"-knappen och generate_pdf.py.

INNEHÅLL
--------
crosscontrol-offertbyggare.html   Webbappen. Dubbelklicka för att öppna i webbläsaren.
generate_pdf.py                   Genererar en exakt PDF från exporterad offert-JSON.
cc-logo.svg                       CrossControl-loggan. MÅSTE ligga bredvid generate_pdf.py.
poppins-700-b64.txt               Poppins Bold, för generate_pdf.py:s rubriker. MÅSTE ligga bredvid.
poppins-800-b64.txt               Poppins ExtraBold, för generate_pdf.py:s rubriker. MÅSTE ligga bredvid.
parse_pricelist.py                (Frivillig) Konverterar Excel-prislista lokalt.
xlsx_parser.js                    Redan inbakad i HTML-filen. Behövs inte separat.

VIKTIGT: Lägg generate_pdf.py, cc-logo.svg och de två poppins-*.txt-filerna
i SAMMA mapp. Saknas typsnittsfilerna faller PDF:en tillbaka på Arial för
rubriker (fungerar, men matchar inte varumärkesprofilen lika exakt).

ARBETSFLÖDE
-----------
1. Öppna crosscontrol-offertbyggare.html i webbläsaren (Chrome/Edge).
2. Bygg offerten: lägg till produkter, sätt kund, villkor, valuta osv.
   - Allt sparas automatiskt med ett löpnummer (CC-2026-0001 osv).
   - Klicka "Archive" för att hämta upp tidigare offerter.
3. Två sätt att få PDF:
   A) Snabbt: klicka "Download quote as PDF" — vektor-PDF direkt i webbläsaren,
      med upprepad header/footer på varje sida. Inget Python behövs.
   B) Exakt: klicka "Export quote data (.json)", lägg json-filen bredvid
      generate_pdf.py, kör:  python3 generate_pdf.py quote-CC-2026-0001.json
      PDF:en skapas i samma mapp.

KRAV FÖR generate_pdf.py
------------------------
  pip install weasyprint
  (cc-logo.svg och poppins-700-b64.txt / poppins-800-b64.txt måste finnas i samma mapp)

UPPDATERA PRISLISTAN
--------------------
Ladda upp ny Excel direkt i appen ("Upload updated price list"),
eller kör parse_pricelist.py lokalt.

STANDARD TERMS & CONDITIONS
---------------------------
T&C-dokumentet refereras automatiskt på varje offert och ska skickas
med som separat fil till kunden. Uppdatera vid behov via appen.

#!/usr/bin/env python3
"""
generate_pdf.py — CrossControl quote generator

Takes a JSON file exported from the quote builder (the "Export quote data" button)
and generates a polished PDF quote with CrossControl logo and branding.

Usage:
    python3 generate_pdf.py quote-CC-2026-1234.json
    python3 generate_pdf.py quote-CC-2026-1234.json -o my-quote.pdf

Requires: pip install weasyprint --break-system-packages
The logo (cc-logo.svg) must be in the same folder as this script,
or specified with --logo.
"""
import argparse
import json
import os
import sys
from weasyprint import HTML

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOGO = os.path.join(SCRIPT_DIR, 'cc-logo.svg')

# Brand colors (CrossControl graphical profile)
CC_ORANGE = '#F7971C'
CC_ORANGE_DARK = '#c9760f'
CC_GREY = '#646363'
INK = '#2b2b2a'
INK_DIM = '#646363'
LINE = '#e4e2dc'
BG_SOFT = '#f7f6f2'


def load_font_b64(filename):
    """Load a font file from the script directory and return its base64 content,
    for embedding via a data: URI in @font-face. Returns '' if the file is missing
    (the PDF will then fall back to Arial, per the brand guide's own fallback rule)."""
    path = os.path.join(SCRIPT_DIR, filename)
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return f.read().strip()
    return ''


POPPINS_700_B64 = load_font_b64('poppins-700-b64.txt')
POPPINS_800_B64 = load_font_b64('poppins-800-b64.txt')

OFFICES = {
    'alfta':    {'name': 'CrossControl', 'line1': 'Box 83, SE-822 22 Alfta', 'fax': '+46 271 75 76 89'},
    'vasteras': {'name': 'CrossControl', 'line1': 'Kopparlundsvägen 14, SE-721 30 Västerås', 'fax': '+46 21 40 32 10'},
    'uppsala':  {'name': 'CrossControl', 'line1': 'Fyrisborgsgatan 4, SE-754 50 Uppsala', 'fax': '+46 18 12 38 85'},
}
OFFICE_EMAIL = 'info@crosscontrol.com'
OFFICE_WEB = 'www.crosscontrol.com'
OFFICE_PHONE = '+46 271 75 76 00'


CURRENCY_RATES = {
    'EUR': {'symbol': '€', 'rate': 1, 'label': 'EUR (€)'},
    'USD': {'symbol': '$', 'rate': 1.08, 'label': 'USD ($)'},
    'SEK': {'symbol': 'kr', 'rate': 11.4, 'label': 'SEK (kr)'},
}


def fmt_money(eur_amount, currency='EUR', rate_override=None):
    conf = CURRENCY_RATES.get(currency, CURRENCY_RATES['EUR'])
    rate = rate_override if rate_override else conf['rate']
    converted = eur_amount * rate
    formatted = f"{converted:,.2f}"
    if currency == 'SEK':
        return f"{formatted} {conf['symbol']}"
    return f"{conf['symbol']}{formatted}"


def build_html(offer, logo_path):
    cust = offer.get('customer', {})
    cust_name = cust.get('name') or '[Customer name not specified]'
    cust_contact = cust.get('contact', '')
    cust_country = cust.get('country', '')

    office_key = offer.get('sender_office') or 'alfta'
    office = OFFICES.get(office_key, OFFICES['alfta'])
    header_address_html = f"{office['name']}<br>{office['line1']}, Sweden<br>"

    cust_line = f"To <b>{cust_name}</b>"
    if cust_contact:
        cust_line += f", attn: {cust_contact}"
    if cust_country:
        cust_line += f" ({cust_country})"

    currency = offer.get('currency', 'EUR')
    currency_rate = offer.get('currency_rate')  # explicit rate from the app, if provided

    rows_html = ""
    for line in offer['lines']:
        is_custom = line.get('is_custom', False)
        tier_tag = ''
        if is_custom:
            tier_tag = '<span class="tier-tag custom-tag">Custom item</span>'
        elif line.get('tier_label'):
            tier_tag = f'<span class="tier-tag">Tier {line["tier_label"]} units</span>'
        discount_tag = ''
        if line.get('extra_discount_pct', 0) > 0:
            discount_tag = f'<span class="discount-tag">+ {line["extra_discount_pct"]}% negotiated discount</span>'
        note_html = ''
        if line.get('note'):
            note_html = f'<div class="line-note">{line["note"]}</div>'
        list_price_cell = '<span class="strike">—</span>' if is_custom else f'<span class="strike">{fmt_money(line["list_price_eur"], currency, currency_rate)}</span>'
        part_number_html = f'<div class="psku">{line["part_number"]}</div>' if line.get('part_number') else ''
        rows_html += f"""
        <tr>
          <td>
            <div class="pname">{line['description'] or 'Untitled custom item'}</div>
            {part_number_html}
            {tier_tag}
            {discount_tag}
            {note_html}
          </td>
          <td class="num">{list_price_cell}</td>
          <td class="num finalprice">{fmt_money(line['final_unit_price_eur'], currency, currency_rate)}</td>
          <td class="num">{line['qty']}</td>
          <td class="num finalprice">{fmt_money(line['line_total_eur'], currency, currency_rate)}</td>
        </tr>"""

    appendix_html = ""
    for name in offer.get('appendices', []):
        appendix_html += f'<div class="appendix-note">📎 Appendix: {name}</div>'

    tc_filename = offer.get('tc_filename', 'CrossControl Standard Terms & Conditions 2023')
    tc_ref_html = f"""
      <div class="tc-reference">
        <div class="tc-ref-icon">§</div>
        <div class="tc-ref-text">
          This quote is subject to CrossControl&#x2019;s <strong>Standard Terms &amp; Conditions</strong>,
          enclosed as a separate document (<em>{tc_filename}</em>).
          By accepting this quote, the buyer agrees to be bound by these terms.
        </div>
      </div>"""

    signature_html = ""
    sig = offer.get('signature', {})
    if sig.get('include', True):
        signer_name = sig.get('signer_name', '') or '&nbsp;'
        signer_title = sig.get('signer_title', '') or '&nbsp;'
        cust_for_sig = cust_name if cust_name != '[Customer name not specified]' else 'Customer'
        signature_html = f"""
      <div class="signature-block">
        <div class="section-eyebrow">Acceptance</div>
        <div class="signature-grid">
          <div class="signature-col">
            <div class="sig-role">For CrossControl</div>
            <div class="signature-line"></div>
            <div class="sig-caption">Signature</div>
            <div class="sig-name">{signer_name}</div>
            <div class="sig-title">{signer_title}</div>
            <div class="signature-date-row">Date: <span class="date-line"></span></div>
          </div>
          <div class="signature-col">
            <div class="sig-role">For {cust_for_sig}</div>
            <div class="signature-line"></div>
            <div class="sig-caption">Signature</div>
            <div class="sig-name">&nbsp;</div>
            <div class="sig-title">&nbsp;</div>
            <div class="signature-date-row">Date: <span class="date-line"></span></div>
          </div>
        </div>
      </div>"""

    logo_svg = ""
    if logo_path and os.path.exists(logo_path):
        with open(logo_path, encoding='utf-8') as f:
            svg_raw = f.read()
        logo_svg = svg_raw.split('?>', 1)[1].strip() if '?>' in svg_raw else svg_raw

    terms = offer.get('terms', {})

    build_footer_html = f"""
  <div class="doc-footer">
    <div class="valid-line"><span class="valid">Valid until {offer['valid_until']}</span></div>
    <div class="footer-addresses">
      <div class="office-col {'active' if office_key == 'alfta' else ''}">
        <b>CrossControl (HQ)</b>
        Box 83, SE-822 22 Alfta<br>
        <span>Phone {OFFICE_PHONE}</span><br>
        <span>Fax {OFFICES['alfta']['fax']}</span>
      </div>
      <div class="office-col {'active' if office_key == 'vasteras' else ''}">
        <b>CrossControl Västerås</b>
        Kopparlundsvägen 14<br>
        SE-721 30 Västerås<br>
        <span>Fax {OFFICES['vasteras']['fax']}</span>
      </div>
      <div class="office-col {'active' if office_key == 'uppsala' else ''}">
        <b>CrossControl Uppsala</b>
        Fyrisborgsgatan 4<br>
        SE-754 50 Uppsala<br>
        <span>Fax {OFFICES['uppsala']['fax']}</span>
      </div>
    </div>
    <div class="footer-contact">{OFFICE_EMAIL} · {OFFICE_WEB}</div>
  </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><style>
  @font-face {{
    font-family: 'Poppins';
    font-weight: 700;
    font-style: normal;
    src: url(data:font/ttf;base64,{POPPINS_700_B64}) format('truetype');
  }}
  @font-face {{
    font-family: 'Poppins';
    font-weight: 800;
    font-style: normal;
    src: url(data:font/ttf;base64,{POPPINS_800_B64}) format('truetype');
  }}
  @page {{
    /* A4. Side margins 1.5cm. Top and bottom margins are enlarged to reserve room
       for the running header and the 3-column running footer, which both repeat
       on every page. */
    size: A4;
    margin: 3.0cm 1.5cm 3.4cm 1.5cm;
    @top-center {{
      content: element(pageheader);
      vertical-align: top;
      width: 100%;
    }}
    @bottom-center {{
      content: element(pagefooter);
      margin-bottom: 0;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, 'DejaVu Sans', sans-serif; margin:0; padding:0; color:{INK}; font-size:11.5px; }}
  .doc-header {{
    padding: 0 0 14px; display:flex; justify-content:space-between; align-items:flex-start;
    border-bottom: 4px solid {CC_ORANGE};
    position: running(pageheader);
    width: 100%;
  }}
  .doc-logo svg {{ height: 64px; width:auto; display:block; }}
  .doc-header-right {{ text-align:right; color:{INK_DIM}; font-size:10.5px; line-height:1.6; }}
  .doc-header-right .doc-id {{ color:{CC_ORANGE_DARK}; font-weight:700; font-size:10.5px; }}
  .doc-title-bar {{ padding: 8px 0 14px; }}
  .doc-title-bar h1 {{
    margin:0 0 6px; font-size:24px; font-weight:800; color:{INK};
    font-family:'Poppins',Arial,sans-serif; text-transform:uppercase; letter-spacing:0.01em;
  }}
  .doc-title-bar .meta {{ font-size:11.5px; color:{INK_DIM}; }}
  .doc-body {{ padding: 0; }}
  .section-eyebrow {{
    font-family:'Poppins',Arial,sans-serif;
    font-size:10px; text-transform:uppercase; letter-spacing:0.1em; color:{CC_ORANGE_DARK}; font-weight:700;
    margin-bottom:10px;
  }}
  table.quote-table {{ width:100%; border-collapse:collapse; margin-bottom:22px; font-size:11px; }}
  table.quote-table th {{
    text-align:left; font-size:9px; text-transform:uppercase; letter-spacing:0.5px;
    color:{INK_DIM}; padding:0 6px 8px; border-bottom:2px solid {INK};
  }}
  table.quote-table th.num, table.quote-table td.num {{ text-align:right; }}
  table.quote-table td {{ padding:12px 6px; border-bottom:1px solid {LINE}; vertical-align:top; }}
  .pname {{ font-weight:700; color:{INK}; font-size:12px; }}
  .psku {{ font-size:9.5px; color:{INK_DIM}; margin-top:1px; }}
  .tier-tag {{
    display:inline-block; font-size:9px; background:{BG_SOFT}; color:{INK_DIM};
    padding:2px 7px; border-radius:9px; margin-top:6px; margin-right:4px;
  }}
  .strike {{ text-decoration:line-through; color:#a8a39a; font-size:10px; }}
  .finalprice {{ font-weight:700; color:{INK}; }}
  .discount-tag {{ color:{CC_ORANGE_DARK}; font-size:9.5px; font-weight:700; display:block; margin-top:4px; }}
  .custom-tag {{ background:#fdf1de; color:{CC_ORANGE_DARK}; }}
  .line-note {{
    margin-top:6px; font-size:9.5px; color:{INK_DIM}; font-style:italic;
    background:{BG_SOFT}; padding:4px 7px; border-radius:2px; border-left:2px solid {LINE};
  }}
  .totals {{ display:flex; justify-content:flex-end; margin-bottom:26px; }}
  .totals-box {{ width:300px; font-size:11.5px; background:{BG_SOFT}; padding:12px 16px; }}
  .totals-row {{ display:flex; justify-content:space-between; padding:5px 0; color:{INK_DIM}; gap:16px; white-space:nowrap; }}
  .totals-row.final {{
    border-top:2px solid {INK}; margin-top:6px; padding-top:10px;
    font-family:'Poppins',Arial,sans-serif; text-transform:uppercase; letter-spacing:0.02em;
    font-size:12px; font-weight:700; color:{INK};
    white-space:nowrap;
  }}
  .totals-row.final span:last-child {{
    font-family:Arial,sans-serif; text-transform:none; letter-spacing:0;
    font-weight:700; color:{CC_ORANGE_DARK}; font-size:17px;
  }}
  .terms-grid {{ display:flex; flex-wrap:wrap; gap:16px; margin-bottom:22px; font-size:11px; color:{INK_DIM}; }}
  .term-item {{ width:45%; }}
  .term-item b {{ display:block; color:{INK}; font-size:10.5px; margin-bottom:2px; }}
  .appendix-note {{
    background:{BG_SOFT}; border-left:3px solid {CC_ORANGE}; padding:8px 12px; font-size:10.5px;
    color:{INK_DIM}; margin-bottom:8px;
  }}
  .tc-reference {{
    margin-top:20px; padding:10px 14px; background:{BG_SOFT};
    border-left:3px solid {CC_ORANGE}; border-radius:0;
    display:flex; gap:10px; align-items:flex-start; font-size:10px; color:{INK_DIM};
  }}
  .tc-ref-icon {{ font-size:16px; color:{CC_ORANGE_DARK}; font-weight:700; line-height:1.2; flex-shrink:0; }}
  .tc-ref-text {{ line-height:1.6; }}
  .signature-block {{ margin-top:28px; padding-top:20px; border-top:1px solid {LINE}; break-inside:avoid; }}
  .signature-grid {{ display:flex; gap:36px; margin-top:12px; }}
  .signature-col {{ width:48%; }}
  .signature-col .sig-role {{
    font-family:'Poppins',Arial,sans-serif;
    font-size:9.5px; text-transform:uppercase; letter-spacing:0.06em;
    color:{CC_ORANGE_DARK}; font-weight:700; margin-bottom:16px;
  }}
  .signature-line {{ border-bottom:1px solid {INK}; height:32px; margin-bottom:5px; }}
  .signature-col .sig-caption {{ font-size:9px; color:{INK_DIM}; margin-bottom:12px; }}
  .signature-col .sig-name {{ font-size:10.5px; font-weight:700; color:{INK}; margin-top:2px; }}
  .signature-col .sig-title {{ font-size:9.5px; color:{INK_DIM}; }}
  .signature-date-row {{ margin-top:14px; font-size:9px; color:{INK_DIM}; }}
  .signature-date-row .date-line {{ border-bottom:1px solid {INK_DIM}; width:90px; display:inline-block; height:12px; }}
  .doc-footer {{
    padding:8px 0 4px; border-top:1px solid {LINE};
    font-size:8.5px; color:{INK_DIM}; width:100%;
    position:running(pagefooter);
  }}
  .doc-footer .valid-line {{ text-align:center; font-size:9.5px; font-weight:700; margin-bottom:8px; }}
  .doc-footer .valid {{ color:{CC_ORANGE_DARK}; font-weight:700; }}
  .footer-addresses {{
    display:flex; gap:0; padding-top:6px; border-top:1px solid {LINE};
    justify-content:space-between; text-align:left;
  }}
  .footer-addresses .office-col {{ width:32%; line-height:1.5; }}
  .footer-addresses .office-col:nth-child(2) {{ text-align:center; }}
  .footer-addresses .office-col:last-child {{ text-align:right; }}
  .footer-addresses .office-col b {{ display:block; color:{INK}; font-size:9px; margin-bottom:1px; }}
  .footer-addresses .office-col.active {{ color:{CC_ORANGE_DARK}; }}
  .footer-addresses .office-col.active b {{ color:{CC_ORANGE_DARK}; }}
  .footer-addresses .office-col span {{ white-space:nowrap; }}
  .footer-contact {{ margin-top:5px; font-size:8.5px; color:{INK_DIM}; text-align:center; }}
</style></head>
<body>
  {build_footer_html}
  <div class="doc-header">
    <div class="doc-logo">{logo_svg}</div>
    <div class="doc-header-right">
      {header_address_html}
      <span class="doc-id">QUOTE #{offer['quote_id']}</span>
    </div>
  </div>

  <div class="doc-title-bar">
    <h1>Price Quote</h1>
    <div class="meta">{cust_line} &nbsp;·&nbsp; Issued {offer['issued_date']}</div>
  </div>

  <div class="doc-body">
    <div class="doc-content">
      <div class="section-eyebrow">Products &amp; Pricing</div>
      <table class="quote-table">
        <thead><tr>
          <th>Product</th><th class="num">List Price</th><th class="num">Unit Price</th>
          <th class="num">Qty</th><th class="num">Total</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>

      <div class="totals">
        <div class="totals-box">
          <div class="totals-row"><span>Subtotal</span><span>{fmt_money(offer['subtotal_eur'], currency, currency_rate)}</span></div>
          <div class="totals-row"><span>Shipping &amp; handling</span><span>Per terms</span></div>
          <div class="totals-row final"><span>Total (excl. VAT)</span><span>{fmt_money(offer['subtotal_eur'], currency, currency_rate)}</span></div>
        </div>
      </div>

      <div class="section-eyebrow">Terms</div>
      <div class="terms-grid">
        <div class="term-item"><b>Payment terms</b>{terms.get('payment','')}</div>
        <div class="term-item"><b>Delivery terms</b>{terms.get('delivery','')}</div>
        <div class="term-item"><b>Validity</b>This quote is valid until {offer['valid_until']}</div>
        <div class="term-item"><b>Currency</b>{CURRENCY_RATES.get(currency, CURRENCY_RATES['EUR'])['label']} — prices excl. VAT</div>
      </div>

      {appendix_html}

      {tc_ref_html}
    </div>

    {signature_html}
  </div>
</body></html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description='Generate a CrossControl quote as a PDF from exported JSON.')
    parser.add_argument('json_file', help='Path to the exported quote JSON file')
    parser.add_argument('-o', '--output', help='Path to output PDF (default: same name as JSON, .pdf)')
    parser.add_argument('--logo', default=DEFAULT_LOGO, help='Path to the CrossControl logo SVG')
    args = parser.parse_args()

    with open(args.json_file, encoding='utf-8') as f:
        offer = json.load(f)

    out_path = args.output or os.path.splitext(args.json_file)[0] + '.pdf'
    html_str = build_html(offer, args.logo)
    HTML(string=html_str, base_url=SCRIPT_DIR).write_pdf(out_path)
    print(f"PDF created: {out_path}")


if __name__ == '__main__':
    main()

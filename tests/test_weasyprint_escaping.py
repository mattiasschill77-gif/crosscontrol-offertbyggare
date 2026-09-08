"""Every user-controlled field must be escaped on the WeasyPrint path.

generate_pdf.py used to escape exactly ONE value - the quote number - and
interpolate everything else raw into the HTML it hands WeasyPrint: the customer
name, contact and country, every description, part number and line note, the
volume-tier labels, appendix names, the T&C file name, the signer's name and
title, the terms and the VAT note.

Archives move between colleagues and a quote's fields are free text, so this is
the same exposure the quote number had (HANDOFF.md §20.2).

These tests call build_html directly rather than rendering a PDF: the question is
what reaches the markup, and a rendered PDF cannot tell "<b>x</b> printed as text"
from "<b>x</b> interpreted as markup" - by then it is too late to see the
difference. One test does go all the way to the PDF, to prove the payload survives
as visible text.
"""
import importlib.util
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("generate_pdf", REPO / "generate_pdf.py")
generate_pdf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_pdf)

# Distinctive, and each one is a real injection shape rather than a generic string.
PAYLOAD = '<img src=x onerror=alert(1)>'
BOLD = '<b>BOLD</b>'


def _offer():
    """A quote with a payload in every free-text field at once."""
    return {
        'quote_id': f'CC-2026-0001{PAYLOAD}',
        'issued_date': f'26/08/2026{PAYLOAD}',
        'valid_until': f'24/11/2026{PAYLOAD}',
        'currency': 'EUR',
        'currency_rate': 1,
        'qty_heading': f'EAU{PAYLOAD}',
        'sender_office': 'alfta',
        'tc_filename': f'Terms{PAYLOAD}',
        'appendices': [f'Appendix{PAYLOAD}'],
        'subtotal_eur': 100.0,
        'show_list_price': True,
        'forecast_condition': True,
        'customer': {
            'name': f'Caudwell{PAYLOAD}',
            'contact': f'James{PAYLOAD}',
            'country': f'UK{PAYLOAD}',
            'address': f'Dock Road{PAYLOAD}',
        },
        'terms': {
            'payment': f'30 days{PAYLOAD}',
            'delivery': f'DAP{PAYLOAD}',
            'vat_note': f'excl VAT{PAYLOAD}',
        },
        'signature': {
            'include': True,
            'signer_name': f'Mattias{PAYLOAD}',
            'signer_title': f'KAM{PAYLOAD}',
        },
        'lines': [
            {
                'description': f'CCpilot VI{PAYLOAD}',
                'part_number': f'C000 144-05{PAYLOAD}',
                'note': f'lead time{PAYLOAD}',
                'tier_label': f'100-249{PAYLOAD}',
                'qty': 15,
                'extra_discount_pct': 12,
                'list_price_eur': 526.76,
                'final_unit_price_eur': 256.96,
                'line_total_eur': 3854.40,
            },
            {
                'description': f'Matrix product{PAYLOAD}',
                'part_number': f'S020 144-05{PAYLOAD}',
                'note': f'matrix note{PAYLOAD}',
                'custom_tiers': True,
                'qty': 1,
                'list_price_eur': 0,
                'final_unit_price_eur': 0,
                'line_total_eur': 0,
                'volume_tiers': [
                    {'label': f'1-99{PAYLOAD}', 'sublabel': f'MOQ 15{PAYLOAD}', 'price': 100.0},
                ],
            },
        ],
    }


@pytest.fixture(scope="module")
def rendered_html():
    return generate_pdf.build_html(_offer(), str(REPO / "cc-logo.svg"))


def test_no_payload_survives_as_live_markup(rendered_html):
    """The whole point: not one copy of the tag reaches the document unescaped."""
    assert PAYLOAD not in rendered_html, (
        "a raw <img src=x onerror=...> reached the HTML handed to WeasyPrint"
    )


def test_every_field_is_present_but_escaped(rendered_html):
    """Non-vacuous: the payload must be THERE, as escaped text, in every field.

    Without this a build_html that silently dropped all the fields would pass the
    test above.
    """
    escaped = "&lt;img src=x onerror=alert(1)&gt;"
    count = rendered_html.count(escaped)
    # customer name x2 (bill-to + signature), contact, country, address, qty heading,
    # quote id, issued, valid_until x2, tc filename, appendix, payment, delivery,
    # vat note, signer name, signer title, and the two lines' fields
    assert count >= 18, (
        f"expected the escaped payload in at least 18 places, found {count} - "
        "either a field is being dropped or one is still raw"
    )


def test_angle_brackets_are_neutralised_everywhere(rendered_html):
    """No stray unescaped '<b>' anywhere - a narrower shape that a naive
    replace('<img', ...) style fix would miss."""
    off = _offer()
    for key in ('name', 'contact', 'country', 'address'):
        off['customer'][key] = BOLD
    off['lines'][0]['description'] = BOLD
    off['lines'][0]['note'] = BOLD
    off['terms']['payment'] = BOLD
    html = generate_pdf.build_html(off, str(REPO / "cc-logo.svg"))
    assert "<b>BOLD</b>" not in html
    assert "&lt;b&gt;BOLD&lt;/b&gt;" in html


def test_the_document_still_renders_normal_text_unharmed():
    """Escaping must not mangle ordinary content, and the &nbsp; fallbacks in the
    signature block must survive an EMPTY signer rather than becoming visible text."""
    off = _offer()
    off['customer'] = {'name': 'Caudwell Marine Ltd', 'contact': 'James Caudwell',
                       'country': 'UK', 'address': 'Dock Road\nBirkenhead'}
    off['signature'] = {'include': True, 'signer_name': '', 'signer_title': ''}
    off['lines'] = [dict(off['lines'][0], description='CCpilot VI',
                         part_number='C000 144-05', note='', tier_label='100-249')]
    html = generate_pdf.build_html(off, str(REPO / "cc-logo.svg"))
    assert 'Caudwell Marine Ltd' in html
    assert 'CCpilot VI' in html
    assert 'C000 144-05' in html
    # the empty signer falls back to a real non-breaking space, not "&amp;nbsp;"
    assert '&amp;nbsp;' not in html, "an HTML fallback was escaped into visible text"


def test_an_ampersand_in_a_real_name_is_escaped_not_broken(rendered_html):
    """'Wilson & Sons' is a normal customer name, not an attack. It must print
    as typed and be encoded correctly in the markup."""
    off = _offer()
    off['customer'] = {'name': 'Wilson & Sons Ltd', 'contact': '', 'country': '', 'address': ''}
    html = generate_pdf.build_html(off, str(REPO / "cc-logo.svg"))
    assert 'Wilson &amp; Sons Ltd' in html
    assert 'Wilson & Sons Ltd' not in html

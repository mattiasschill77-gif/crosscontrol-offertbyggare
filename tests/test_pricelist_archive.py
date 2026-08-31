"""The price list archive (v1.7.2).

The store `cc_pricelist_archive_v1` existed from 2026-08-17 and nothing ever read
it back: every reference to PL_ARCHIVE_KEY lived inside plSaveToArchive. "Save to
archive" toasted a number and put the price list somewhere unreachable forever.

What these guard, worst consequence first:

1. Cost never reaches the customer. mkByPart is in the archive record now, so a
   reopened list restores the KAM's typed manufacturing cost - which means this
   feature is the newest way that number could leak into a customer document.
2. A restored list is priced the way it was saved. basisColumn was missing from
   the record, so a reopen silently fell back to List price: right-looking
   document, wrong prices.
3. One customer's price list is never saved over another's.
4. The two archives do not bleed into each other's tab.
5. A record written before 1.7.2 still opens.
"""
import json
import re
import zipfile

from playwright.sync_api import sync_playwright

from harness import app_page, page_texts, serve

MK_SEK = 4711.25          # distinctive: a real cost, findable as a substring
MK_NEEDLE = "4711"


def _digits_run(text):
    """Strip the separators a number picks up on its way to a screen, a PDF or a
    cell, so the search is for the number and not for one rendering of it. The
    margin card prints 4,711.25; a PDF may wrap it as 4 711,25; the workbook
    stores it raw. All three must reduce to the same digit run."""
    return re.sub(r"[\s,  ']", "", text)


def _build_and_save(page, customer="Caudwell Marine Ltd", n=5, with_cost=True):
    """Build a price list on the real tab and save it. Returns its archive id."""
    page.evaluate("switchView('pricelist')")
    page.fill("#plCustName", customer)
    page.fill("#plRevision", "Rev. 2026-C")
    page.evaluate(
        """(args) => {
            const parts = plSections(PRICE_DATA)[0].products.slice(0, args.n).map(p => p.part_number);
            parts.forEach(p => PL.selection[p] = true);
            const tiers = plTierLabels().map(t => t.label);
            PL.basisColumn = tiers[0] || 'list';
            plEl('plBasisColumn').value = PL.basisColumn;
            if (args.withCost) PL.mkByPart[parts[0]] = args.mk;
            plRenderAll();
        }""",
        {"n": n, "withCost": with_cost, "mk": MK_SEK},
    )
    page.click("#plSaveBtn")
    page.wait_for_timeout(300)
    return page.evaluate("PL_ID")


def test_cost_never_reaches_the_price_list_pdf_or_the_excel(tmp_path):
    """The hard rule. Asserted on the decompressed PDF text and the workbook XML,
    not on the screen - and the probe is proven non-vacuous first by confirming
    the cost really is loaded and really is rendered in the internal card."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            pl_id = _build_and_save(page)
            # Wipe, reopen from the archive: the cost now comes from the record,
            # which is the new path this test exists for.
            page.evaluate("PL.mkByPart = {}; plRenderAll();")
            page.evaluate(f"plOpenFromArchive({pl_id!r})")
            page.wait_for_timeout(400)

            restored = page.evaluate("Object.values(PL.mkByPart)[0]")
            margin_card = page.inner_text("#plMarginBody")

            with page.expect_download(timeout=30000) as dl:
                page.click("#plDownloadPdfBtn")
            pdf = tmp_path / "pricelist.pdf"
            dl.value.save_as(str(pdf))

            with page.expect_download(timeout=30000) as dlx:
                page.click("#plDownloadXlsxBtn")
            xlsx = tmp_path / "pricelist.xlsx"
            dlx.value.save_as(str(xlsx))

    # The probe can fail: the cost is genuinely in play on the internal card.
    assert restored == MK_SEK, "the cost never came back, so the search below proves nothing"
    assert MK_NEEDLE in _digits_run(margin_card), (
        f"the cost is not on the internal margin card, so this test is vacuous: {margin_card[:200]}"
    )

    pdf_text = " ".join(page_texts(pdf))
    assert MK_NEEDLE not in _digits_run(pdf_text), "manufacturing cost reached the price list PDF"

    with zipfile.ZipFile(xlsx) as z:
        book = " ".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".xml"))
    assert MK_NEEDLE not in _digits_run(book), "manufacturing cost reached the Excel export"


def test_a_reopened_price_list_is_priced_the_way_it_was_saved():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            pl_id = _build_and_save(page)
            saved_basis = page.evaluate("PL.basisColumn")
            assert saved_basis != "list", "pick a non-default basis or this proves nothing"

            page.evaluate(
                "PL.selection={}; PL.mkByPart={}; PL.basisColumn='list';"
                "plEl('plBasisColumn').value='list'; plEl('plCustName').value='';"
                "PL_ID=null; plRenderAll();"
            )
            page.evaluate(f"plOpenFromArchive({pl_id!r})")
            page.wait_for_timeout(400)
            got = page.evaluate(
                "({basis: PL.basisColumn, select: plEl('plBasisColumn').value,"
                " cust: plEl('plCustName').value, rev: plEl('plRevision').value,"
                " sel: Object.keys(PL.selection).length, mk: Object.values(PL.mkByPart)[0]})"
            )
    assert got["basis"] == saved_basis, "the calculation base silently reverted to List price"
    assert got["select"] == saved_basis
    assert got["cust"] == "Caudwell Marine Ltd"
    assert got["rev"] == "Rev. 2026-C"
    assert got["sel"] == 5
    assert got["mk"] == MK_SEK


def test_saving_a_bound_list_updates_it_instead_of_piling_up_duplicates():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            first = _build_and_save(page)
            page.click("#plSaveBtn")
            page.click("#plSaveBtn")
            page.wait_for_timeout(300)
            ids = page.evaluate("Object.keys(plLoadArchive())")
    assert ids == [first], f"three saves of one list produced {ids}"


def test_a_different_customer_never_overwrites_the_first_ones_list():
    """The one real loss case: reuse an open list for someone else and save."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            first = _build_and_save(page, customer="Caudwell Marine Ltd")
            page.fill("#plCustName", "Someone Else AB")
            page.wait_for_timeout(150)
            assert page.evaluate("PL_ID") is None, "the binding was not released on rename"
            page.click("#plSaveBtn")
            page.wait_for_timeout(300)
            store = page.evaluate("plLoadArchive()")
    assert store[first]["meta"]["customerName"] == "Caudwell Marine Ltd", (
        "the second customer's list was saved over the first"
    )
    assert len(store) == 2


def test_the_two_archives_do_not_bleed_into_each_other():
    """.archive-list is display:flex, and an author display rule beats the UA
    stylesheet's [hidden]{display:none} - so the quote list stayed on screen
    under the Price lists tab. Every scripted check was green; a screenshot
    caught it."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            _build_and_save(page)
            page.evaluate("addProductToCart(FLAT_PRODUCTS[0].part_number)")
            page.wait_for_timeout(500)
            page.click("#openArchiveBtn")
            page.click("#archiveTabPricelists")
            page.wait_for_timeout(200)
            on_pl = page.evaluate(
                "({quotes: getComputedStyle(document.getElementById('archiveList')).display,"
                "  pls: getComputedStyle(document.getElementById('plArchiveList')).display})"
            )
            page.click("#archiveTabQuotes")
            page.wait_for_timeout(200)
            on_quotes = page.evaluate(
                "({quotes: getComputedStyle(document.getElementById('archiveList')).display,"
                "  pls: getComputedStyle(document.getElementById('plArchiveList')).display})"
            )
    assert on_pl["quotes"] == "none", "a quote was showing under the Price lists tab"
    assert on_pl["pls"] != "none"
    assert on_quotes["pls"] == "none", "a price list was showing under the Quotes tab"
    assert on_quotes["quotes"] != "none"


def test_a_saved_price_list_can_be_deleted():
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            pl_id = _build_and_save(page)
            page.click("#openArchiveBtn")
            page.click("#archiveTabPricelists")
            page.click(f".archive-delete-btn[data-pl-id='{pl_id}']")
            page.wait_for_timeout(300)
            store = page.evaluate("plLoadArchive()")
            bound = page.evaluate("PL_ID")
    assert pl_id not in store
    assert bound is None, "the deleted list is still bound, so the next save would resurrect it"


def test_a_record_written_before_1_7_2_still_opens():
    """No basisColumn, no mkByPart. It must default, not throw."""
    legacy = {
        "id": "PL-2026-0009",
        "app_version": "1.7.1",
        "saved_at": "2026-08-20T10:00:00.000Z",
        "meta": {"customerName": "Legacy Customer", "revision": "Rev. 2026-A", "currency": "EUR"},
        "selection": {},
        "familyDiscounts": {},
        "moqByPart": {},
        "statusByPart": {},
        "defaultDiscountPct": "7",
    }
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            page.evaluate(
                "(rec) => plSaveArchiveStore(Object.assign(plLoadArchive(), {[rec.id]: rec}))",
                legacy,
            )
            page.evaluate("plOpenFromArchive('PL-2026-0009')")
            page.wait_for_timeout(300)
            got = page.evaluate(
                "({basis: PL.basisColumn, cust: plEl('plCustName').value,"
                " mk: JSON.stringify(PL.mkByPart), disc: plEl('plDefaultDiscount').value})"
            )
    assert not alerts, f"opening a pre-1.7.2 record alerted: {alerts}"
    assert got["basis"] == "list"
    assert got["cust"] == "Legacy Customer"
    assert got["mk"] == "{}"
    assert got["disc"] == "7"


def test_the_backup_file_carries_price_lists(tmp_path):
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            pl_id = _build_and_save(page)
            page.click("#openArchiveBtn")
            with page.expect_download(timeout=30000) as dl:
                page.click("#exportArchiveBtn")
            out = tmp_path / "archive.json"
            dl.value.save_as(str(out))
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["format_version"] == 2
    assert pl_id in payload["pricelists"]
    assert "quotes" in payload, "the quotes must still be there"


def test_a_colliding_price_list_is_kept_alongside_and_never_overwrites(tmp_path):
    """Every machine starts its series at PL-YYYY-0001, so the same number holds
    different lists on two desks - exactly the quote collision, and it must be
    survivable in exactly the same way."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, _alerts):
            mine = _build_and_save(page, customer="My Own Customer")
            theirs = {
                "format": "cc-quote-archive",
                "format_version": 2,
                "exported_at": "2026-08-31T00:00:00.000Z",
                "app_version": "1.7.2",
                "quotes": {},
                "pricelists": {
                    mine: {
                        "id": mine,
                        "saved_at": "2026-08-01T00:00:00.000Z",
                        "meta": {"customerName": "Their Different Customer"},
                        "selection": {},
                    }
                },
            }
            path = tmp_path / "theirs.json"
            path.write_text(json.dumps(theirs), encoding="utf-8")
            page.set_input_files("#importArchiveInput", str(path))
            page.wait_for_timeout(800)
            store = page.evaluate("plLoadArchive()")
    assert store[mine]["meta"]["customerName"] == "My Own Customer", (
        "the imported price list overwrote a local one"
    )
    kept = [k for k, v in store.items() if v.get("meta", {}).get("customerName") == "Their Different Customer"]
    assert kept, "the imported price list was dropped instead of kept alongside"
    assert kept[0] != mine
    assert store[kept[0]]["id"] == kept[0], "the renumbered record kept its old id inside"


def test_a_quote_only_backup_file_still_imports(tmp_path):
    """A v1 file has no `pricelists` key at all. That is not an error."""
    with serve() as url, sync_playwright() as p:
        with app_page(p, url) as (page, alerts):
            legacy = {
                "format": "cc-quote-archive",
                "format_version": 1,
                "exported_at": "2026-08-26T00:00:00.000Z",
                "app_version": "1.7.1",
                "quotes": {"CC-2019-0042": {"quote_id": "CC-2019-0042", "customer_name": "Legacy"}},
            }
            path = tmp_path / "v1.json"
            path.write_text(json.dumps(legacy), encoding="utf-8")
            page.set_input_files("#importArchiveInput", str(path))
            page.wait_for_timeout(800)
            quotes = page.evaluate("loadArchive()")
            pls = page.evaluate("plLoadArchive()")
    assert quotes["CC-2019-0042"]["customer_name"] == "Legacy"
    assert pls == {}
    assert not [a for a in alerts if "could not" in a.lower()], f"a v1 file was refused: {alerts}"

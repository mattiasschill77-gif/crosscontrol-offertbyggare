// ===== IN-BROWSER EXCEL PARSER (mirrors parse_pricelist.py logic) =====
// Parses an uploaded "TG_kalkyl_och_valuta_updated.xlsx"-shaped workbook into
// the same { meta, groups, accessories } structure as PRICE_DATA.

const TIER_COLS = ['E', 'F', 'G', 'H'];
const COL_IDX = { A:1,B:2,C:3,D:4,E:5,F:6,G:7,H:8,I:9,J:10 };
const SKIP_LABELS = new Set(['Part number', 'Part No.', 'MOQ', 'List price', 'Accessories', 'Cables']);

function xlsxCell(sheet, row, colLetter) {
  const colIdx = COL_IDX[colLetter];
  const addr = XLSX.utils.encode_cell({ r: row - 1, c: colIdx - 1 });
  const cell = sheet[addr];
  return cell ? cell.v : undefined;
}

function sheetMaxRow(sheet) {
  const ref = sheet['!ref'];
  if (!ref) return 0;
  const range = XLSX.utils.decode_range(ref);
  return range.e.r + 1; // 1-indexed
}

function parsePriceListWorkbook(workbook) {
  const ws = workbook.Sheets['Aktuell prislista'];
  if (!ws) throw new Error('Sheet "Aktuell prislista" not found in this workbook.');
  const maxRow = sheetMaxRow(ws);

  // ---- Pass 1: find block boundaries ----
  const blocks = []; // { startRow, kind: 'group'|'accessory', name }
  for (let r = 1; r <= maxRow; r++) {
    const a = xlsxCell(ws, r, 'A');
    if (!(a && typeof a === 'string')) continue;
    const aStripped = a.trim();
    if (aStripped === 'Accessories' || aStripped === 'Cables') {
      blocks.push({ startRow: r, kind: 'accessory', name: aStripped });
      continue;
    }
    if (SKIP_LABELS.has(aStripped)) continue;
    const cThis = xlsxCell(ws, r, 'C');
    const cNext = xlsxCell(ws, r + 1, 'C');
    if (cThis === 'List price' || cNext === 'List price') {
      blocks.push({ startRow: r, kind: 'group', name: aStripped });
    }
  }
  blocks.push({ startRow: maxRow + 1, kind: 'end', name: null });

  const groups = [];
  const accessorySections = [];

  for (let i = 0; i < blocks.length - 1; i++) {
    const { startRow, kind, name } = blocks[i];
    const endRow = blocks[i + 1].startRow - 1;

    if (kind === 'group') {
      let tierLabels = TIER_COLS.map(c => xlsxCell(ws, startRow, c));
      let headerRow = startRow;
      if (tierLabels.every(t => t === undefined || t === null)) {
        headerRow = startRow + 1;
        tierLabels = TIER_COLS.map(c => xlsxCell(ws, headerRow, c));
      }

      let moqRow = null;
      for (let look = startRow; look <= Math.min(startRow + 3, endRow); look++) {
        if (xlsxCell(ws, look, 'D') === 'MOQ') { moqRow = look; break; }
      }
      const tierMoqs = TIER_COLS.map(c => moqRow ? xlsxCell(ws, moqRow, c) : null);
      const dataStart = moqRow ? moqRow + 1 : headerRow + 1;

      const products = [];
      for (let rr = dataStart; rr <= endRow; rr++) {
        const pn = xlsxCell(ws, rr, 'A');
        const desc = xlsxCell(ws, rr, 'B');
        const listPrice = xlsxCell(ws, rr, 'C');
        if (!pn || (typeof pn === 'string' && SKIP_LABELS.has(pn.trim()))) continue;
        if (listPrice === undefined || listPrice === null) continue;

        const tiers = {};
        tierLabels.forEach((label, idx) => {
          const col = TIER_COLS[idx];
          const val = xlsxCell(ws, rr, col);
          if (label && val !== undefined && val !== null) {
            tiers[String(label)] = { moq: tierMoqs[idx], price_eur: Math.round(parseFloat(val) * 100) / 100 };
          }
        });
        const negMargin = xlsxCell(ws, rr, 'I');
        const lifecycle = xlsxCell(ws, rr, 'J');
        products.push({
          part_number: String(pn).trim(),
          description: desc ? String(desc).trim() : '',
          list_price_eur: Math.round(parseFloat(listPrice) * 100) / 100,
          tiers,
          negotiation_margin: typeof negMargin === 'number' ? negMargin : null,
          lifecycle_comment: lifecycle || null,
          mk_sek: null,
        });
      }
      if (products.length) groups.push({ group: name, products });

    } else if (kind === 'accessory') {
      let hr = startRow + 1;
      while (hr <= endRow) {
        const v = xlsxCell(ws, hr, 'A');
        if (v === 'Part No.' || v === 'Part number') break;
        hr++;
      }
      const items = [];
      for (let rr = hr + 1; rr <= endRow; rr++) {
        const pn = xlsxCell(ws, rr, 'A');
        const desc = xlsxCell(ws, rr, 'B');
        const price = xlsxCell(ws, rr, 'C');
        if (!pn || price === undefined || price === null) continue;
        items.push({
          part_number: String(pn).trim(),
          description: desc ? String(desc).trim() : '',
          price_eur: Math.round(parseFloat(price) * 100) / 100,
        });
      }
      if (items.length) accessorySections.push({ section: name, items });
    }
  }

  // ---- TG-kalkyl seed ----
  let tgAssumptions = { target_tg: 0.35, vat: 0.25, fx_sek_eur: 0.0949, note: 'Defaults used — TG-kalkyl sheet not found or incomplete in uploaded file.' };
  const tgSheet = workbook.Sheets['TG-kalkyl'];
  if (tgSheet) {
    const get = (addr) => tgSheet[addr] ? tgSheet[addr].v : undefined;
    const seedPartNumber = get('A2');
    const seedMkSek = get('B6');
    const seedTargetTg = get('B7');
    const seedVat = get('B8');
    const seedFx = get('C9');
    tgAssumptions = {
      target_tg: typeof seedTargetTg === 'number' ? seedTargetTg : 0.35,
      vat: typeof seedVat === 'number' ? seedVat : 0.25,
      fx_sek_eur: typeof seedFx === 'number' ? seedFx : 0.0949,
      note: 'MK (manufacturing cost, SEK) currently only known for one seed article. Margin display should only appear when MK is present on a product (from the price list or entered manually).',
    };
    if (seedPartNumber && typeof seedMkSek === 'number') {
      const seedPn = String(seedPartNumber).trim();
      groups.forEach(g => g.products.forEach(p => {
        if (p.part_number === seedPn) p.mk_sek = Math.round(seedMkSek * 100) / 100;
      }));
    }
  }

  return {
    meta: {
      currency: 'EUR',
      source_file: 'uploaded',
      tg_assumptions: tgAssumptions,
    },
    groups,
    accessories: accessorySections,
  };
}

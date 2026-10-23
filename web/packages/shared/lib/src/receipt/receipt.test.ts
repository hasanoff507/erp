import { describe, expect, it } from "vitest";

import type { Money } from "#/money/index.ts";

import {
  blockLines,
  canEncodeCp866,
  cp866Byte,
  encodeCp866,
  encodeEscPos,
  layoutReceipt,
  needsRaster,
  normalizeReceiptText,
  qrCommand,
  rasterCommand,
  type Rasterizer,
  type RasterSegment,
  type ReceiptDoc,
  renderReceiptHtml,
  rgbaToMono,
  TEST_RECEIPT_TEXT,
  testReceiptDoc,
  wrapText,
} from "./index.ts";

const m = (v: string) => v as Money;

/** Index of a byte sequence inside an array (−1 if absent). */
function indexOf(haystack: Uint8Array, needle: readonly number[], from = 0): number {
  outer: for (let i = from; i <= haystack.length - needle.length; i += 1) {
    for (let j = 0; j < needle.length; j += 1) if (haystack[i + j] !== needle[j]) continue outer;
    return i;
  }
  return -1;
}

const fakeRasterizer = (): Rasterizer & { calls: number; segments: RasterSegment[] } => {
  const r = {
    calls: 0,
    segments: [] as RasterSegment[],
    rasterize: (segment: RasterSegment, width: number) => {
      r.calls += 1;
      r.segments.push(segment);
      // 2 rows: first row all black, second white
      const rowBytes = width / 8;
      const data = new Uint8Array(rowBytes * 2);
      data.fill(0xff, 0, rowBytes);
      return { width, height: 2, data };
    },
  };
  return r;
};

const SALE: ReceiptDoc = {
  kind: "sale",
  store: {
    name: "Do'kon",
    address: "Toshkent",
    phone: "+998 71 200 00 00",
    stir: "123456789",
    branchName: "Chilonzor-3",
  },
  number: "K-01-2026-000154",
  issuedAt: "2026-10-12T22:41:00",
  cashierName: "Dilnoza",
  shiftNo: 7,
  registerNo: "RG-1",
  receiptSeq: 154,
  lines: [
    {
      name: 'Non "Bekhurmon"',
      nameRu: "Хлеб",
      qty: "2.000",
      qtyKind: "integer",
      unitPrice: "12000.00",
      unitLabel: "dona",
      total: m("24000.00"),
      mxik: "10202001001000000",
      barcode: "4780000123456",
      vatRate: "12",
      vat: m("2571.43"),
    },
    {
      name: "Guruch",
      nameRu: null,
      qty: "1.250",
      qtyKind: "fractional",
      unitPrice: "18000.00",
      unitLabel: "kg",
      discount: m("2000.00"),
      total: m("20500.00"),
      vatRate: null,
      vat: m("0.00"),
      vatExemptCode: "10001",
      markingCodes: ["0104780000123456215abc"],
    },
  ],
  totals: { total: m("44500.00"), discount: m("2000.00"), vat: [{ rate: "12", amount: m("2571.43") }] },
  payments: {
    form: "mixed",
    items: [
      { method: "cash", amount: m("20000.00") },
      {
        method: "card",
        amount: m("24500.00"),
        card: {
          entryMode: "integrated",
          cardType: "personal",
          cardMask: "8600****1234",
          rrn: "612345678901",
          approvalCode: "A1B2C3",
          scheme: "uzcard",
          tid: "12345678",
        },
      },
    ],
    received: m("50000.00"),
    change: m("30000.00"),
  },
  fiscal: {
    fmTerminalId: "ZZ000000000000",
    fmReceiptSeq: 77,
    fiscalSign: "123456789012",
    qrUrl: "https://ofd.soliq.uz/check?t=ZZ000000000000&r=77&c=20261012224100&s=123456789012",
  },
};

describe("CP866 (24 §6.1, ESC t 17)", () => {
  it("maps Russian Cyrillic, Ў/ў and №; Қ/Ғ/Ҳ and ʻ are not in the code page", () => {
    expect(cp866Byte("А")).toBe(0x80);
    expect(cp866Byte("Я")).toBe(0x9f);
    expect(cp866Byte("а")).toBe(0xa0);
    expect(cp866Byte("п")).toBe(0xaf);
    expect(cp866Byte("р")).toBe(0xe0);
    expect(cp866Byte("я")).toBe(0xef);
    expect(cp866Byte("Ё")).toBe(0xf0);
    expect(cp866Byte("Ў")).toBe(0xf6);
    expect(cp866Byte("ў")).toBe(0xf7);
    expect(cp866Byte("№")).toBe(0xfc);
    for (const ch of ["Қ", "қ", "Ғ", "ғ", "Ҳ", "ҳ", "ʻ"]) expect(cp866Byte(ch)).toBeNull();
    expect(Array.from(encodeCp866("Итого: 5"))).toEqual([0x88, 0xe2, 0xae, 0xa3, 0xae, 0x3a, 0x20, 0x35]);
  });

  it("normalisation: ʻ ʼ → ', NBSP → space, − → -", () => {
    expect(normalizeReceiptText("Oʻzbekiston gʼalla 1 000 − «a»")).toBe("O'zbekiston g'alla 1 000 - \"a\"");
    expect(canEncodeCp866(normalizeReceiptText("Oʻzbekiston"))).toBe(true);
  });
});

describe("layout (08 §13.1, 18 §4.9)", () => {
  it("wraps and right-aligns amounts at 32 (58 mm) / 48 (80 mm) columns", () => {
    expect(wrapText("aaa bbb ccc", 7)).toEqual(["aaa bbb", "ccc"]);
    expect(wrapText("abcdefghij", 4)).toEqual(["abcd", "efgh", "ij"]);
    const line = blockLines(
      { type: "text", left: "Jami / Итого:", right: "69 000 so'm", align: "left", size: "normal" },
      32,
    );
    expect(line).toEqual(["Jami / Итого:        69 000 so'm"]);
    expect(line[0]).toHaveLength(32);
  });

  it("two languages per line, card requisites only for integrated payments, fiscal block with QR", () => {
    const layout = layoutReceipt(SALE, { paperWidth: 80 });
    const texts = layout.blocks.flatMap((b) => (b.type === "text" ? [b.left, b.right ?? ""] : []));
    expect(texts).toContain('1. Non "Bekhurmon" / Хлеб');
    expect(texts).toContain("2. Guruch");
    expect(texts).toContain("   MXIK 10202001001000000 · dona · 4780000123456 · QQS 12%: 2 571,43");
    expect(texts).toContain("   kg · QQSsiz (imtiyoz: 10001)");
    expect(texts).toContain("   Markirovka: 0104780000123456215abc");
    expect(texts).toContain("   Karta turi / Тип карты: shaxsiy / личная");
    expect(texts).toContain("   8600****1234 · RRN 612345678901");
    expect(texts).toContain("Aralash / Смешанная");
    expect(texts).toContain("FM: ZZ000000000000");
    expect(layout.blocks.some((b) => b.type === "qr")).toBe(true);
    // 58 mm: Russian name on its own (small) line
    const narrow = layoutReceipt(SALE, { paperWidth: 58 });
    expect(narrow.blocks.some((b) => b.type === "text" && b.left === "   Хлеб" && b.size === "small")).toBe(
      true,
    );
    expect(narrow.columns).toBe(32);
    // manual (terminal-less) card: payment form only (26 #178)
    const manual = layoutReceipt(
      {
        ...SALE,
        payments: {
          form: "card",
          items: [{ method: "card", amount: m("44500.00"), card: { entryMode: "manual" } }],
        },
      },
      { paperWidth: 58 },
    );
    const manualTexts = manual.blocks.flatMap((b) => (b.type === "text" ? [b.left] : []));
    expect(manualTexts.join("|")).not.toMatch(/RRN|8600|Karta turi/);
    expect(manualTexts).toContain("Bank kartalari / Банковские карты");
  });

  it("pending fiscal, reprint copy mark, credit receipt without QR", () => {
    const pending = layoutReceipt({ ...SALE, fiscal: null, copy: true }, { paperWidth: 58 });
    const t = pending.blocks.flatMap((b) => (b.type === "text" ? [b.left] : []));
    expect(t).toContain("Fiskal belgi kutilmoqda / Фискальный признак ожидается");
    expect(t).toContain("NUSXA / КОПИЯ");
    const noQr = layoutReceipt({ ...SALE, noQr: true }, { paperWidth: 58 });
    expect(noQr.blocks.some((b) => b.type === "qr")).toBe(false);
  });
});

describe("ESC/POS bytes (QT-M01-22 unit part)", () => {
  it("test_qt_m01_22_test_receipt_raster_auto: Қ/Ғ/Ҳ switch auto mode to raster (GS v 0), cp866 selected", () => {
    const layout = layoutReceipt(
      testReceiptDoc({ at: "2026-10-16T10:00:00", transport: "webserial", paperWidth: 58 }),
      {
        paperWidth: 58,
      },
    );
    expect(layout.blocks.some((b) => b.type === "text" && b.left === TEST_RECEIPT_TEXT)).toBe(true);
    expect(needsRaster(layout)).toBe(true);
    const rasterizer = fakeRasterizer();
    const { bytes, mode } = encodeEscPos(layout, { renderMode: "auto", rasterizer });
    expect(mode).toBe("raster");
    expect(Array.from(bytes.slice(0, 5))).toEqual([0x1b, 0x40, 0x1b, 0x74, 17]); // ESC @, ESC t 17
    // GS v 0 m=0, xL=48 (384 dots / 8), xH=0, yL=2, yH=0, then the bitmap rows
    const at = indexOf(bytes, [0x1d, 0x76, 0x30, 0x00, 48, 0, 2, 0]);
    expect(at).toBeGreaterThan(0);
    expect(Array.from(bytes.slice(at + 8, at + 8 + 49))).toEqual([...new Array<number>(48).fill(0xff), 0x00]);
    expect(Array.from(bytes.slice(-4))).toEqual([0x1d, 0x56, 66, 0]); // GS V 66 0
    // the ʻ of the Latin half reached the rasterizer as '
    const segment = rasterizer.segments[0];
    const drawn = segment?.blocks.flatMap((b) => (b ? [b.left] : [])) ?? [];
    expect(drawn).toContain("Ўзбекистон Қўқон Ғалла Ҳисоб / O'zbekiston g'alla");
  });

  it("test_qt_m01_22_latin_russian_text_mode: no Uzbek Cyrillic → text mode, ʻ printed as '", () => {
    const layout = layoutReceipt(
      { ...testReceiptDoc({ at: "2026-10-16T10:00:00" }), extraLines: ["Oʻzbekiston gʻalla / Итого"] },
      { paperWidth: 58 },
    );
    const rasterizer = fakeRasterizer();
    const { bytes, mode } = encodeEscPos(layout, { renderMode: "auto", rasterizer });
    expect(mode).toBe("text");
    expect(rasterizer.calls).toBe(0);
    const expected = [
      ...Array.from(new TextEncoder().encode("O'zbekiston g'alla / ")),
      0x88,
      0xe2,
      0xae,
      0xa3,
      0xae,
      0x0a,
    ];
    expect(indexOf(bytes, expected)).toBeGreaterThan(0);
    expect(indexOf(bytes, [0x1d, 0x76, 0x30])).toBe(-1);
  });

  it("render_mode=raster forces raster; render_mode=text keeps text and prints ? for missing glyphs", () => {
    const layout = layoutReceipt(testReceiptDoc({ at: "2026-10-16T10:00:00" }), { paperWidth: 80 });
    expect(encodeEscPos(layout, { renderMode: "text" }).mode).toBe("text");
    const text = encodeEscPos(layout, { renderMode: "text" }).bytes;
    expect(indexOf(text, [0x3f, 0xf7, 0x3f, 0xae, 0xad])).toBeGreaterThan(0); // Қўқон → "?ў?он"
    const raster = encodeEscPos(layout, { renderMode: "raster", rasterizer: fakeRasterizer() });
    expect(raster.mode).toBe("raster");
    expect(indexOf(raster.bytes, [0x1d, 0x76, 0x30, 0x00, 72, 0])).toBeGreaterThan(0); // 576 dots
  });

  it("sale receipt: styles, rule, native QR between raster segments", () => {
    const layout = layoutReceipt(SALE, { paperWidth: 58 });
    const { bytes, mode } = encodeEscPos(layout, { renderMode: "auto" });
    expect(mode).toBe("text");
    expect(indexOf(bytes, [0x1d, 0x21, 0x11])).toBeGreaterThan(0); // store name double size
    expect(indexOf(bytes, [...new Array<number>(32).fill(0x2d), 0x0a])).toBeGreaterThan(0); // 32-column rule
    expect(indexOf(bytes, qrCommand(SALE.fiscal?.qrUrl ?? ""))).toBeGreaterThan(0);
    // Uzbek Cyrillic product name → raster, QR stays a native command between two bitmaps
    const uz = layoutReceipt({ ...SALE, lines: [{ ...SALE.lines[0]!, name: "Қовун" }] }, { paperWidth: 58 });
    const rasterizer = fakeRasterizer();
    const encoded = encodeEscPos(uz, { renderMode: "auto", rasterizer });
    expect(encoded.mode).toBe("raster");
    expect(rasterizer.calls).toBe(2);
    expect(indexOf(encoded.bytes, qrCommand(SALE.fiscal?.qrUrl ?? ""))).toBeGreaterThan(0);
  });

  it("QR command: model 2, module 8, ECC M, store length pL pH", () => {
    expect(qrCommand("AB")).toEqual([
      0x1d, 0x28, 0x6b, 4, 0, 0x31, 0x41, 0x32, 0, 0x1d, 0x28, 0x6b, 3, 0, 0x31, 0x43, 8, 0x1d, 0x28, 0x6b, 3,
      0, 0x31, 0x45, 0x31, 0x1d, 0x28, 0x6b, 5, 0, 0x31, 0x50, 0x30, 0x41, 0x42, 0x1d, 0x28, 0x6b, 3, 0, 0x31,
      0x51, 0x30,
    ]);
  });

  it("raster bands of 96 rows", () => {
    const bitmap = { width: 16, height: 100, data: new Uint8Array(200).fill(0xaa) };
    const out = rasterCommand(bitmap);
    expect(out.slice(0, 8)).toEqual([0x1d, 0x76, 0x30, 0, 2, 0, 96, 0]);
    expect(out.slice(8 + 192, 8 + 192 + 8)).toEqual([0x1d, 0x76, 0x30, 0, 2, 0, 4, 0]);
    expect(out).toHaveLength(8 + 192 + 8 + 8);
  });

  it("rgbaToMono packs MSB-first, dark = 1", () => {
    const rgba = new Uint8Array([0, 0, 0, 255, 255, 255, 255, 255, 10, 10, 10, 255]);
    expect(Array.from(rgbaToMono(rgba, 3, 1).data)).toEqual([0b10100000]);
  });
});

describe("HTML receipt", () => {
  it("escapes product names and draws the QR as SVG", () => {
    const html = renderReceiptHtml(
      layoutReceipt(
        { ...SALE, lines: [{ ...SALE.lines[0]!, name: "<script>x</script>" }] },
        { paperWidth: 58 },
      ),
    );
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;x&lt;/script&gt;");
    expect(html).toContain("<svg");
    expect(html).not.toMatch(/style=/);
  });
});

describe("Z-report receipt (kind z_report, 18 §3.2)", () => {
  const Z: ReceiptDoc = {
    kind: "z_report",
    store: { name: "Do'kon", stir: "123456789", branchName: "Chilonzor-3" },
    number: "Z-7",
    issuedAt: "2026-10-16T22:00:00",
    cashierName: "Dilnoza",
    shiftNo: 7,
    lines: [],
    totals: null,
    payments: null,
    fiscal: null,
    zReport: {
      openedAt: "2026-10-16T08:00:00",
      closedAt: "2026-10-16T22:00:00",
      salesCount: 154,
      returnsCount: 2,
      totalsByMethod: { cash: m("1200000.00"), card: m("800000.00"), debt: m("50000.00") },
      cardSplit: { integrated: m("700000.00"), manual: m("100000.00") },
      cardSettlements: [
        {
          terminal: "TID 12345678",
          netTotal: m("700000.00"),
          expectedTotal: m("700000.00"),
          variance: m("0.00"),
          status: "matched",
        },
      ],
      returnsTotal: m("30000.00"),
      discountTotal: m("15000.00"),
      vatTotal: m("214285.71"),
      expectedCash: m("1200000.00"),
      countedCash: m("1199000.00"),
      variance: m("-1000.00"),
    },
  };
  const texts = (doc: ReceiptDoc) =>
    layoutReceipt(doc, { paperWidth: 58 }).blocks.flatMap((b) => (b.type === "text" ? [b.left] : []));

  it("title, figures, no thanks line, no fiscal block unless pending or fiscalized", () => {
    const t = texts(Z);
    expect(t).toContain("Z-HISOBOT / Z-ОТЧЁТ");
    expect(t).toContain("Sotuvlar soni / Кол-во продаж:");
    expect(t).toContain("Naqd / Наличные");
    expect(t).toContain("Qarz / Долг");
    expect(t).toContain("   Karta (terminalsiz) / Карта (без терминала)");
    expect(t).toContain("Terminal sverkasi / Сверка терминала: TID 12345678");
    expect(t).toContain("Farq / Расхождение:");
    expect(t).not.toContain("Rahmat! Yana kuting. / Спасибо! Ждём вас.");
    expect(t).not.toContain("Fiskal belgi kutilmoqda / Фискальный признак ожидается");
    expect(texts({ ...Z, fiscalPending: true })).toContain(
      "Fiskal belgi kutilmoqda / Фискальный признак ожидается",
    );
    const fiscalized = texts({
      ...Z,
      noQr: true,
      fiscal: { fmTerminalId: "ZZ000000000000", fmReceiptSeq: 155, fiscalSign: "1", qrUrl: "" },
    });
    expect(fiscalized).toContain("FM: ZZ000000000000");
    // sale receipts keep the pending line and the thanks line
    expect(texts({ ...Z, kind: "sale", zReport: null })).toContain(
      "Fiskal belgi kutilmoqda / Фискальный признак ожидается",
    );
  });

  it("ESC/POS: text mode, cp866 title bytes, amount rows right-aligned at 32 columns", () => {
    const layout = layoutReceipt(Z, { paperWidth: 58 });
    const { bytes, mode } = encodeEscPos(layout, { renderMode: "auto" });
    expect(mode).toBe("text");
    // "Z-HISOBOT / Z-" + "ОТЧЁТ" (cp866: О=8E Т=92 Ч=97 Ё=F0 Т=92), bold, centred
    const title = [
      ...Array.from(new TextEncoder().encode("Z-HISOBOT / Z-")),
      0x8e,
      0x92,
      0x97,
      0xf0,
      0x92,
      0x0a,
    ];
    expect(indexOf(bytes, title)).toBeGreaterThan(0);
    expect(indexOf(bytes, [0x1b, 0x45, 1, ...new Array<number>(6).fill(0x20), ...title])).toBeGreaterThan(0); // centred: (32 - 20) / 2
    const row = "Naqd / Наличные        1 200 000";
    expect(
      blockLines(
        { type: "text", left: "Naqd / Наличные", right: "1 200 000", align: "left", size: "normal" },
        32,
      ),
    ).toEqual([row]);
    expect(indexOf(bytes, [...encodeCp866(row), 0x0a])).toBeGreaterThan(0);
    expect(indexOf(bytes, [0x1d, 0x28, 0x6b])).toBe(-1); // no QR
  });

  it("HTML: title and figures, escaped, no QR", () => {
    const html = renderReceiptHtml(layoutReceipt(Z, { paperWidth: 80 }));
    expect(html).toContain('<span class="erp-receipt__left">Z-HISOBOT / Z-ОТЧЁТ</span>');
    expect(html).toContain('<span class="erp-receipt__left">Sanalgan naqd / Фактическая наличность:</span>');
    expect(html).not.toContain("<svg");
    expect(html).not.toContain("Rahmat!");
  });
});

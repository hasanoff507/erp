/**
 * Receipt layout — 08 §13.1 template (two languages, qaror #29), 18 §4.9 (name / name_ru rule),
 * 18 §4.5 (payment form, card requisites only for integrated card payments). Produces printer-agnostic
 * blocks; `escpos.ts` turns them into bytes, `html.ts` into HTML/DOM.
 */
import { formatDateTime } from "#/date/index.ts";
import { formatMoney, formatQty } from "#/format/index.ts";
import { addMoney, type Money, toDecimal } from "#/money/index.ts";

import type {
  PaperWidth,
  ReceiptBlock,
  ReceiptCardDetails,
  ReceiptDoc,
  ReceiptLayout,
  ReceiptLine,
  ReceiptPayment,
  ReceiptPaymentMethod,
  ReceiptPayments,
  ReceiptZReport,
  TextBlock,
  TextSize,
} from "./types.ts";

/** Font A characters per line (12×24 dots: 384 / 576 dots). */
export const COLUMNS: Record<PaperWidth, number> = { 58: 32, 80: 48 };
/** Font B characters per line (9×17 dots). */
export const SMALL_COLUMNS: Record<PaperWidth, number> = { 58: 42, 80: 64 };
/** Printable width in dots at 203 dpi. */
export const PRINT_DOTS: Record<PaperWidth, number> = { 58: 384, 80: 576 };

/** QT-M01-22 / US-M01-07 test text. */
export const TEST_RECEIPT_TEXT = "Ўзбекистон Қўқон Ғалла Ҳисоб / Oʻzbekiston gʻalla";

/** Fixed bilingual labels of the printed receipt (08 §13.1, 18 §4.9) — not UI i18n: the receipt is always uz / ru. */
export const RECEIPT_LABELS = {
  receiptNo: "Chek №",
  cashier: "Kassir / Кассир",
  shift: "Smena №",
  register: "Kassa / Касса",
  internalNo: "Ichki № / Внутр. №",
  total: "Jami / Итого:",
  discount: "Chegirma / Скидка",
  vatIncluded: (rate: string) => `QQS / НДС (${rate}%, ichida):`,
  vatExempt: "QQSsiz / Без НДС",
  paymentForm: "To'lov shakli / Форма оплаты:",
  received: "Olingan / Получено:",
  change: "Qaytim / Сдача:",
  cardType: "Karta turi / Тип карты:",
  approvalCode: "Tasdiq kodi / Код авт.:",
  fiscalPending: "Fiskal belgi kutilmoqda / Фискальный признак ожидается",
  fiscalSign: "Fiskal belgi:",
  fmReceipt: "Chek FM №:",
  ofdCheck: "ofd.soliq.uz — chekni tekshirish",
  thanks: "Rahmat! Yana kuting. / Спасибо! Ждём вас.",
  copy: "NUSXA / КОПИЯ",
  marking: "Markirovka:",
  z: {
    opened: "Smena ochildi / Смена открыта:",
    closed: "Smena yopildi / Смена закрыта:",
    zNumber: "Z №:",
    salesCount: "Sotuvlar soni / Кол-во продаж:",
    returnsCount: "Qaytarishlar soni / Кол-во возвратов:",
    byMethod: "To'lov usullari bo'yicha / По способам оплаты:",
    cardIntegrated: "Karta (integratsiyalangan) / Карта (интегр.)",
    cardManual: "Karta (terminalsiz) / Карта (без терминала)",
    settlement: "Terminal sverkasi / Сверка терминала:",
    settlementNet: "Terminal / Терминал",
    settlementExpected: "Kutilgan / Ожидалось",
    matched: "mos / совпадает",
    mismatch: "farq bor / расхождение",
    failed: "bajarilmadi / не выполнена",
    returnsTotal: "Qaytarishlar / Возвраты:",
    discountTotal: "Chegirmalar / Скидки:",
    vatTotal: "QQS / НДС:",
    expectedCash: "Kutilgan naqd / Ожидаемая наличность:",
    countedCash: "Sanalgan naqd / Фактическая наличность:",
    variance: "Farq / Расхождение:",
  },
  titles: {
    sale: null,
    return: "QAYTARISH / ВОЗВРАТ",
    debt_settlement: "QARZ TO'LOVI / ПОГАШЕНИЕ ДОЛГА",
    z_report: "Z-HISOBOT / Z-ОТЧЁТ",
    test: "SINOV CHEKI / ТЕСТОВЫЙ ЧЕК",
  },
  forms: {
    cash: "Naqd / Наличные",
    card: "Bank kartalari / Банковские карты",
    qr: "QR-kodli to'lov / Оплата по QR-коду",
    mixed: "Aralash / Смешанная",
  },
  methods: {
    cash: "Naqd / Наличные",
    card: "Bank kartasi / Банковская карта",
    uzqr: "QR-kodli to'lov (UzQR) / Оплата по QR-коду (UzQR)",
    click: "QR-kodli to'lov (Click) / Оплата по QR-коду (Click)",
    payme: "QR-kodli to'lov (Payme) / Оплата по QR-коду (Payme)",
    uzum: "QR-kodli to'lov (Uzum) / Оплата по QR-коду (Uzum)",
    debt: "Qarz / Долг",
  },
  cardTypes: {
    personal: "shaxsiy / личная",
    corporate: "korporativ / корпоративная",
    social: "ijtimoiy / социальная",
    unknown: "noma'lum / не определён",
  },
} as const;

const som = (value: Money | string): string => formatMoney(value, { withCurrency: false });
const somWithCurrency = (value: Money | string): string => formatMoney(value);
const vatAmount = (value: Money | string): string =>
  formatMoney(value, { precision: 2, withCurrency: false });

function price(value: string): string {
  return formatMoney(value, { precision: toDecimal(value).isInteger() ? 0 : 2, withCurrency: false });
}

/** Word wrap to `width` characters; words longer than a line are split. */
export function wrapText(text: string, width: number): string[] {
  const out: string[] = [];
  for (const paragraph of text.split("\n")) {
    let line = "";
    for (const rawWord of paragraph.split(" ")) {
      let word = rawWord;
      while ([...word].length > width) {
        const room = line ? width - [...line].length - 1 : width;
        if (room <= 0) {
          out.push(line);
          line = "";
          continue;
        }
        const chars = [...word];
        const head = chars.slice(0, room).join("");
        out.push(line ? `${line} ${head}` : head);
        line = "";
        word = chars.slice(room).join("");
      }
      if (!line) line = word;
      else if ([...line].length + 1 + [...word].length <= width) line = `${line} ${word}`;
      else {
        out.push(line);
        line = word;
      }
    }
    out.push(line);
  }
  return out;
}

const textLength = (s: string) => [...s].length;

/** Characters per line for a block size. `large` = double width (GS ! 0x11). */
export function columnsFor(layout: Pick<ReceiptLayout, "columns" | "smallColumns">, size: TextSize): number {
  if (size === "small") return layout.smallColumns;
  if (size === "large") return Math.floor(layout.columns / 2);
  return layout.columns;
}

/**
 * Plain-text lines of a text block at a fixed column count: wraps `left`, puts `right` at the end of the last
 * line (or on its own line when it does not fit), pads for center/right alignment.
 */
export function blockLines(block: TextBlock, columns: number): string[] {
  const lines = wrapText(block.left, columns);
  if (block.right !== undefined && block.right !== "") {
    const right = block.right;
    const last = lines[lines.length - 1] ?? "";
    if (textLength(last) + 1 + textLength(right) <= columns) {
      lines[lines.length - 1] = last + " ".repeat(columns - textLength(last) - textLength(right)) + right;
    } else {
      lines.push(" ".repeat(Math.max(0, columns - textLength(right))) + right);
    }
    return lines;
  }
  if (block.align === "left") return lines;
  return lines.map((line) => {
    const free = Math.max(0, columns - textLength(line));
    const pad = block.align === "center" ? Math.floor(free / 2) : free;
    return " ".repeat(pad) + line;
  });
}

const text = (left: string, options: Partial<Omit<TextBlock, "type" | "left">> = {}): TextBlock => ({
  type: "text",
  left,
  align: options.align ?? "left",
  size: options.size ?? "normal",
  ...(options.right !== undefined ? { right: options.right } : {}),
  ...(options.bold ? { bold: true } : {}),
});

const INDENT = "   ";

function lineBlocks(line: ReceiptLine, index: number, paperWidth: PaperWidth): ReceiptBlock[] {
  const blocks: ReceiptBlock[] = [];
  const columns = COLUMNS[paperWidth];
  const n = `${index + 1}. `;
  const nameRu = line.nameRu?.trim() ? line.nameRu.trim() : null;
  const joined = nameRu ? `${n}${line.name} / ${nameRu}` : `${n}${line.name}`;
  if (!nameRu || (paperWidth === 80 && textLength(joined) <= columns)) {
    blocks.push(text(joined));
  } else {
    blocks.push(text(`${n}${line.name}`));
    blocks.push(text(`${INDENT}${nameRu}`, { size: "small" }));
  }
  const discount = line.discount && !toDecimal(line.discount).isZero() ? line.discount : null;
  const gross = discount ? addMoney(line.total, discount) : line.total;
  blocks.push(
    text(`${INDENT}${formatQty(line.qty, line.qtyKind)} x ${price(line.unitPrice)}`, { right: som(gross) }),
  );
  if (discount) blocks.push(text(`${INDENT}${RECEIPT_LABELS.discount}`, { right: `-${som(discount)}` }));
  const requisites = [
    line.mxik ? `MXIK ${line.mxik}` : null,
    line.unitLabel,
    line.barcode ?? null,
    line.vatRate !== null
      ? `QQS ${line.vatRate}%: ${vatAmount(line.vat)}`
      : `QQSsiz${line.vatExemptCode ? ` (imtiyoz: ${line.vatExemptCode})` : ""}`,
  ].filter((part): part is string => Boolean(part));
  blocks.push(text(`${INDENT}${requisites.join(" · ")}`, { size: "small" }));
  for (const code of line.markingCodes ?? []) {
    blocks.push(text(`${INDENT}${RECEIPT_LABELS.marking} ${code}`, { size: "small" }));
  }
  return blocks;
}

function cardBlocks(card: ReceiptCardDetails): ReceiptBlock[] {
  // Terminal-less (manual) card payment: payment form only, no requisites (21 §9.2, 26 #178).
  if (card.entryMode !== "integrated") return [];
  const blocks: ReceiptBlock[] = [];
  if (card.cardType) {
    blocks.push(
      text(`${INDENT}${RECEIPT_LABELS.cardType} ${RECEIPT_LABELS.cardTypes[card.cardType]}`, {
        size: "small",
      }),
    );
  }
  const maskRrn = [card.cardMask, card.rrn ? `RRN ${card.rrn}` : null].filter(Boolean).join(" · ");
  if (maskRrn) blocks.push(text(`${INDENT}${maskRrn}`, { size: "small" }));
  const scheme = [
    card.scheme ? card.scheme.charAt(0).toUpperCase() + card.scheme.slice(1) : null,
    card.approvalCode ? `${RECEIPT_LABELS.approvalCode} ${card.approvalCode}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  if (scheme) blocks.push(text(`${INDENT}${scheme}`, { size: "small" }));
  if (card.tid) blocks.push(text(`${INDENT}TID ${card.tid}`, { size: "small" }));
  return blocks;
}

function paymentLabel(payment: ReceiptPayment): string {
  return RECEIPT_LABELS.methods[payment.method];
}

function paymentBlocks(payments: ReceiptPayments): ReceiptBlock[] {
  const blocks: ReceiptBlock[] = [
    text(RECEIPT_LABELS.paymentForm),
    text(RECEIPT_LABELS.forms[payments.form], { bold: true }),
  ];
  for (const payment of payments.items) {
    blocks.push(text(paymentLabel(payment), { right: som(payment.amount) }));
    if (payment.card) blocks.push(...cardBlocks(payment.card));
  }
  if (payments.received)
    blocks.push(text(RECEIPT_LABELS.received, { right: somWithCurrency(payments.received) }));
  if (payments.change) blocks.push(text(RECEIPT_LABELS.change, { right: somWithCurrency(payments.change) }));
  return blocks;
}

function zReportBlocks(z: ReceiptZReport): ReceiptBlock[] {
  const L = RECEIPT_LABELS.z;
  const blocks: ReceiptBlock[] = [];
  if (z.zNumber != null) blocks.push(text(L.zNumber, { right: String(z.zNumber), bold: true }));
  if (z.openedAt) blocks.push(text(L.opened, { right: formatDateTime(z.openedAt) }));
  if (z.closedAt) blocks.push(text(L.closed, { right: formatDateTime(z.closedAt) }));
  blocks.push(text(L.salesCount, { right: String(z.salesCount) }));
  blocks.push(text(L.returnsCount, { right: String(z.returnsCount) }));
  blocks.push({ type: "rule" });
  blocks.push(text(L.byMethod));
  for (const method of Object.keys(RECEIPT_LABELS.methods) as ReceiptPaymentMethod[]) {
    const amount = z.totalsByMethod[method];
    if (amount != null) blocks.push(text(RECEIPT_LABELS.methods[method], { right: som(amount) }));
  }
  if (z.cardSplit) {
    blocks.push(text(`${INDENT}${L.cardIntegrated}`, { right: som(z.cardSplit.integrated), size: "small" }));
    blocks.push(text(`${INDENT}${L.cardManual}`, { right: som(z.cardSplit.manual), size: "small" }));
  }
  for (const st of z.cardSettlements ?? []) {
    blocks.push(text(`${L.settlement} ${st.terminal}`));
    blocks.push(text(`${INDENT}${L.settlementNet}`, { right: som(st.netTotal), size: "small" }));
    blocks.push(text(`${INDENT}${L.settlementExpected}`, { right: som(st.expectedTotal), size: "small" }));
    blocks.push(
      text(
        `${INDENT}${st.status === "matched" ? L.matched : st.status === "failed" ? L.failed : L.mismatch}`,
        {
          right: som(st.variance),
          size: "small",
        },
      ),
    );
  }
  blocks.push({ type: "rule" });
  blocks.push(text(L.returnsTotal, { right: somWithCurrency(z.returnsTotal) }));
  blocks.push(text(L.discountTotal, { right: somWithCurrency(z.discountTotal) }));
  blocks.push(text(L.vatTotal, { right: `${vatAmount(z.vatTotal)} so'm` }));
  blocks.push({ type: "rule" });
  blocks.push(text(L.expectedCash, { right: somWithCurrency(z.expectedCash) }));
  blocks.push(text(L.countedCash, { right: somWithCurrency(z.countedCash) }));
  blocks.push(text(L.variance, { right: somWithCurrency(z.variance), bold: true }));
  return blocks;
}

export interface LayoutOptions {
  paperWidth: PaperWidth;
}

/** ReceiptDoc → printer-agnostic blocks (08 §13.1). */
export function layoutReceipt(doc: ReceiptDoc, { paperWidth }: LayoutOptions): ReceiptLayout {
  const blocks: ReceiptBlock[] = [];
  const rule = (): void => {
    blocks.push({ type: "rule" });
  };

  blocks.push(text(doc.store.name, { align: "center", bold: true, size: "large" }));
  const contact = [doc.store.address, doc.store.phone].filter(Boolean).join(", ");
  if (contact) blocks.push(text(contact, { align: "center", size: "small" }));
  const ids = [
    doc.store.stir ? `STIR: ${doc.store.stir}` : null,
    doc.store.branchName ? `Filial: ${doc.store.branchName}` : null,
  ]
    .filter(Boolean)
    .join("  ");
  if (ids) blocks.push(text(ids, { align: "center", size: "small" }));
  const title = RECEIPT_LABELS.titles[doc.kind];
  if (title) blocks.push(text(title, { align: "center", bold: true }));
  rule();

  blocks.push(text(`${RECEIPT_LABELS.receiptNo} ${doc.number}`, { right: formatDateTime(doc.issuedAt) }));
  blocks.push(
    text(`${RECEIPT_LABELS.cashier}: ${doc.cashierName}`, {
      right: doc.shiftNo != null ? `${RECEIPT_LABELS.shift}${doc.shiftNo}` : "",
    }),
  );
  const registerParts = [
    doc.registerNo ? `${RECEIPT_LABELS.register}: ${doc.registerNo}` : null,
    doc.receiptSeq != null ? `${RECEIPT_LABELS.internalNo} ${doc.receiptSeq}` : null,
  ].filter(Boolean);
  if (registerParts.length) blocks.push(text(registerParts.join(" · "), { size: "small" }));

  if (doc.extraLines?.length) {
    rule();
    for (const extra of doc.extraLines) blocks.push(text(extra));
  }

  if (doc.zReport) {
    rule();
    blocks.push(...zReportBlocks(doc.zReport));
  }

  if (doc.lines.length) {
    rule();
    doc.lines.forEach((line, i) => blocks.push(...lineBlocks(line, i, paperWidth)));
  }

  if (doc.totals) {
    rule();
    blocks.push(text(RECEIPT_LABELS.total, { right: somWithCurrency(doc.totals.total), bold: true }));
    blocks.push(text(`${RECEIPT_LABELS.discount}:`, { right: somWithCurrency(doc.totals.discount) }));
    if (doc.totals.vat.length === 0) blocks.push(text(RECEIPT_LABELS.vatExempt));
    for (const row of doc.totals.vat) {
      blocks.push(text(RECEIPT_LABELS.vatIncluded(row.rate), { right: `${vatAmount(row.amount)} so'm` }));
    }
  }

  if (doc.payments) {
    rule();
    blocks.push(...paymentBlocks(doc.payments));
  }

  const fiscalBlock =
    doc.kind === "z_report" ? Boolean(doc.fiscal || doc.fiscalPending) : doc.kind !== "test";
  if (fiscalBlock) {
    rule();
    if (doc.fiscal) {
      blocks.push(
        text(`FM: ${doc.fiscal.fmTerminalId}`, {
          right: `${RECEIPT_LABELS.fmReceipt} ${doc.fiscal.fmReceiptSeq}`,
        }),
      );
      if (!doc.noQr) {
        blocks.push(text(`${RECEIPT_LABELS.fiscalSign} ${doc.fiscal.fiscalSign}`));
        blocks.push({ type: "qr", data: doc.fiscal.qrUrl });
        blocks.push(text(RECEIPT_LABELS.ofdCheck, { align: "center", size: "small" }));
      }
    } else {
      blocks.push(text(RECEIPT_LABELS.fiscalPending, { align: "center", size: "small" }));
    }
  }

  if (doc.slipText) {
    rule();
    for (const slip of doc.slipText.split("\n")) blocks.push(text(slip, { size: "small" }));
  }

  if (doc.kind !== "z_report") {
    rule();
    blocks.push(text(RECEIPT_LABELS.thanks, { align: "center" }));
  }
  if (doc.copy) blocks.push(text(RECEIPT_LABELS.copy, { align: "center", bold: true, size: "large" }));
  blocks.push({ type: "feed", lines: 3 });

  return { paperWidth, columns: COLUMNS[paperWidth], smallColumns: SMALL_COLUMNS[paperWidth], blocks };
}

export interface TestReceiptOptions {
  /** ISO instant of the test print. */
  at: string;
  storeName?: string;
  transport?: string | null;
  paperWidth?: PaperWidth;
  codepage?: string;
}

/** «Sinov chek» of POS-16 (US-M01-07, QT-M01-22). */
export function testReceiptDoc(options: TestReceiptOptions): ReceiptDoc {
  const extra = [
    TEST_RECEIPT_TEXT,
    "Lotin / Латиница: O'zbekiston, g'alla, so'm",
    "Кириллица: Ўзбекистон, Тошкент",
  ];
  if (options.transport) extra.push(`Printer / Принтер: ${options.transport}`);
  if (options.paperWidth) extra.push(`Qog'oz / Бумага: ${options.paperWidth} mm`);
  extra.push(`Kod sahifa / Кодовая страница: ${options.codepage ?? "cp866"}`);
  return {
    kind: "test",
    store: { name: options.storeName ?? "ERP" },
    number: "TEST",
    issuedAt: options.at,
    cashierName: "—",
    lines: [],
    totals: null,
    payments: null,
    fiscal: null,
    extraLines: extra,
  };
}

/** Every visible string of a layout (raster decision, tests). */
export function layoutTexts(layout: ReceiptLayout): string[] {
  const out: string[] = [];
  for (const block of layout.blocks) {
    if (block.type === "text") {
      out.push(block.left);
      if (block.right) out.push(block.right);
    }
  }
  return out;
}

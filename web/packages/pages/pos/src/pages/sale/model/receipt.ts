/**
 * POS-04 receipt (07 POS-04; 18 §4.5, §6; 08 §13): the printed receipt goes out right after the sale through
 * the device `PrinterPort`; a printer error offers the electronic receipt (QR on screen) and POS-16. Fiscal
 * state comes from the outbox result (`server.fiscal`) and the pulled `fiscal_receipts` row
 * (`fiscal.receiptFor`): pending → «Fiskal belgi kutilmoqda», fiscalized → sign + QR, failed → retry visible
 * (online `POST /fiscal-receipts/{id}/retry`). A reprint prints «NUSXA / КОПИЯ» and writes
 * `receipt.reprinted` — it needs the server's `fiscal_receipt_id`, so it is enabled once that id is known.
 */
import { combine, createEffect, createEvent, createStore, sample } from "effector";

import { api } from "@shared/api";
import { PrinterError } from "@shared/lib/printer";
import type { ReceiptDoc, ReceiptLine, ReceiptPayment } from "@shared/lib/receipt";
import {
  enqueueEvent,
  fiscal,
  outbox,
  outboxChanged,
  pullApplied,
  type FiscalReceiptRow,
  type OutboxRow,
} from "@shared/offline";
import { $isOnline } from "@shared/state/network";

import { $posCashier, $posDevice } from "#/entities/pos-session/index.ts";
import { posPrinter } from "#/shared/lib/device-runtime.ts";

import { $storeInfo, type StoreInfo } from "./context.ts";
import type { CardPart } from "./lib/sale-payload.ts";
import { $lastSale, type FinishedSale } from "./payment.ts";

export interface ReceiptFiscalView {
  status: "pending" | "sent" | "fiscalized" | "failed" | "deferred" | "local";
  fiscalReceiptId: string | null;
  fiscalSign: string | null;
  qrUrl: string | null;
  fmTerminalId: string | null;
  fmReceiptSeq: string | number | null;
  fiscalAt: string | null;
  number: string | null;
  syncStatus: OutboxRow["status"] | null;
  errorCode: string | null;
}

export const receiptOpened = createEvent();
export const printRequested = createEvent<{ copy: boolean }>();
export const fiscalRefreshRequested = createEvent();
export const fiscalRetryRequested = createEvent();
export const electronicShown = createEvent<"printer_failure" | "customer_request">();

const unitKind = (fractional: boolean) => (fractional ? "fractional" : "integer");

const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);

function cardDetails(card: CardPart | undefined): ReceiptPayment["card"] {
  if (!card) return null;
  if (card.mode === "manual") return { entryMode: "manual" };
  const r = card.cardResult;
  return {
    entryMode: "integrated",
    cardType: (str(r.card_type) as "personal" | "corporate" | "social" | "unknown" | null) ?? "unknown",
    cardMask: str(r.card_mask),
    rrn: str(r.rrn),
    approvalCode: str(r.approval_code),
    scheme: str(r.card_scheme),
    tid: str(r.tid),
  };
}

/** Receipt document (08 §13.1, two languages, VAT by rate — US-M10-01). */
export function receiptDoc(
  sale: FinishedSale,
  store: StoreInfo,
  fiscalView: ReceiptFiscalView | null,
  copy: boolean,
): ReceiptDoc {
  const lines: ReceiptLine[] = sale.totals.lines.map((l) => ({
    name: l.name,
    nameRu: l.nameRu,
    qty: l.qty,
    qtyKind: unitKind(l.fractional),
    unitPrice: l.price,
    unitLabel: l.unitCode,
    discount: l.discount,
    total: l.total,
    mxik: l.mxik,
    barcode: l.barcode,
    vatRate: l.vatExemptionCode && l.vatRate === "0.00" ? null : l.vatRate.replace(/\.00$/, ""),
    vat: l.vat,
    vatExemptCode: l.vatExemptionCode,
    markingCodes: l.markingCode ? [l.markingCode] : [],
  }));
  const fiscalBlock =
    fiscalView?.status === "fiscalized" && fiscalView.fiscalSign && fiscalView.qrUrl
      ? {
          fmTerminalId: fiscalView.fmTerminalId ?? "",
          fmReceiptSeq: fiscalView.fmReceiptSeq ?? "",
          fiscalSign: fiscalView.fiscalSign,
          qrUrl: fiscalView.qrUrl,
          fiscalAt: fiscalView.fiscalAt,
        }
      : null;
  const slip = sale.parts.find((p) => p.card?.mode === "integrated")?.card;
  return {
    kind: "sale",
    copy,
    store: { name: store.name, stir: store.stir, branchName: store.branchName },
    number: fiscalView?.number ?? sale.tempNumber,
    issuedAt: sale.createdAt,
    cashierName: sale.cashierName,
    shiftNo: sale.shiftNo,
    registerNo: store.registerName,
    receiptSeq: sale.receiptSeq,
    lines,
    totals: { total: sale.totals.total, discount: sale.totals.discount, vat: sale.totals.vat },
    payments: {
      form: sale.form,
      items: sale.parts.map((p) => ({ method: p.method, amount: p.amount, card: cardDetails(p.card) })),
      received: sale.received,
      change: sale.change,
    },
    fiscal: fiscalBlock,
    slipText: slip?.mode === "integrated" ? str(slip.cardResult.slip_text) : null,
  };
}

function fromRows(row: OutboxRow | undefined, receipt: FiscalReceiptRow | undefined): ReceiptFiscalView {
  const server = row?.server ?? null;
  const serverFiscal = (server?.fiscal ?? null) as Record<string, unknown> | null;
  const status = (str(receipt?.status) ??
    str(serverFiscal?.status) ??
    "local") as ReceiptFiscalView["status"];
  return {
    status: row?.status === "rejected" ? "failed" : status,
    fiscalReceiptId: receipt?.id ?? null,
    fiscalSign: str(receipt?.fiscal_sign),
    qrUrl: str(receipt?.qr_url),
    fmTerminalId: str(receipt?.fm_terminal_id),
    fmReceiptSeq: (receipt?.fm_receipt_seq as string | number | null | undefined) ?? null,
    fiscalAt: str(receipt?.fiscal_at),
    number: str(server?.number),
    syncStatus: row?.status ?? null,
    errorCode: row?.status === "rejected" ? row.error_code : null,
  };
}

/** Local outbox + pulled fiscal row; online and not pulled yet → `GET /fiscal-receipts?sale_id=`. */
export const loadFiscalFx = createEffect(
  async ({ sale, online }: { sale: FinishedSale; online: boolean }): Promise<ReceiptFiscalView> => {
    const [row, pulled] = await Promise.all([
      outbox.get(sale.clientEventId),
      fiscal.receiptFor(sale.clientEventId),
    ]);
    let receipt = pulled;
    if (!receipt && online && sale.fiscal && (row?.status === "accepted" || row?.status === "duplicate")) {
      try {
        const page = await api.sales.listFiscalReceipts({ sale_id: sale.saleId, kind: "sale" });
        const first = page.items[0];
        if (first) receipt = { ...first };
      } catch {
        /* offline / not yet — the next pull brings it */
      }
    }
    return fromRows(row, receipt);
  },
);

export const $receiptFiscal = createStore<ReceiptFiscalView | null>(null)
  .on(loadFiscalFx.doneData, (_, v) => v)
  .reset(receiptOpened);

export type PrintState =
  | { kind: "idle" }
  | { kind: "printing" }
  | { kind: "printed"; copy: boolean }
  | { kind: "error"; code: string };

export const $printState = createStore<PrintState>({ kind: "idle" });
export const $electronic = createStore<"printer_failure" | "customer_request" | null>(null)
  .on(electronicShown, (_, r) => r)
  .reset(receiptOpened);
export const $reprintCount = createStore(0).reset(receiptOpened);

export const printFx = createEffect(async (doc: ReceiptDoc) => {
  const port = await posPrinter();
  await port.printReceipt(doc);
  return doc.copy === true;
});

/** `receipt.reprinted` (18 §6) — one audit row per copy. */
export const reprintEventFx = createEffect(
  async ({ sale, fiscalReceiptId, actor }: { sale: FinishedSale; fiscalReceiptId: string; actor: string }) =>
    enqueueEvent(
      "receipt.reprinted",
      { fiscal_receipt_id: fiscalReceiptId, sale_id: sale.saleId, reason: null },
      { actorUserId: actor },
    ),
);

$printState
  .on(printFx, () => ({ kind: "printing" }))
  .on(printFx.doneData, (_, copy) => ({ kind: "printed", copy }))
  .on(printFx.failData, (_, e) => ({
    kind: "error",
    code: e instanceof PrinterError ? e.code : "write_failed",
  }))
  .reset(receiptOpened);
$reprintCount.on(reprintEventFx.done, (n) => n + 1);

const $source = combine({ sale: $lastSale, store: $storeInfo, fiscalView: $receiptFiscal });

// first print right after the sale (printed delivery only); refresh the fiscal state
sample({
  clock: receiptOpened,
  source: { sale: $lastSale, online: $isOnline },
  filter: ({ sale }) => sale !== null,
  fn: ({ sale, online }) => ({ sale: sale as FinishedSale, online }),
  target: loadFiscalFx,
});
/** The first print happens once per sale (a remount / StrictMode re-run never prints twice). */
const $firstPrinted = createStore<string | null>(null);
const firstPrint = sample({
  clock: receiptOpened,
  source: { s: $source, done: $firstPrinted },
  filter: ({ s, done }) => s.sale !== null && s.sale.delivery === "printed" && done !== s.sale.clientEventId,
  fn: ({ s }) => s,
});
$firstPrinted.on(firstPrint, (_, s) => s.sale?.clientEventId ?? null);
sample({
  clock: firstPrint,
  fn: ({ sale, store, fiscalView }) => receiptDoc(sale as FinishedSale, store, fiscalView, false),
  target: printFx,
});
sample({
  clock: [fiscalRefreshRequested, outboxChanged, pullApplied],
  source: { sale: $lastSale, online: $isOnline },
  filter: ({ sale }) => sale !== null,
  fn: ({ sale, online }) => ({ sale: sale as FinishedSale, online }),
  target: loadFiscalFx,
});

// reprint: copy print + receipt.reprinted (only with a known fiscal_receipt_id)
sample({
  clock: printRequested,
  source: $source,
  filter: ({ sale }) => sale !== null,
  fn: ({ sale, store, fiscalView }, { copy }) => receiptDoc(sale as FinishedSale, store, fiscalView, copy),
  target: printFx,
});
sample({
  clock: printFx.done,
  source: { sale: $lastSale, fiscalView: $receiptFiscal, cashier: $posCashier },
  filter: ({ sale, fiscalView, cashier }, { params }) =>
    params.copy === true && sale !== null && !!fiscalView?.fiscalReceiptId && cashier !== null,
  fn: ({ sale, fiscalView, cashier }) => ({
    sale: sale as FinishedSale,
    fiscalReceiptId: fiscalView?.fiscalReceiptId ?? "",
    actor: cashier?.userId ?? "",
  }),
  target: reprintEventFx,
});

/** Fiscal receipt failed → retry (online, 18 §14.2). */
export const retryFiscalFx = createEffect(async (fiscalReceiptId: string) => {
  await api.sales.retryFiscalReceipt(fiscalReceiptId, null);
});
sample({
  clock: fiscalRetryRequested,
  source: { view: $receiptFiscal, online: $isOnline },
  filter: ({ view, online }) => online && !!view?.fiscalReceiptId,
  fn: ({ view }) => view?.fiscalReceiptId ?? "",
  target: retryFiscalFx,
});
sample({ clock: retryFiscalFx.finally, target: fiscalRefreshRequested });

export const $canReprint = combine(
  $receiptFiscal,
  $posDevice,
  (view, device) => device !== null && !!view?.fiscalReceiptId,
);

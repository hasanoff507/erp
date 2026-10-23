/**
 * Scanner / product pick → receipt line (07 POS-02, 06 §1.6–§1.7, 24 §5.1, QT-NFR-01 < 100 ms, all local):
 * 1. a marked product waits for its DataMatrix → the next scan is the marking code (local duplicate check
 *    always, 18 §4.2 / 16 §7; the online precheck endpoint is not in B3 — `block` policy refuses online);
 * 2. weight / amount EAN-13 of the tenant templates (US-M09-06) → product by item code + qty from the label;
 * 3. an ordinary barcode (pack size `units_per_barcode`) or a DataMatrix whose GTIN is a product barcode;
 * 4. tile click: piece → line (+1 if present), weighed → weight dialog, marked → «Markirovka kodini skanerlang».
 * A product without a current price is never sold (16 §7, MARKING_PRICE_UNKNOWN_OFFLINE for marked goods).
 */
import { createEffect, createEvent, createStore, sample } from "effector";

import { newAttemptId as newId } from "@shared/lib/card-terminal";
import { parseWeightBarcode, weightLineQty, type WeightBarcodeTemplate } from "@shared/lib/scale";
import { catalog, markingCodes, type ProductView } from "@shared/offline";
import { $isOnline } from "@shared/state/network";

import {
  $draft,
  lineAdded,
  parseQty,
  price4,
  type DraftLine,
  type LineKind,
} from "#/entities/receipt-draft/index.ts";

import { $posSettings } from "./context.ts";
import { unitIsFractional } from "./units.ts";

export interface ScanError {
  code: string;
  params?: Record<string, unknown>;
}

export const codeScanned = createEvent<string>();
export const productPicked = createEvent<ProductView>();
export const weightEntered = createEvent<{ view: ProductView; qty: string }>();
export const scanPromptClosed = createEvent();
export const scanErrorDismissed = createEvent();

/** Product kind chip (07 POS-02: «dona» / «tarozi» / «markirovka»). */
export function kindOf(view: Pick<ProductView, "product">): LineKind {
  if (view.product.is_marked === true) return "marked";
  if (view.product.is_weighed === true) return "weighed";
  return "piece";
}

/** A unit that was not pulled yet counts as non-fractional unless the product is weighed (18 §2.3). */
export function isFractional(view: Pick<ProductView, "product">): boolean {
  return view.product.is_weighed === true || unitIsFractional(view.product.unit_code);
}

const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);

export function toLine(
  view: ProductView,
  qty: string,
  extra: { barcode?: string | null; markingCode?: string | null; markingWarning?: boolean } = {},
): DraftLine {
  const rate = str(view.product.vat_rate);
  return {
    id: newId(),
    productId: view.product.id,
    name: view.product.name,
    nameRu: view.product.name_ru ?? null,
    unitCode: view.product.unit_code,
    fractional: isFractional(view),
    kind: kindOf(view),
    qty,
    price: price4(view.price ?? "0"),
    vatRate: rate ? price4(rate).slice(0, -2) : "0.00",
    vatExemptionCode: str(view.product.vat_exemption_code),
    mxik: str(view.product.mxik_code),
    barcode: extra.barcode ?? null,
    markingCode: extra.markingCode ?? null,
    markingWarning: extra.markingWarning ?? false,
  };
}

/** DataMatrix of the marking system: `01` + GTIN-14 (+ AI 21 serial, GS separators). */
export function gtinOf(code: string): string | null {
  const m = /^(?:\]d2)?01(\d{14})/.exec(code);
  return m?.[1] ?? null;
}

export function looksLikeMarking(code: string): boolean {
  return code.length >= 18 && (code.includes("\u001d") || gtinOf(code) !== null);
}

const MARKING_MIN = 18;
const MARKING_MAX = 255;
/** 18 §4.2 / backend `marking_code_valid`: 18–255 printable ASCII, GS allowed inside. */
export function markingCodeValid(code: string): boolean {
  if (
    code.length < MARKING_MIN ||
    code.length > MARKING_MAX ||
    code !== code.trim() ||
    code.startsWith("\u001d")
  )
    return false;
  for (const ch of code) {
    const c = ch.charCodeAt(0);
    if (ch !== "\u001d" && (c < 0x21 || c > 0x7e)) return false;
  }
  return true;
}

type ScanOutcome =
  | { kind: "line"; line: DraftLine }
  | { kind: "await_marking"; view: ProductView }
  | { kind: "weigh"; view: ProductView }
  | { kind: "error"; error: ScanError };

interface ScanInput {
  code: string;
  awaiting: ProductView | null;
  templates: readonly WeightBarcodeTemplate[];
  precheck: "off" | "warn" | "block";
  online: boolean;
  usedInDraft: readonly string[];
}

async function markedLine(view: ProductView, code: string, input: ScanInput): Promise<ScanOutcome> {
  if (!markingCodeValid(code)) return { kind: "error", error: { code: "MARKING_CODE_INVALID" } };
  if (input.usedInDraft.includes(code) || (await markingCodes.isUsed(code))) {
    return { kind: "error", error: { code: "MARKING_CODE_ALREADY_SOLD" } };
  }
  if (view.price === null) {
    return {
      kind: "error",
      error: { code: "MARKING_PRICE_UNKNOWN_OFFLINE", params: { name: view.product.name } },
    };
  }
  // 18 §15 precheck: `block` needs a positive online answer; the verify endpoint is not available in B3.
  if (input.online && input.precheck === "block") {
    return { kind: "error", error: { code: "MARKING_VERIFY_UNAVAILABLE" } };
  }
  return { kind: "line", line: toLine(view, "1.000", { markingCode: code }) };
}

function priced(view: ProductView): ScanError | null {
  return view.price === null ? { code: "PRICE_UNKNOWN", params: { name: view.product.name } } : null;
}

export async function resolveScan(input: ScanInput): Promise<ScanOutcome> {
  const code = input.code.trim();
  if (!code) return { kind: "error", error: { code: "PRODUCT_NOT_FOUND" } };

  if (input.awaiting) {
    if (looksLikeMarking(code) || markingCodeValid(code)) return markedLine(input.awaiting, code, input);
    // a product barcode instead of the DataMatrix → keep waiting
    return {
      kind: "error",
      error: { code: "MARKING_SCAN_REQUIRED", params: { name: input.awaiting.product.name } },
    };
  }

  const weight = parseWeightBarcode(code, input.templates);
  if (weight.ok) {
    const view = await catalog.byItemCode(weight.productCode);
    if (!view) return { kind: "error", error: { code: "PRODUCT_NOT_FOUND" } };
    const noPrice = priced(view);
    if (noPrice) return { kind: "error", error: noPrice };
    const qty = weight.kind === "WEIGHT" ? weight.qty : weightLineQty(weight, view.price ?? "0");
    if (!qty || qty === "0.000") return { kind: "error", error: { code: "BARCODE_INVALID" } };
    return { kind: "line", line: toLine(view, qty, { barcode: code }) };
  }

  const hit = await catalog.byBarcode(code);
  if (hit) {
    const noPrice = kindOf(hit) === "marked" ? null : priced(hit);
    if (noPrice) return { kind: "error", error: noPrice };
    if (kindOf(hit) === "marked") return { kind: "await_marking", view: hit };
    if (kindOf(hit) === "weighed" && hit.unitsPerBarcode === "1.000") return { kind: "weigh", view: hit };
    return { kind: "line", line: toLine(hit, hit.unitsPerBarcode || "1.000", { barcode: code }) };
  }

  const gtin = gtinOf(code);
  if (gtin) {
    const byGtin = (await catalog.byBarcode(gtin)) ?? (await catalog.byBarcode(gtin.replace(/^0/, "")));
    if (byGtin && kindOf(byGtin) === "marked") return markedLine(byGtin, code, input);
  }

  if (!weight.ok && weight.reason === "check_digit")
    return { kind: "error", error: { code: "BARCODE_INVALID" } };
  return { kind: "error", error: { code: "PRODUCT_NOT_FOUND", params: { code } } };
}

export const $awaitingMarking = createStore<ProductView | null>(null);
export const $weighing = createStore<ProductView | null>(null);
export const $scanError = createStore<ScanError | null>(null);

export const scanFx = createEffect(resolveScan);

sample({
  clock: codeScanned,
  source: { awaiting: $awaitingMarking, settings: $posSettings, online: $isOnline, draft: $draft },
  fn: ({ awaiting, settings, online, draft }, code): ScanInput => ({
    code,
    awaiting,
    templates: (settings?.weightBarcodeTemplates ?? []) as unknown as WeightBarcodeTemplate[],
    precheck: settings?.markingPrecheck ?? "warn",
    online,
    usedInDraft: draft.lines.flatMap((l) => (l.markingCode ? [l.markingCode] : [])),
  }),
  target: scanFx,
});

sample({
  clock: scanFx.doneData,
  filter: (r) => r.kind === "line",
  fn: (r) => (r as Extract<ScanOutcome, { kind: "line" }>).line,
  target: lineAdded,
});

$awaitingMarking
  .on(scanFx.doneData, (s, r) => (r.kind === "await_marking" ? r.view : r.kind === "line" ? null : s))
  .on(productPicked, (_, v) => (kindOf(v) === "marked" ? v : null))
  .reset(scanPromptClosed);
$weighing
  .on(scanFx.doneData, (s, r) => (r.kind === "weigh" ? r.view : s))
  .on(productPicked, (_, v) => (kindOf(v) === "weighed" && v.price !== null ? v : null))
  .reset(weightEntered, scanPromptClosed);
$scanError
  .on(scanFx.doneData, (_, r) => (r.kind === "error" ? r.error : null))
  .on(scanFx.failData, () => ({ code: "PRODUCT_NOT_FOUND" }))
  .on(productPicked, (_, v) => (priced(v) && kindOf(v) !== "marked" ? priced(v) : null))
  .reset(scanErrorDismissed, lineAdded);

// tile click: piece goods → +1 line; weighed → $weighing dialog; marked → $awaitingMarking prompt
sample({
  clock: productPicked,
  filter: (v) => kindOf(v) === "piece" && v.price !== null,
  fn: (v) => toLine(v, "1.000"),
  target: lineAdded,
});
sample({
  clock: weightEntered,
  filter: ({ view, qty }) => parseQty(qty, true) !== null && view.price !== null,
  fn: ({ view, qty }) => toLine(view, parseQty(qty, true) ?? "1.000"),
  target: lineAdded,
});

// an unexpected failure is shown as «Mahsulot topilmadi» — keep the cause visible for support
scanFx.failData.watch((error) => console.error("POS scan failed", error));

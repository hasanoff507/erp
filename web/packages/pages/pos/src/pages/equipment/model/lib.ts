/**
 * POS-16 pure helpers (07 POS-16, 24 §6.1/§6.3): printer form ↔ settings, LAN address rule per transport,
 * scale-template rows with a worked example (EAN-13 `PP CCCCC VVVVV K`), scanner-test classification.
 */
import { ean13CheckDigit } from "@shared/lib/barcode";
import { parseLanAddress, type PrinterSettings, type PrinterTransport } from "@shared/lib/printer";
import {
  DEFAULT_WEIGHT_BARCODE_TEMPLATES,
  parseWeightBarcode,
  type WeightBarcodeTemplate,
} from "@shared/lib/scale";

import { classifyCode, type CodeKind } from "#/features/wh-scan/index.ts";

export type CatalogView = "grid" | "list";
export const CATALOG_VIEW_KEY = "pos.catalog_view";

/** Transports that need `printer.lan_address` and their default port (24 §6.1). */
export const LAN_TRANSPORTS: Partial<Record<PrinterTransport, number>> = {
  agent_raw: 9100,
  http_epos: 80,
  http_webprnt: 80,
};

/** Shown in the radio list, in the 07 POS-16 maket order. `cloud` is Bosqich 5 (server queue) — never enabled. */
export const TRANSPORT_ORDER: readonly PrinterTransport[] = [
  "webserial",
  "webusb",
  "webbluetooth",
  "system_print",
  "agent_raw",
  "http_epos",
  "http_webprnt",
  "cloud",
];

export function transportEnabled(t: PrinterTransport, available: readonly PrinterTransport[]): boolean {
  return t !== "cloud" && available.includes(t);
}

export type PrinterFormError = "transport_required" | "lan_address_invalid";

export function printerFormErrors(form: PrinterSettings): PrinterFormError[] {
  if (!form.transport) return ["transport_required"];
  const port = LAN_TRANSPORTS[form.transport];
  if (port !== undefined && !parseLanAddress(form.lanAddress, port)) return ["lan_address_invalid"];
  return [];
}

export interface ScaleRow {
  prefixes: string[];
  kind: WeightBarcodeTemplate["value_kind"];
  itemLen: number;
  valueLen: number;
  decimals: number;
  enabled: boolean;
  /** Example label code and what it decodes to (qty kg or amount so'm). */
  example: string;
  decoded: string;
}

function exampleCode(t: WeightBarcodeTemplate): string {
  const prefix = t.prefixes[0] ?? "22";
  const plu = "12345678".slice(0, t.item_code_len).padStart(t.item_code_len, "0");
  const value = (t.value_kind === "WEIGHT" ? "01250" : "11875")
    .padStart(t.value_len, "0")
    .slice(-t.value_len);
  const first12 = `${prefix}${plu}${value}`.slice(0, 12);
  return first12.length === 12 ? first12 + ean13CheckDigit(first12) : first12;
}

export function scaleRows(templates: readonly WeightBarcodeTemplate[] | null | undefined): ScaleRow[] {
  const list = templates && templates.length ? templates : DEFAULT_WEIGHT_BARCODE_TEMPLATES;
  return list.map((t) => {
    const example = exampleCode(t);
    const parsed = parseWeightBarcode(example, [{ ...t, enabled: true }]);
    const decoded = !parsed.ok ? "" : parsed.kind === "WEIGHT" ? parsed.qty : parsed.amount;
    return {
      prefixes: [...t.prefixes],
      kind: t.value_kind,
      itemLen: t.item_code_len,
      valueLen: t.value_len,
      decimals: t.decimals,
      enabled: t.enabled !== false,
      example,
      decoded,
    };
  });
}

export type ScanTestKind = CodeKind | "weight";

export interface ScanTestResult {
  code: string;
  kind: ScanTestKind;
  /** Weight label: PLU and qty / amount. */
  weight: { productCode: string; value: string; valueKind: "WEIGHT" | "AMOUNT" } | null;
}

/** «Skaner sinovi»: the code as read and its type (EAN-13, DataMatrix GS1, scale label…) — 07 POS-16. */
export function describeScan(
  code: string,
  templates: readonly WeightBarcodeTemplate[] | null | undefined,
): ScanTestResult {
  const trimmed = code.trim().slice(0, 256);
  const weight = parseWeightBarcode(trimmed, templates);
  if (weight.ok) {
    return {
      code: trimmed,
      kind: "weight",
      weight: {
        productCode: weight.productCode,
        value: weight.kind === "WEIGHT" ? weight.qty : weight.amount,
        valueKind: weight.kind,
      },
    };
  }
  return { code: trimmed, kind: classifyCode(trimmed), weight: null };
}

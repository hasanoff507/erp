import { addMoney, money, subtractMoney, type Money } from "@shared/lib/money";
import type { ListEinvoicesParams } from "@shared/models";

import {
  IN_STATUS_FILTERS,
  PAGE_LIMIT,
  RISK_FILTERS,
  TABS,
  type EInvoice,
  type InFilters,
  type InStatusFilter,
  type Kpis,
  type ListRequest,
  type RiskFilter,
  type Tab,
} from "../types/index.ts";

export function isTab(value: string | null): value is Tab {
  return value !== null && (TABS as readonly string[]).includes(value);
}

export function isRiskFilter(value: string): value is RiskFilter {
  return (RISK_FILTERS as readonly string[]).includes(value);
}

export function isInStatusFilter(value: string): value is InStatusFilter {
  return (IN_STATUS_FILTERS as readonly string[]).includes(value);
}

/** `GET /einvoices?direction=in&risk_flag=&status=` (19 §19). */
export function inboundParams(req: ListRequest<InFilters>): ListEinvoicesParams {
  return {
    direction: "in",
    ...(req.filters.risk === "all" ? {} : { risk_flag: req.filters.risk }),
    ...(req.filters.status === "all" ? {} : { status: req.filters.status }),
    ...(req.cursor ? { cursor: req.cursor } : {}),
    limit: PAGE_LIMIT,
  };
}

const ZERO = "0.00";

function sum(values: readonly (string | null)[]): Money {
  return addMoney(money(ZERO), ...values.filter((v): v is string => v !== null).map((v) => money(v)));
}

/**
 * 07 BO-15 KPI cards from the unfiltered pages: incoming of the month (count, total, VAT), awaiting signature
 * (`received`), deferred VAT credit (`red`/`unknown`, not rejected — VM 830, 13 §2.8), outgoing not sent
 * (`draft`/`signed`).
 */
export function computeKpis(
  inbound: readonly EInvoice[],
  outbound: readonly EInvoice[],
  month: string,
): Kpis {
  const ofMonth = inbound.filter((e) => (e.doc_date ?? e.created_at).startsWith(month));
  const deferred = inbound.filter(
    (e) =>
      (e.risk_flag === "red" || e.risk_flag === "unknown") &&
      e.status !== "rejected" &&
      e.status !== "cancelled",
  );
  return {
    inCount: ofMonth.length,
    inTotal: sum(ofMonth.map((e) => e.total_amount)),
    inVat: sum(ofMonth.map((e) => e.vat_amount)),
    awaitingSignature: inbound.filter((e) => e.status === "received").length,
    deferredVat: sum(deferred.map((e) => e.vat_amount)),
    outUnsent: outbound.filter((e) => e.status === "draft" || e.status === "signed").length,
  };
}

/** VAT-exclusive total of an e-invoice (total − VAT). */
export function netOf(e: Pick<EInvoice, "total_amount" | "vat_amount">): string | null {
  if (e.total_amount === null) return null;
  return subtractMoney(money(e.total_amount), money(e.vat_amount ?? ZERO));
}

export interface PayloadLine {
  line_no: number;
  name: string;
  qty: string;
  net_amount: string;
  vat_rate: string;
  vat_amount: string;
  total_amount: string;
}

function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : typeof value === "number" ? String(value) : fallback;
}

/** `payload.lines[]` of an e-invoice (19 §19: tovar qatorlari, MXIK, QQS) in a safe shape. */
export function payloadLines(payload: Record<string, unknown> | undefined): PayloadLine[] {
  const lines = payload?.lines;
  if (!Array.isArray(lines)) return [];
  return lines.map((raw: unknown, index) => {
    const line = (raw ?? {}) as Record<string, unknown>;
    const net = str(line.net_amount, ZERO);
    const vat = str(line.vat_amount, ZERO);
    return {
      line_no: typeof line.line_no === "number" ? line.line_no : index + 1,
      name: str(line.name, "—"),
      qty: str(line.qty, "0.000"),
      net_amount: net,
      vat_rate: str(line.vat_rate, "0.00"),
      vat_amount: vat,
      total_amount: str(line.total_amount, addMoney(money(net), money(vat))),
    };
  });
}

/** `"1 200,5"` / `"1200.5"` → `"1200.500"` (qty 3 dp) or null; no Number() on quantities (qaror #57). */
export function normalizeDecimal(input: string, places: number): string | null {
  const compact = input.replace(/[\s\u00a0]/g, "").replace(",", ".");
  if (!/^\d{1,14}(\.\d+)?$/.test(compact)) return null;
  const [whole = "0", frac = ""] = compact.split(".");
  if (frac.length > places) return null;
  return `${whole}.${frac.padEnd(places, "0")}`;
}

import { addMoney, compareMoney, money, subtractMoney, toDecimal, type Money } from "@shared/lib/money";
import type { ListBankSettlementsParams } from "@shared/models";

import { addDays } from "#/shared/lib/effect.ts";
import { typedMoney, ZERO } from "#/shared/lib/money.ts";

import {
  BANK_REF_MAX,
  COMMENT_MAX,
  METHODS,
  PAGE_SIZE,
  STATUSES,
  type BankForm,
  type BankFormErrors,
  type BankSettlementIn,
  type BankSettlementPatch,
  type ListRequest,
  type Method,
  type PreviewLine,
  type Settlement,
  type SettlementDetail,
  type SettlementStatus,
  type TransitBalance,
  type TransitRow,
} from "../types/index.ts";

export function isMethod(v: string | null): v is Method {
  return v !== null && (METHODS as readonly string[]).includes(v);
}

export function isSettlementStatus(v: string | null): v is SettlementStatus {
  return v !== null && (STATUSES as readonly string[]).includes(v);
}

export function toListParams(req: ListRequest): ListBankSettlementsParams {
  const f = req.filters;
  return {
    ...(f.branchId ? { branch_id: f.branchId } : {}),
    ...(f.method ? { method: f.method } : {}),
    ...(f.status ? { status: f.status } : {}),
    ...(f.source ? { source: f.source } : {}),
    ...(f.from ? { doc_date__gte: f.from } : {}),
    ...(f.to ? { doc_date__lte: f.to } : {}),
    ...(req.cursor ? { cursor: req.cursor } : {}),
    limit: PAGE_SIZE,
  };
}

/** New document: today, the period «kecha – kecha» (07 BO-24 defaults). */
export function emptyBankForm(today: string, branchId: string | null): BankForm {
  const yesterday = addDays(today, -1);
  return {
    branchId: branchId ?? "",
    docDate: today,
    method: null,
    settledFrom: yesterday,
    settledTo: yesterday,
    gross: "",
    commission: "0.00",
    variance: "0.00",
    bankRef: "",
    comment: "",
    attachment: null,
  };
}

export function formOf(d: SettlementDetail): BankForm {
  return {
    branchId: d.branch_id,
    docDate: d.doc_date,
    method: d.method,
    settledFrom: d.settled_from,
    settledTo: d.settled_to,
    gross: d.gross_amount,
    commission: d.commission_amount,
    variance: d.variance_amount,
    bankRef: d.bank_ref ?? "",
    comment: d.comment ?? "",
    attachment: null,
  };
}

const m = (v: string): Money => typedMoney(v) ?? ZERO;

/** `net = gross − commission + variance` (shown with @shared/lib/money; the server generates it). */
export function netAmount(form: Pick<BankForm, "gross" | "commission" | "variance" | "method">): Money {
  const variance = form.method === "collection" ? m(form.variance) : ZERO;
  return addMoney(subtractMoney(m(form.gross), m(form.commission)), variance);
}

/** Commission share of gross, percent with two decimals ("1.00"); null when gross is 0. */
export function commissionPct(gross: string, commission: string): string | null {
  const g = m(gross);
  if (compareMoney(g, ZERO) <= 0) return null;
  return toDecimal(m(commission)).times(100).dividedBy(toDecimal(g)).toFixed(2);
}

/**
 * Commission expense account (13 §2.18a): card / UzQR → 9430; Click / Payme / Uzum → the tenant setting
 * `payment_org_commission_account` (default 9430 — the preview assumes the default); collection → 9410.
 */
export function commissionAccount(method: Method): string {
  return method === "collection" ? "9410" : "9430";
}

/** 13 §2.18a posting preview (only rows with an amount; Kt 5710 total = gross). */
export function previewLines(
  form: Pick<BankForm, "gross" | "commission" | "variance" | "method">,
): PreviewLine[] {
  if (!form.method) return [];
  const lines: PreviewLine[] = [];
  const net = netAmount(form);
  if (compareMoney(net, ZERO) > 0) lines.push({ dt: "5110", kt: "5710", amount: net });
  const commission = m(form.commission);
  if (compareMoney(commission, ZERO) > 0)
    lines.push({ dt: commissionAccount(form.method), kt: "5710", amount: commission });
  if (form.method === "collection") {
    const variance = m(form.variance);
    const sign = compareMoney(variance, ZERO);
    if (sign < 0) lines.push({ dt: "5910", kt: "5710", amount: subtractMoney(ZERO, variance) });
    if (sign > 0) lines.push({ dt: "5710", kt: "9390", amount: variance });
  }
  return lines;
}

/** Field checks of 07 BO-24 / 20 #55c (keys in `common`; the transit cap is checked by the server). */
export function validateBankForm(form: BankForm, today: string): BankFormErrors {
  const e: BankFormErrors = {};
  if (form.branchId === "") e.branchId = "validation.required";
  if (!form.method) e.method = "validation.required";
  if (form.docDate === "") e.docDate = "validation.required";
  else if (form.docDate > today) e.docDate = "validation.doc_date_in_future";
  if (form.settledFrom === "") e.settledFrom = "validation.required";
  if (form.settledTo === "") e.settledTo = "validation.required";
  if (form.settledFrom && form.settledTo && form.settledFrom > form.settledTo)
    e.settledTo = "validation.date_range";
  else if (form.settledTo && form.docDate && form.settledTo > form.docDate)
    e.settledTo = "validation.date_range";
  const gross = typedMoney(form.gross);
  if (form.gross.trim() === "") e.gross = "validation.required";
  else if (!gross || compareMoney(gross, ZERO) <= 0) e.gross = "validation.must_be_positive";
  const commission = typedMoney(form.commission === "" ? "0" : form.commission);
  if (!commission || compareMoney(commission, ZERO) < 0) e.commission = "validation.non_negative";
  else if (gross && compareMoney(commission, gross) >= 0)
    e.commission = "validation.bank_commission_ge_gross";
  if (form.method !== "collection" && compareMoney(m(form.variance), ZERO) !== 0)
    e.variance = "validation.not_allowed";
  else if (gross && !e.commission && compareMoney(netAmount(form), ZERO) <= 0)
    e.variance = "validation.must_be_positive";
  if (form.bankRef.length > BANK_REF_MAX) e.bankRef = "validation.max_length";
  if (form.comment.length > COMMENT_MAX) e.comment = "validation.max_length";
  return e;
}

const opt = (v: string): string | null => (v.trim() === "" ? null : v.trim());

export function toCreateBody(form: BankForm): BankSettlementIn {
  return {
    branch_id: form.branchId,
    doc_date: form.docDate,
    method: form.method ?? "card",
    settled_from: form.settledFrom,
    settled_to: form.settledTo,
    gross_amount: m(form.gross),
    commission_amount: m(form.commission),
    variance_amount: form.method === "collection" ? m(form.variance) : ZERO,
    bank_ref: opt(form.bankRef),
    attachment_id: form.attachment?.id ?? null,
    comment: opt(form.comment),
  };
}

/** 20 #55h: only the editable fields that changed + `version` (branch / method / date are fixed). */
export function toPatchBody(form: BankForm, d: SettlementDetail): BankSettlementPatch {
  const patch: BankSettlementPatch = { version: d.version };
  if (m(form.gross) !== d.gross_amount) patch.gross_amount = m(form.gross);
  if (m(form.commission) !== d.commission_amount) patch.commission_amount = m(form.commission);
  const variance = form.method === "collection" ? m(form.variance) : ZERO;
  if (variance !== d.variance_amount) patch.variance_amount = variance;
  if (form.settledFrom !== d.settled_from) patch.settled_from = form.settledFrom;
  if (form.settledTo !== d.settled_to) patch.settled_to = form.settledTo;
  if (opt(form.bankRef) !== d.bank_ref) patch.bank_ref = opt(form.bankRef);
  if (opt(form.comment) !== d.comment) patch.comment = opt(form.comment);
  return patch;
}

export const isPatchEmpty = (p: BankSettlementPatch): boolean => Object.keys(p).length === 1;

/** «Yo'ldagi pul qoldig'i» of branch × method (the gross suggestion), or null. */
export function transitFor(
  items: readonly TransitBalance[],
  branchId: string,
  method: Method | null,
): Money | null {
  if (!method) return null;
  const row = items.find((i) => i.branch_id === branchId && i.method === method);
  return row ? money(row.balance) : null;
}

/** Transit panel rows: method × branch (card split into integrated / terminal-less when known). */
export function transitRows(items: readonly TransitBalance[]): {
  rows: TransitRow[];
  branches: string[];
  totals: Record<string, string>;
  total: string;
} {
  const branches = [...new Set(items.map((i) => i.branch_id))];
  const rows: TransitRow[] = [];
  const push = (key: TransitRow["key"], pick: (i: TransitBalance) => string | null) => {
    const byBranch: Record<string, string> = {};
    let oldest: string | null = null;
    for (const i of items) {
      const v = pick(i);
      if (v === null) continue;
      byBranch[i.branch_id] = addMoney(money(byBranch[i.branch_id] ?? "0"), money(v));
      if (i.oldest_unsettled_date && (!oldest || i.oldest_unsettled_date < oldest))
        oldest = i.oldest_unsettled_date;
    }
    if (Object.keys(byBranch).length === 0) return;
    rows.push({
      key,
      byBranch,
      total: addMoney(ZERO, ...Object.values(byBranch).map((v) => money(v))),
      oldest,
    });
  };
  for (const method of METHODS) {
    if (method === "card" && items.some((i) => i.method === "card" && i.card_breakdown)) {
      push("card_integrated", (i) =>
        i.method === "card" ? (i.card_breakdown?.integrated ?? i.balance) : null,
      );
      push("card_manual", (i) => (i.method === "card" ? (i.card_breakdown?.manual ?? "0.00") : null));
    } else push(method, (i) => (i.method === method ? i.balance : null));
  }
  const totals: Record<string, string> = {};
  for (const b of branches)
    totals[b] = addMoney(ZERO, ...items.filter((i) => i.branch_id === b).map((i) => money(i.balance)));
  return { rows, branches, totals, total: addMoney(ZERO, ...items.map((i) => money(i.balance))) };
}

/** Footer «O'tkazilgan jami» over the loaded posted rows. */
export function postedTotals(list: readonly Settlement[]): {
  count: number;
  gross: Money;
  commission: Money;
  variance: Money;
  net: Money;
} {
  const posted = list.filter((s) => s.status === "posted");
  const sum = (pick: (s: Settlement) => string) => addMoney(ZERO, ...posted.map((s) => money(pick(s))));
  return {
    count: posted.length,
    gross: sum((s) => s.gross_amount),
    commission: sum((s) => s.commission_amount),
    variance: sum((s) => s.variance_amount),
    net: sum((s) => s.net_amount),
  };
}

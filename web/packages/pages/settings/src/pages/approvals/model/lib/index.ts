import { dayjs } from "@shared/lib/date";
import type { ListRequestsParams } from "@shared/models";

import {
  APPROVAL_KINDS,
  CASH_REASONS,
  DOC_TYPES,
  EXPENSE_SOURCES,
  MANUAL_REASONS,
  PAGE_SIZE,
  PERCENT_KINDS,
  QUEUE_TABS,
  type ApprovalKind,
  type ApprovalRequest,
  type ContextLine,
  type LinkedDocType,
  type ListRequest,
  type QueueTab,
} from "../types/index.ts";

export function toListParams(req: ListRequest): ListRequestsParams {
  return { status: req.tab, ...(req.cursor ? { cursor: req.cursor } : {}), limit: PAGE_SIZE };
}

export function isQueueTab(value: string | null): value is QueueTab {
  return value !== null && (QUEUE_TABS as readonly string[]).includes(value);
}

export function isApprovalKind(value: string | null): value is ApprovalKind {
  return value !== null && (APPROVAL_KINDS as readonly string[]).includes(value);
}

/** Number of loaded requests per kind (filter chips «Chegirma 1»…). */
export function kindCounts(list: readonly ApprovalRequest[]): Record<ApprovalKind, number> {
  const counts = Object.fromEntries(APPROVAL_KINDS.map((k) => [k, 0])) as Record<ApprovalKind, number>;
  for (const r of list) counts[r.kind] += 1;
  return counts;
}

export function filterByKind(list: readonly ApprovalRequest[], kind: ApprovalKind | null): ApprovalRequest[] {
  return kind ? list.filter((r) => r.kind === kind) : [...list];
}

/** Requested value as shown: percent kinds → `{ pct }`, others → `{ amount }` (so'm), or nothing. */
export function requestedValue(
  r: Pick<ApprovalRequest, "kind" | "requested_value" | "context">,
): { pct: string } | { amount: string } | null {
  if (PERCENT_KINDS.includes(r.kind)) {
    const pct = r.requested_value ?? str(r.context.requested_pct);
    return pct ? { pct } : null;
  }
  const amount = r.requested_value ?? str(r.context.amount);
  return amount ? { amount } : null;
}

function str(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function oneOf<T extends string>(values: readonly T[], value: string | null): value is T {
  return value !== null && (values as readonly string[]).includes(value);
}

/** The label key of a linked document type (unknown → `other`). */
export function docTypeKey(docType: string): LinkedDocType | "other" {
  return oneOf(DOC_TYPES, docType) ? docType : "other";
}

/**
 * Readable lines of the `context` snapshot (18 §9.1 — kind-specific): the cash movement reason
 * (enum), the manual card reason (enum), free-text `reason`/`comment`, the number of `lines`.
 * Ids and unknown keys are not shown (raw server data never reaches the UI — 08 §11).
 */
export function contextLines(r: Pick<ApprovalRequest, "kind" | "context">): ContextLine[] {
  const c = r.context;
  const lines: ContextLine[] = [];
  const reason = str(c.reason);
  if (reason !== null) {
    if (r.kind === "cash_withdrawal_over_limit" && oneOf(CASH_REASONS, reason)) {
      lines.push({ key: "reason", value: reason });
    } else lines.push({ key: "comment", value: reason });
  }
  const manual = str(c.manual_reason);
  if (oneOf(MANUAL_REASONS, manual)) lines.push({ key: "manualReason", value: manual });
  const comment = str(c.comment) ?? str(c.note);
  if (comment !== null) lines.push({ key: "comment", value: comment });
  if (Array.isArray(c.lines) && c.lines.length > 0) lines.push({ key: "lines", count: c.lines.length });
  // B4: a big expense (20 #43 context) / a POS cash expense; a debt over the credit limit (18 §2.4).
  const category = str(c.category_name);
  if (category !== null) lines.push({ key: "category", value: category });
  const source = str(c.source);
  if (r.kind === "expense_over_limit" && oneOf(EXPENSE_SOURCES, source))
    lines.push({ key: "source", value: source });
  const docDate = str(c.doc_date);
  if (docDate !== null && /^\d{4}-\d{2}-\d{2}$/.test(docDate)) lines.push({ key: "docDate", value: docDate });
  const customer = str(c.counterparty_name) ?? str(c.customer_name);
  if (customer !== null) lines.push({ key: "customer", value: customer });
  const creditLimit = str(c.credit_limit);
  if (creditLimit !== null) lines.push({ key: "creditLimit", value: creditLimit });
  const currentDebt = str(c.receivable_balance) ?? str(c.current_debt);
  if (currentDebt !== null) lines.push({ key: "currentDebt", value: currentDebt });
  return lines;
}

/** Whole minutes left until `expires_at` (0 when already due). */
export function minutesLeft(expiresAt: string, now: number): number {
  const ms = Date.parse(expiresAt) - now;
  return ms <= 0 ? 0 : Math.ceil(ms / 60_000);
}

/** A `pending` request whose `expires_at` has passed (the server turns it into `expired` on read). */
export function isDue(r: Pick<ApprovalRequest, "status" | "expires_at">, now: number): boolean {
  return r.status === "pending" && Date.parse(r.expires_at) <= now;
}

/** «Bugun hal qilinganlar»: resolved on the local `today`, newest first, without duplicates. */
export function resolvedOn(list: readonly ApprovalRequest[], today: string): ApprovalRequest[] {
  const seen = new Set<string>();
  return list
    .filter((r) => r.resolved_at !== null && dayjs(r.resolved_at).format("YYYY-MM-DD") === today)
    .filter((r) => (seen.has(r.id) ? false : (seen.add(r.id), true)))
    .sort((a, b) => Date.parse(b.resolved_at ?? "") - Date.parse(a.resolved_at ?? ""));
}

/** A request decided here leaves the pending list at once (the next refresh confirms it). */
export function dropDecided(list: readonly ApprovalRequest[], id: string): ApprovalRequest[] {
  return list.filter((r) => r.id !== id || r.status !== "pending");
}

/** `record` without `id` (per-request error maps). */
export function without<T>(record: Readonly<Record<string, T>>, id: string): Record<string, T> {
  const rest: Record<string, T> = { ...record };
  delete rest[id];
  return rest;
}

/** PIN of 18 §9.4 (`^[0-9]{4,6}$`). */
export function isPinValid(pin: string): boolean {
  return /^[0-9]{4,6}$/.test(pin);
}

/** Rejection reason: 1–1000 chars after trim (18 §9.5, backend `RejectIn`). */
export function isReasonValid(reason: string): boolean {
  const t = reason.trim();
  return t.length > 0 && t.length <= 1000;
}

/** Errors after which the card is stale: the request was decided/expired elsewhere → reload. */
export function isStaleDecision(e: { status: number | null; code: string }): boolean {
  return (
    e.status === 404 ||
    e.code === "APPROVAL_REQUEST_ALREADY_RESOLVED" ||
    e.code === "APPROVAL_REQUEST_EXPIRED"
  );
}

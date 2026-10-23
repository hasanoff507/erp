/**
 * BO-21 ④ «Boshlang'ich qarzlar» (07 BO-21 `debts[]` — Jadval/Excel: ism + telefon + summa; US-M08-07; 18 §12.4):
 * each row → `POST /debt-openings {counterparty:{name, phone, kind:"person"}, amount, direction, due_date?}` →
 * `POST /debt-openings/{id}/post` (13 §2.13 — posted on `go_live_date − 1`). Rows can be typed or pasted from
 * Excel (tab separated: name, phone, amount[, due date]). Rows already saved are never sent twice; a draft
 * whose post failed is cancelled (best effort). `validation.go_live_date_missing` stops the run (every row
 * would fail the same way). Permission: the Owner (`stock.opening.manage` / `debts.limit.manage`).
 */
import { api, toApiError, type ApiError } from "@shared/api";
import { compareMoney, isMoney, money, type Money } from "@shared/lib/money";
import { isCompleteNationalPhone, nationalDigits, toE164 } from "@shared/lib/phone";
import type { DebtOpeningCreate, DebtOpeningOut } from "@shared/models";

export type DebtDirection = "receivable" | "payable";

export interface DebtRowDraft {
  key: string;
  name: string;
  /** National digits ("901234567"). */
  phone: string;
  /** Decimal string ("350000.00") or "". */
  amount: string;
  /** `YYYY-MM-DD` or "". */
  dueDate: string;
}

export type RowField = "name" | "phone" | "amount" | "dueDate";
export type RowErrors = Partial<Record<RowField, string>>;

export type RowResult = { ok: true; id: string } | { ok: false; error: ApiError };

export const MAX_ROWS = 500;

let serial = 0;
export function newRow(patch: Partial<DebtRowDraft> = {}): DebtRowDraft {
  serial += 1;
  return { key: `r${serial}`, name: "", phone: "", amount: "", dueDate: "", ...patch };
}

/**
 * "350 000", "350000,5", "350.000,50", "350.000", "1.500.000" → "350000.00" / "350000.50" / "1500000.00";
 * "" when not a positive amount. So'm has at most 2 decimals, so a dot followed by exactly three digits (no
 * comma in the string) is always a thousands separator ("350.000" = 350 000, not 350.00); "350.5" stays 350.50.
 */
export function normalizeAmount(text: string): string {
  let s = text.replace(/[\s\u00a0']/g, "").replace(/so'?m|сум|uzs/gi, "");
  if (!s) return "";
  if (/^\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, "");
  else if (s.includes(",") && s.includes("."))
    s =
      s.lastIndexOf(",") > s.lastIndexOf(".") ? s.replace(/\./g, "").replace(",", ".") : s.replace(/,/g, "");
  else if (s.includes(",")) s = /,\d{1,2}$/.test(s) ? s.replace(",", ".") : s.replace(/,/g, "");
  if (!isMoney(s)) return "";
  const m = money(s);
  return compareMoney(m, "0.00" as Money) > 0 ? m : "";
}

/** "31.12.2026" / "2026-12-31" → "2026-12-31"; anything else → "". */
export function normalizeDate(text: string): string {
  const t = text.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(t)) return t;
  const m = /^(\d{1,2})[./](\d{1,2})[./](\d{4})$/.exec(t);
  if (!m) return "";
  return `${m[3]}-${(m[2] ?? "").padStart(2, "0")}-${(m[1] ?? "").padStart(2, "0")}`;
}

/** Rows pasted from Excel / Google Sheets (tab separated; `;` also accepted); a header row is skipped. */
export function parsePasted(text: string): DebtRowDraft[] {
  const rows: DebtRowDraft[] = [];
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue;
    const cells = (line.includes("\t") ? line.split("\t") : line.split(";")).map((c) => c.trim());
    const [name = "", phone = "", amount = "", due = ""] = cells;
    const parsedAmount = normalizeAmount(amount);
    if (!parsedAmount && rows.length === 0 && !/\d/.test(phone)) continue; // header
    rows.push(
      newRow({ name, phone: nationalDigits(phone), amount: parsedAmount, dueDate: normalizeDate(due) }),
    );
    if (rows.length >= MAX_ROWS) break;
  }
  return rows;
}

export function isBlank(row: DebtRowDraft): boolean {
  return !row.name.trim() && !row.phone && !row.amount;
}

export function validateRow(row: DebtRowDraft, direction: DebtDirection): RowErrors {
  const errors: RowErrors = {};
  if (!row.name.trim()) errors.name = "validation.required";
  if (!row.phone && direction === "receivable") errors.phone = "validation.required";
  else if (row.phone && !isCompleteNationalPhone(row.phone)) errors.phone = "validation.phone_uz";
  if (!row.amount || !isMoney(row.amount) || compareMoney(money(row.amount), "0.00" as Money) <= 0) {
    errors.amount = "validation.required";
  }
  return errors;
}

export function toOpeningBody(row: DebtRowDraft, direction: DebtDirection): DebtOpeningCreate {
  return {
    counterparty: {
      name: row.name.trim().slice(0, 255),
      phone: row.phone ? toE164(row.phone) : null,
      kind: "person",
    },
    amount: money(row.amount),
    direction,
    due_date: row.dueDate || null,
  };
}

export interface OpeningDebtsDeps {
  create: (body: DebtOpeningCreate) => Promise<DebtOpeningOut>;
  post: (id: string) => Promise<DebtOpeningOut>;
  cancel: (id: string) => Promise<unknown>;
}

export const defaultDeps: OpeningDebtsDeps = {
  create: (body) => api.debts.createDebtOpening(body),
  post: (id) => api.debts.postDebtOpening(id),
  cancel: (id) => api.debts.cancelDebtOpening(id, { reason: "post failed" }),
};

/** Sends the not-yet-saved valid rows one by one; returns the result per row key. */
export async function submitRows(
  rows: readonly DebtRowDraft[],
  direction: DebtDirection,
  saved: ReadonlySet<string>,
  deps: OpeningDebtsDeps = defaultDeps,
): Promise<Record<string, RowResult>> {
  const out: Record<string, RowResult> = {};
  for (const row of rows) {
    if (saved.has(row.key) || isBlank(row) || Object.keys(validateRow(row, direction)).length > 0) continue;
    let draftId: string | null = null;
    try {
      const draft = await deps.create(toOpeningBody(row, direction));
      draftId = draft.id;
      const posted = await deps.post(draft.id);
      out[row.key] = { ok: true, id: posted.id };
    } catch (e) {
      if (draftId) await deps.cancel(draftId).catch(() => undefined);
      const error = toApiError(e);
      out[row.key] = { ok: false, error };
      if (
        error.details.some((d) => d.messageKey === "validation.go_live_date_missing") ||
        error.messageKey === "validation.go_live_date_missing"
      )
        break;
    }
  }
  return out;
}

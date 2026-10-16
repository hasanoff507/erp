import { dayjs } from "@shared/lib/date";

import type { Branch, CashRegister, SettlementCategory } from "../types/index.ts";

/** Retail turnover-tax rate of a settlement category (SK 467, US-M14-04). */
export const SETTLEMENT_RATE: Readonly<Record<SettlementCategory, string>> = {
  city_100k_plus: "4",
  other: "2",
  remote_mountain: "1",
};

/** First day of the current month — the `valid_from` a PATCH category change gets (20 #33). */
export function currentMonthStart(today: Date = new Date()): string {
  return dayjs(today).startOf("month").format("YYYY-MM-DD");
}

/** `<input type="month">` value "2026-11" → "2026-11-01". */
export function monthToValidFrom(month: string): string {
  return `${month}-01`;
}

export function currentMonthValue(today: Date = new Date()): string {
  return dayjs(today).format("YYYY-MM");
}

/** Past months are refused by the server (20 #35); the current month is allowed. */
export function isPastMonth(month: string, today: Date = new Date()): boolean {
  return month < currentMonthValue(today);
}

export function upsertBranch(list: readonly Branch[], branch: Branch): Branch[] {
  const index = list.findIndex((b) => b.id === branch.id);
  if (index === -1) return [...list, branch];
  const next = [...list];
  next[index] = branch;
  return next;
}

export function patchById<T extends { id: string }>(list: readonly T[], id: string, patch: Partial<T>): T[] {
  return list.map((item) => (item.id === id ? { ...item, ...patch } : item));
}

/** The default branch first, then by code. */
export function sortBranches(list: readonly Branch[]): Branch[] {
  return [...list].sort((a, b) =>
    a.is_default === b.is_default ? a.code.localeCompare(b.code) : a.is_default ? -1 : 1,
  );
}

/** A register can sell fiscal receipts only after tax registration (SK 221) — shown as a warning chip. */
export function isRegisteredForTax(register: CashRegister): boolean {
  return register.ofd_status === "registered" || register.ofd_status === "active";
}

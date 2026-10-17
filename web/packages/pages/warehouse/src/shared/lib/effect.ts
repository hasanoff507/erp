import { createEffect } from "effector";

import { toApiError, type ApiError } from "@shared/api";
import { dayjs } from "@shared/lib/date";

/** An effect whose failure is always a normalised ApiError (24 §3). */
export function apiFx<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw toApiError(e);
    }
  });
}

/** Local calendar date `YYYY-MM-DD` (document dates). */
export function todayIso(): string {
  return dayjs().format("YYYY-MM-DD");
}

/** Whole days from `today` to `date` (both `YYYY-MM-DD`); negative = already past. */
export function daysUntil(date: string, today: string): number {
  return dayjs(date).startOf("day").diff(dayjs(today).startOf("day"), "day");
}

/** Reads every cursor page (`limit` 200) up to `maxPages`; `capped` = more rows were left unread. */
export async function readAllPages<T>(
  load: (cursor: string | null) => Promise<{ items: T[]; next_cursor: string | null }>,
  maxPages = 25,
): Promise<{ items: T[]; capped: boolean }> {
  const items: T[] = [];
  let cursor: string | null = null;
  for (let i = 0; i < maxPages; i += 1) {
    const page = await load(cursor);
    items.push(...page.items);
    cursor = page.next_cursor;
    if (cursor === null) return { items, capped: false };
  }
  return { items, capped: true };
}

export const PAGE_LIMIT = 50;
export const BULK_LIMIT = 200;

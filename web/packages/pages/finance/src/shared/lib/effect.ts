/** Effect helpers of the finance screens (24 §3: an effect's failure is always a normalised ApiError). */
import { createEffect } from "effector";

import { toApiError, type ApiError } from "@shared/api";
import { dayjs } from "@shared/lib/date";

export function apiFx<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw toApiError(e);
    }
  });
}

/** Local calendar date `YYYY-MM-DD` (document dates; Tashkent is the device zone). */
export function todayIso(): string {
  return dayjs().format("YYYY-MM-DD");
}

/** `YYYY-MM-DD` of the first day of the date's month. */
export function monthStart(date: string): string {
  return `${date.slice(0, 7)}-01`;
}

/** `YYYY-MM-DD` shifted by whole days. */
export function addDays(date: string, days: number): string {
  return dayjs(date).add(days, "day").format("YYYY-MM-DD");
}

export const PAGE_LIMIT = 50;
export type LoadStatus = "idle" | "loading" | "error";

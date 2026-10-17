import { dayjs } from "@shared/lib/date";
import { ALL_BRANCHES } from "@shared/state/session";

import {
  CHART_DAYS,
  type DashboardRequest,
  type DayBar,
  type SalesReport,
  type WeekRequest,
} from "../types/index.ts";

/** Topbar branch → report `branch_id`: «Barcha filiallar» / none chosen → `null` (consolidated). */
export function branchParam(active: string | null): string | null {
  return active && active !== ALL_BRANCHES ? active : null;
}

export function weekRange(today: string, branchId: string | null): WeekRequest {
  return {
    branchId,
    from: dayjs(today)
      .subtract(CHART_DAYS - 1, "day")
      .format("YYYY-MM-DD"),
    to: today,
  };
}

export function sameDashboardRequest(a: DashboardRequest, b: DashboardRequest): boolean {
  return a.period === b.period && a.branchId === b.branchId;
}

export function sameWeekRequest(a: WeekRequest, b: WeekRequest): boolean {
  return a.branchId === b.branchId && a.from === b.from && a.to === b.to;
}

/**
 * The 7 chart columns (today − 6 … today), zero for a day the report does not list; today is
 * highlighted. `weekday(date)` gives the short day label («Du», «Пн»).
 */
export function dayBars(
  report: SalesReport | null,
  today: string,
  weekday: (isoDate: string) => string,
): DayBar[] {
  const byDay = new Map((report?.rows ?? []).map((r) => [r.group_key, r.total_sales]));
  return Array.from({ length: CHART_DAYS }, (_, i) => {
    const day = dayjs(today)
      .subtract(CHART_DAYS - 1 - i, "day")
      .format("YYYY-MM-DD");
    return { key: day, label: weekday(day), value: byDay.get(day) ?? "0.00", highlight: day === today };
  });
}

/** Whole minutes since `at` (07 offline «Oxirgi yangilanish: N daqiqa oldin»). */
export function minutesSince(at: string, now: Date): number {
  return Math.max(0, Math.floor((now.getTime() - new Date(at).getTime()) / 60_000));
}

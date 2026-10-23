import type { DashboardOut, SalesReportOut } from "@shared/models";

export type Dashboard = DashboardOut;
export type SalesReport = SalesReportOut;

/** BO-02 `periodFilter` (07): Bugun / Hafta / Oy — API values today | week | month. */
export type DashboardPeriod = "today" | "week" | "month";

export const DASHBOARD_PERIODS: readonly DashboardPeriod[] = ["today", "week", "month"];

export type LoadStatus = "idle" | "loading" | "error";

/** «Savdo — oxirgi 7 kun» (07 BO-02): today − 6 … today. */
export const CHART_DAYS = 7;

export interface DashboardMountParams {
  /** Local date `YYYY-MM-DD`. */
  today: string;
}

export interface DashboardRequest {
  period: DashboardPeriod;
  /** `null` = «Barcha filiallar» (the caller's branches, 20 §17). */
  branchId: string | null;
}

export interface WeekRequest {
  branchId: string | null;
  from: string;
  to: string;
}

/** One column of the 7-day chart. */
export interface DayBar {
  key: string;
  label: string;
  value: string;
  highlight: boolean;
}

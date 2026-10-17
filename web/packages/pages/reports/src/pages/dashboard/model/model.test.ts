import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { $activeBranchId, ALL_BRANCHES } from "@shared/state/session";

import { alertHref, sortAlerts, type Alert } from "#/entities/alert/index.ts";
import { chartPoints, millions, percentChange, sharePercent } from "#/shared/lib/chart.ts";

import {
  $dashboard,
  $error,
  $period,
  $status,
  $week,
  dayBars,
  loadDashboardFx,
  loadWeekFx,
  minutesSince,
  pageMounted,
  pageUnmounted,
  periodChanged,
  type Dashboard,
  type DashboardRequest,
  type SalesReport,
  type WeekRequest,
} from "./index.ts";

const TODAY = "2026-10-17";

function dashboard(patch: Partial<Dashboard> = {}): Dashboard {
  return {
    period: "today",
    date_from: TODAY,
    date_to: TODAY,
    branch_id: null,
    total_sales: "4250000.00",
    gross_sales: "4300000.00",
    returns_total: "50000.00",
    receipt_count: 86,
    avg_receipt: "50000.00",
    previous_total_sales: "3800000.00",
    net_profit: "900000.00",
    cash_on_hand: "2100000.00",
    by_branch: [
      {
        branch_id: "b-1",
        name: "Chilonzor-3",
        sales: "3000000.00",
        receipt_count: 60,
        avg_receipt: "50000.00",
        profit: "600000.00",
        cash_on_hand: "1500000.00",
        low_stock_count: 3,
      },
      {
        branch_id: "b-2",
        name: "Yunusobod-1",
        sales: "1250000.00",
        receipt_count: 26,
        avg_receipt: "48076.92",
        profit: "300000.00",
        cash_on_hand: "600000.00",
        low_stock_count: 1,
      },
    ],
    top_products: [],
    receivables: null,
    stock: null,
    alerts: [],
    unsynced_devices: 0,
    data_complete: true,
    ...patch,
  };
}

function week(rows: [string, string][]): SalesReport {
  const row = (day: string, total: string) => ({
    group_key: day,
    group_label: null,
    total_sales: total,
    gross_sales: total,
    returns_total: "0.00",
    receipt_count: 1,
    avg_receipt: total,
  });
  return {
    date_from: "2026-10-11",
    date_to: TODAY,
    branch_id: null,
    group_by: "day",
    rows: rows.map(([d, v]) => row(d, v)),
    total: row("total", "0.00"),
    unsynced_devices: 0,
    data_complete: true,
  };
}

function scope(branch: string | null = ALL_BRANCHES) {
  const dashboardCalls: DashboardRequest[] = [];
  const weekCalls: WeekRequest[] = [];
  const s = fork({
    values: [[$activeBranchId, branch]],
    handlers: [
      [
        loadDashboardFx,
        (req: DashboardRequest) => {
          dashboardCalls.push(req);
          return dashboard({ period: req.period, branch_id: req.branchId });
        },
      ],
      [
        loadWeekFx,
        (req: WeekRequest) => {
          weekCalls.push(req);
          return week([[TODAY, "4250000.00"]]);
        },
      ],
    ],
  });
  return { s, dashboardCalls, weekCalls };
}

describe("BO-02 dashboard model (US-M12-01, US-M14-01, QT-M14-01)", () => {
  it("mount reads «Bugun» for «Barcha filiallar» and the last 7 days", async () => {
    const { s, dashboardCalls, weekCalls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    expect(dashboardCalls).toEqual([{ period: "today", branchId: null }]);
    expect(weekCalls).toEqual([{ branchId: null, from: "2026-10-11", to: TODAY }]);
    expect(s.getState($status)).toBe("idle");
    // QT-M14-01: each branch separately and the total.
    expect(s.getState($dashboard)?.by_branch.map((b) => b.name)).toEqual(["Chilonzor-3", "Yunusobod-1"]);
    expect(s.getState($dashboard)?.total_sales).toBe("4250000.00");
    expect(s.getState($week)?.rows).toHaveLength(1);
  });

  it("the period switch re-reads only the dashboard; mount resets it to «Bugun»", async () => {
    const { s, dashboardCalls, weekCalls } = scope("b-1");
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    await allSettled(periodChanged, { scope: s, params: "week" });
    expect(s.getState($period)).toBe("week");
    expect(dashboardCalls.at(-1)).toEqual({ period: "week", branchId: "b-1" });
    expect(weekCalls).toHaveLength(1);
    await allSettled(pageUnmounted, { scope: s });
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    expect(s.getState($period)).toBe("today");
  });

  it("another topbar branch re-reads both; an older answer is dropped", async () => {
    const { s, dashboardCalls, weekCalls } = scope("b-1");
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    await allSettled($activeBranchId, { scope: s, params: "b-2" });
    expect(dashboardCalls.at(-1)).toEqual({ period: "today", branchId: "b-2" });
    expect(weekCalls.at(-1)?.branchId).toBe("b-2");
    expect(s.getState($dashboard)?.branch_id).toBe("b-2");
  });

  it("a late answer for the previous branch does not replace the current one", async () => {
    let releaseFirst: (() => void) | null = null;
    const s = fork({
      values: [[$activeBranchId, "b-1"]],
      handlers: [
        [
          loadDashboardFx,
          (req: DashboardRequest) =>
            req.branchId === "b-1"
              ? new Promise<Dashboard>((resolve) => {
                  releaseFirst = () => resolve(dashboard({ branch_id: "b-1" }));
                })
              : dashboard({ branch_id: req.branchId }),
        ],
        [loadWeekFx, () => week([])],
      ],
    });
    const mounting = allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    await new Promise((r) => setTimeout(r, 0));
    const switching = allSettled($activeBranchId, { scope: s, params: "b-2" });
    await new Promise((r) => setTimeout(r, 0));
    (releaseFirst as (() => void) | null)?.();
    await Promise.all([mounting, switching]);
    expect(s.getState($dashboard)?.branch_id).toBe("b-2");
  });

  it("a failed read shows the error (07 «hisoblash xatosi»)", async () => {
    const s = fork({
      handlers: [
        [
          loadDashboardFx,
          () => {
            throw new Error("boom");
          },
        ],
        [loadWeekFx, () => week([])],
      ],
    });
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    expect(s.getState($status)).toBe("error");
    expect(s.getState($error)).not.toBeNull();
  });
});

describe("BO-02 lib", () => {
  it("7 chart columns: missing days are zero, today highlighted", () => {
    const bars = dayBars(
      week([
        ["2026-10-15", "1200000.00"],
        [TODAY, "4250000.00"],
      ]),
      TODAY,
      (d) => d.slice(8),
    );
    expect(bars.map((b) => b.key)).toEqual([
      "2026-10-11",
      "2026-10-12",
      "2026-10-13",
      "2026-10-14",
      "2026-10-15",
      "2026-10-16",
      TODAY,
    ]);
    expect(bars.map((b) => b.value)).toEqual([
      "0.00",
      "0.00",
      "0.00",
      "0.00",
      "1200000.00",
      "0.00",
      "4250000.00",
    ]);
    expect(bars.filter((b) => b.highlight).map((b) => b.key)).toEqual([TODAY]);
  });

  it("bar heights, «mln so'm» labels, change vs previous, shares", () => {
    const heights = chartPoints([
      { key: "a", label: "a", value: "4000000.00" },
      { key: "b", label: "b", value: "1000000.00" },
      { key: "c", label: "c", value: "0.00" },
      { key: "d", label: "d", value: "-5000.00" },
    ]).map((b) => b.amount);
    expect(heights).toEqual([4000000, 1000000, 0, 0]);
    expect(millions("4250000.00")).toBe("4,3");
    expect(millions("0.00")).toBe("0");
    expect(millions("20000.00")).toBe("0,1");
    expect(millions("125400000.00")).toBe("125");
    expect(percentChange("4250000.00", "3800000.00")).toBe("11.8");
    expect(percentChange("3000000.00", "4000000.00")).toBe("-25.0");
    expect(percentChange("100.00", "0.00")).toBeNull();
    expect(sharePercent("12.000", "40.000")).toBe(30);
    expect(sharePercent("1", "0")).toBe(0);
    expect(minutesSince("2026-10-17T10:00:00Z", new Date("2026-10-17T10:18:30Z"))).toBe(18);
  });

  it("alerts: critical first, only in-app links", () => {
    const a = (type: string, severity: Alert["severity"]): Alert => ({
      type,
      severity,
      message_key: `reports.alerts.${type}`,
      count: 1,
      amount: null,
      route: "/app/approvals",
    });
    expect(
      sortAlerts([
        a("pending_approvals", "info"),
        a("low_stock", "warning"),
        a("fiscal_unacked", "critical"),
      ]).map((x) => x.type),
    ).toEqual(["fiscal_unacked", "low_stock", "pending_approvals"]);
    expect(alertHref({ route: "/app/warehouse/stock?lowStockOnly=1" })).toBe(
      "/app/warehouse/stock?lowStockOnly=1",
    );
    expect(alertHref({ route: "https://evil.example" })).toBe("/app/dashboard");
  });
});

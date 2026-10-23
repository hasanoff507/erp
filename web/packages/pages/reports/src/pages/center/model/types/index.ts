import type {
  BalanceSheetOut,
  CashHistoryItem,
  CashMovementOut,
  CashRegisterOut,
  DebtsAgingOut,
  DiscountReportOut,
  ProfitAndLossOut,
  SalesReportOut,
  ShiftOut,
  StockAsOfOut,
  StockReportOut,
  TopProductsOut,
  TrialBalanceOut,
  VatMoveOut,
  VatMovePage,
} from "@shared/models";

export type ShiftRow = CashHistoryItem;
export type CashMovement = CashMovementOut;
export type CashRegister = CashRegisterOut;
export type Shift = ShiftOut;
export type VatMove = VatMoveOut;
export type { VatMovePage };
export type SalesReport = SalesReportOut;
export type TopProducts = TopProductsOut;
export type StockReport = StockReportOut;
export type ProfitAndLoss = ProfitAndLossOut;
export type DiscountReport = DiscountReportOut;
export type DebtsAging = DebtsAgingOut;
export type TrialBalance = TrialBalanceOut;
export type BalanceSheet = BalanceSheetOut;
export type StockAsOf = StockAsOfOut;

/**
 * 07 BO-09 catalogue — the reports that open (Bosqich 3: «Kassa / smena tarixi», «QQS registri
 * (qaytarishlar bilan)»; Bosqich 4: savdo, top tovarlar, kassirlar, ombor qoldig'i (konsolidatsiya),
 * kam qolgan tovarlar, foyda va zarar, chegirmalar va marja, qarzdorlik muddati; Bosqich 5 (M11): sinov
 * balansi, buxgalteriya balansi, ombor qoldig'i sana holatiga (`doc_date`, ACC-09)). The rest of the
 * catalogue is «Tez orada».
 */
export type ReportKey =
  | "cash-history"
  | "vat-returns"
  | "daily-sales"
  | "top-products"
  | "cashier-sales"
  | "stock"
  | "low-stock"
  | "profit-and-loss"
  | "discounts"
  | "debts-aging"
  | "trial-balance"
  | "balance-sheet"
  | "stock-as-of";
export const REPORT_KEYS: readonly ReportKey[] = [
  "cash-history",
  "vat-returns",
  "daily-sales",
  "top-products",
  "cashier-sales",
  "stock",
  "low-stock",
  "profit-and-loss",
  "discounts",
  "debts-aging",
  "trial-balance",
  "balance-sheet",
  "stock-as-of",
];

/** Reports read from `/reports/*` with the shared period / branch filters. */
export type DataReportKey = Exclude<ReportKey, "cash-history" | "vat-returns">;

export type LoadStatus = "idle" | "loading" | "error";

/** 07 BO-09 quick period buttons (Bugun / Hafta / Oy / Chorak; «Boshqa» = the date inputs). */
export type QuickRange = "today" | "week" | "month" | "quarter";
export const QUICK_RANGES: readonly QuickRange[] = ["today", "week", "month", "quarter"];

export interface DateRange {
  /** `YYYY-MM-DD` (inclusive). */
  from: string;
  to: string;
}

export interface HistoryRequest {
  registerId: string;
  range: DateRange;
}

export interface VatReturnsRequest {
  period: string;
  cursor: string | null;
}

export interface CenterMountParams {
  /** Local date `YYYY-MM-DD`. */
  today: string;
  /** The topbar branch as the default branch filter (`null` = «Barcha filiallar»). */
  branchId?: string | null;
}

/** Σ of the shown shifts (decimal strings). */
export interface HistoryTotals {
  openingCash: string;
  cashSales: string;
  cashIn: string;
  cashOut: string;
  variance: string;
}

export const VAT_PAGE_SIZE = 50;
/** 20 #19: `limit` 1…200. */
export const TOP_LIMIT = 50;
/** Report tables page on the client (whole report in one answer, 20 §20). */
export const CLIENT_PAGE = 50;

export type TopOrder = "top" | "bottom";
export type DiscountsGroupBy = "day" | "branch" | "cashier" | "product";
export const DISCOUNT_GROUPS: readonly DiscountsGroupBy[] = ["day", "branch", "cashier", "product"];
export type AgingDirection = "receivable" | "payable";

/** Per-report options (one store, so a request is a pure function of the stores). */
export interface ReportOptions {
  topOrder: TopOrder;
  discountsGroupBy: DiscountsGroupBy;
  agingDirection: AgingDirection;
  /** Ombor qoldig'i: name or exact barcode, ≤ 64. */
  stockSearch: string;
}

export const DEFAULT_OPTIONS: ReportOptions = {
  topOrder: "top",
  discountsGroupBy: "day",
  agingDirection: "receivable",
  stockSearch: "",
};

export type ReportRequest =
  | { kind: "sales"; report: "daily-sales" | "cashier-sales"; range: DateRange; branchId: string | null }
  | { kind: "top-products"; range: DateRange; branchId: string | null; order: TopOrder }
  | { kind: "stock"; branchId: string | null; belowMinOnly: boolean; search: string }
  | { kind: "profit-and-loss"; range: DateRange; branchId: string | null }
  | { kind: "discounts"; range: DateRange; branchId: string | null; groupBy: DiscountsGroupBy }
  | { kind: "debts-aging"; asOf: string; branchId: string | null; direction: AgingDirection }
  | { kind: "trial-balance"; period: string; branchId: string | null }
  | { kind: "balance-sheet"; asOf: string; branchId: string | null }
  | { kind: "stock-as-of"; asOf: string; branchId: string | null };

export type ReportData =
  | { kind: "sales"; data: SalesReport }
  | { kind: "top-products"; data: TopProducts }
  | { kind: "stock"; data: StockReport }
  | { kind: "profit-and-loss"; data: ProfitAndLoss }
  | { kind: "discounts"; data: DiscountReport }
  | { kind: "debts-aging"; data: DebtsAging }
  | { kind: "trial-balance"; data: TrialBalance }
  | { kind: "balance-sheet"; data: BalanceSheet }
  | { kind: "stock-as-of"; data: StockAsOf };

export interface ReportResult {
  /** `requestKey` of the request it answers. */
  key: string;
  result: ReportData;
}

/** Who may open a report (07 BO-09; the API's own permission is the final word). */
export interface ReportRequirement {
  permission?: string;
  anyOf?: readonly string[];
}

export const REPORT_ACCESS: Record<ReportKey, ReportRequirement> = {
  "cash-history": { anyOf: ["reports.sales.view", "cash.count.shift"] },
  "vat-returns": { permission: "tax.vat.view" },
  "daily-sales": { permission: "reports.sales.view" },
  "top-products": { permission: "reports.sales.view" },
  "cashier-sales": { permission: "reports.sales.view" },
  stock: { permission: "stock.view" },
  "low-stock": { permission: "stock.view" },
  "profit-and-loss": { permission: "reports.finance.view" },
  discounts: { permission: "reports.finance.view" },
  "debts-aging": { anyOf: ["reports.finance.view", "debts.approve"] },
  "trial-balance": { permission: "reports.finance.view" },
  "balance-sheet": { permission: "reports.finance.view" },
  "stock-as-of": { permission: "reports.finance.view" },
};

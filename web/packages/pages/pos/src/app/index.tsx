/**
 * @pages/pos — veb-kassa (POS-01…16). Package router (24 §1): route objects relative to `/pos`,
 * rendered inside the shell's POS layout (full screen, data-theme="light", data-density="touch").
 *
 * Ownership (Bosqich 3): b3-pos-sale owns this file, the sale/search/payment/receipt/sync screens and
 * the POS bootstrap. b3-pos-ops and b3-pos-wh add their routes ONLY between their anchor comments below.
 * Agreed paths: POS-01 login = `/pos/login` (b3-pos-ops, `POS_LOGIN_PATH`), POS-02 sale = `/pos/sale`.
 */
import type React from "react";
import { Navigate, type RouteObject } from "react-router-dom";

import type { RouteHandle } from "@shared/models";

import { PosLogin } from "#/pages/login/ui/page/Page.tsx";
import { Lookup } from "#/pages/lookup/ui/page/Page.tsx";
import { Sale, SalePayment, SaleReceipt } from "#/pages/sale/ui/page/Page.tsx";
// --- debts imports (B4, w-debts) ---
import { DebtBook } from "#/pages/debt-book/ui/page/Page.tsx";
import { SaleCredit } from "#/pages/sale/ui/page/Page.tsx";
// --- debts imports end ---
import { SyncStatus } from "#/pages/sync-status/ui/page/Page.tsx";
// --- pos-ops imports ---
import { CashCount } from "#/pages/cash-count/ui/page/Page.tsx";
import { CashMovement } from "#/pages/cash-movement/ui/page/Page.tsx";
import { Returns } from "#/pages/returns/ui/page/Page.tsx";
import { ShiftClose } from "#/pages/shift-close/ui/page/Page.tsx";
// --- pos-ops imports end ---
// --- pos-wh imports ---
import { Equipment } from "#/pages/equipment/ui/page/Page.tsx";
import { GoodsReceipt } from "#/pages/goods-receipt/ui/page/Page.tsx";
import { StockCount } from "#/pages/stock-count/ui/page/Page.tsx";
import { Transfers } from "#/pages/transfers/ui/page/Page.tsx";
import { WarehouseHub } from "#/pages/warehouse-hub/ui/page/Page.tsx";

/** Warehouse landing (no `shift.open` users) and POS-16 — contracts/pos-wh-routes.md. */
export const POS_WAREHOUSE_PATH = "/pos/warehouse";
export const POS_EQUIPMENT_PATH = "/pos/settings/devices";
// --- pos-wh imports end ---

/** POS-01 (b3-pos-ops) — the POS bootstrap redirects here without a registered device / PIN session. */
export const POS_LOGIN_PATH = "/pos/login";
export const POS_SALE_PATH = "/pos/sale";

export {
  PosBootstrap,
  PosCashierMenu,
  usePosHeader,
  type PosHeader,
  type PrinterChip,
} from "#/app/bootstrap/index.ts";

const route = (r: { route: string; titleKey: string; Page: () => React.ReactNode }): RouteObject => ({
  path: r.route,
  element: <r.Page />,
  handle: { titleKey: r.titleKey } satisfies RouteHandle,
});

export const routes: RouteObject[] = [
  { index: true, element: <Navigate to={Sale.route} replace /> },
  // POS-02, POS-03 (/pos/sale/payment) and POS-04 (/pos/sale/receipt) as overlays of the sale screen
  route(Sale),
  route(SalePayment),
  route(SaleReceipt),
  // POS-11 (F9) and POS-12 (F12)
  route(Lookup),
  route(SyncStatus),
  // --- pos-ops routes ---
  {
    path: PosLogin.route,
    element: <PosLogin.Page />,
    handle: { titleKey: PosLogin.titleKey } satisfies RouteHandle,
  },
  // POS-05 (F6), POS-07 (F8), POS-15, POS-14
  {
    path: Returns.route,
    element: <Returns.Page />,
    handle: { titleKey: Returns.titleKey } satisfies RouteHandle,
  },
  {
    path: ShiftClose.route,
    element: <ShiftClose.Page />,
    handle: { titleKey: ShiftClose.titleKey } satisfies RouteHandle,
  },
  {
    path: CashCount.route,
    element: <CashCount.Page />,
    handle: { titleKey: CashCount.titleKey } satisfies RouteHandle,
  },
  {
    path: CashMovement.route,
    element: <CashMovement.Page />,
    handle: { titleKey: CashMovement.titleKey } satisfies RouteHandle,
  },
  // --- pos-ops routes end ---
  // --- debts routes (B4, w-debts): POS-06 /pos/sale/credit (F5), POS-13 /pos/debts (F7) ---
  route(SaleCredit),
  route(DebtBook),
  // --- debts routes end ---
  // --- pos-wh routes ---
  // Ombor hub, POS-08, POS-09, POS-10, POS-16
  route(WarehouseHub),
  route(GoodsReceipt),
  route(Transfers),
  route(StockCount),
  route(Equipment),
  // --- pos-wh routes end ---
];

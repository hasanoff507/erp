/**
 * BO-03 effects — `GET /reports/stock` (20 §20: rows + KPI of one warehouse or of every branch, WEB-10),
 * `GET /stock-lots` (19 §7), `GET /transfers?status=` (19 §13) and `GET /stock-counts?status=review`
 * (19 §14) for the KPI cards and tab badges.
 */
import { api } from "@shared/api";

import { BULK_LIMIT, apiFx, readAllPages } from "#/shared/lib/effect.ts";

import { digestOf, ofBranch } from "../lib/index.ts";
import {
  ALL_STOCK,
  BALANCE_PAGE_SIZE,
  EXPIRY_DAYS,
  type DigestRequest,
  type DigestTransfer,
  type ExpiringSummary,
  type LotsRequest,
  type StockLotPage,
  type StockReport,
  type TransitSummary,
} from "../types/index.ts";

/** The «Qoldiq» report: one warehouse (its id) or every branch ({@link ALL_STOCK}). */
export const loadStockFx = apiFx<string, StockReport>((scope) =>
  api.reports.getStock(scope === ALL_STOCK ? {} : { warehouse_id: scope }),
);

export const listExpiringLotsFx = apiFx<LotsRequest, StockLotPage>(({ warehouseId, cursor }) =>
  api.inventory.listStockLots({
    warehouse_id: warehouseId,
    expiring_within_days: EXPIRY_DAYS,
    ...(cursor ? { cursor } : {}),
    limit: BALANCE_PAGE_SIZE,
  }),
);

/** KPI «Muddati yaqin partiyalar (7 kun)» + «Muddati N kunda» chips of the balance rows. */
export const loadExpiringFx = apiFx<string, ExpiringSummary>(async (warehouseId) => {
  const { items, capped } = await readAllPages(
    (cursor) =>
      api.inventory.listStockLots({
        warehouse_id: warehouseId,
        expiring_within_days: EXPIRY_DAYS,
        ...(cursor ? { cursor } : {}),
        limit: BULK_LIMIT,
      }),
    5,
  );
  return { lots: items, capped };
});

/**
 * KPI «Yo'ldagi ko'chirishlar» + «Ko'chirishlar» badge (sent; overdue ones) of the given branch — a
 * transfer counts when the branch sends or receives it (WEB-04; the list API has no branch filter).
 */
export const loadTransitFx = apiFx<string, TransitSummary>(async (branchId) => {
  const [sent, posted] = await Promise.all([
    readAllPages(
      (cursor) =>
        api.transfers.listTransfers({ status: "sent", ...(cursor ? { cursor } : {}), limit: BULK_LIMIT }),
      5,
    ),
    readAllPages(
      (cursor) =>
        api.transfers.listTransfers({ status: "posted", ...(cursor ? { cursor } : {}), limit: BULK_LIMIT }),
      5,
    ),
  ]);
  const inTransit = ofBranch(sent.items, branchId);
  return {
    inTransit: inTransit.length,
    overdue: inTransit.filter((t) => t.is_overdue).length,
    waitingEttn: ofBranch(posted.items, branchId).filter(
      (t) => t.transport_mode === "vehicle" && t.ettn?.status !== "registered",
    ).length,
  };
});

/** «Inventarizatsiyalar» badge — counts of the warehouse waiting for «Farqni tasdiqlash» (WEB-04). */
export const loadReviewCountFx = apiFx<string, number>(async (warehouseId) => {
  const { items } = await readAllPages(
    (cursor) =>
      api.stockCounts.listStockCounts({
        status: "review",
        warehouse_id: warehouseId,
        ...(cursor ? { cursor } : {}),
        limit: BULK_LIMIT,
      }),
    5,
  );
  return items.length;
});

/** «Ko'chirishlar va e-TTN» block: transfers of the branch since `from` (newest first, at most 5). */
export const loadDigestFx = apiFx<DigestRequest, DigestTransfer[]>(async ({ branchId, from }) => {
  const { items } = await readAllPages(
    (cursor) => api.transfers.listTransfers({ from, ...(cursor ? { cursor } : {}), limit: BULK_LIMIT }),
    3,
  );
  return digestOf(items, branchId);
});

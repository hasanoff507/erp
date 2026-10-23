import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";

import {
  $cursor,
  $entries,
  $filters,
  $productNames,
  $rangeInvalid,
  $recostFilter,
  $recostJobs,
  $retryError,
  $retrying,
  $status,
  $turnover,
  $warehouseNames,
  defaultFilters,
  filtersChanged,
  filtersReset,
  isRetryable,
  listEntriesFx,
  listRecostFx,
  loadProductNamesFx,
  loadWarehousesFx,
  moreRequested,
  pageMounted,
  recostFilterChanged,
  recostRetryRequested,
  retryRecostFx,
  toQuery,
  turnoverOf,
  type EntriesRequest,
  type LedgerEntry,
  type LedgerEntryPage,
  type RecostJob,
  type RecostRequest,
} from "./index.ts";

const TODAY = "2026-10-16";

function entry(id: string, amount: string, patch: Partial<LedgerEntry> = {}): LedgerEntry {
  return {
    id,
    entry_date: "2026-10-15",
    account_dt: "2910",
    account_kt: "0000",
    amount,
    branch_id: "b-1",
    doc_type: "stock_openings",
    doc_id: "doc-1",
    doc_number: "OO-0001",
    analytics: {},
    reversal_of_id: null,
    ...patch,
  };
}

function job(id: string, status: string, patch: Partial<RecostJob> = {}): RecostJob {
  return {
    id,
    warehouse_id: "w-1",
    product_id: "p-1",
    from_date: "2026-09-28",
    status,
    reason_doc_type: "goods_receipts",
    reason_doc_id: "gr-1",
    attempts: status === "failed" ? 3 : 0,
    last_error: status === "failed" ? "lock timeout" : null,
    created_at: "2026-10-01T05:00:00Z",
    finished_at: null,
    ...patch,
  };
}

function scope(
  pages: Record<string, LedgerEntryPage>,
  { retry }: { retry?: (id: string) => RecostJob } = {},
) {
  const entryCalls: EntriesRequest[] = [];
  const recostCalls: RecostRequest[] = [];
  const s = fork({
    handlers: [
      [
        listEntriesFx,
        (req: EntriesRequest) => {
          entryCalls.push(req);
          return pages[req.cursor ?? "first"] ?? { items: [], next_cursor: null };
        },
      ],
      [
        listRecostFx,
        (req: RecostRequest) => {
          recostCalls.push(req);
          const items =
            req.status === "failed"
              ? [job("j-2", "failed")]
              : [job("j-1", "done", { finished_at: "2026-10-01T05:01:00Z" }), job("j-2", "failed")];
          return { items, next_cursor: null };
        },
      ],
      [
        retryRecostFx,
        retry ?? ((id: string) => job(id, "queued", { attempts: 3, last_error: "lock timeout" })),
      ],
      [loadProductNamesFx, (ids: string[]) => Object.fromEntries(ids.map((id) => [id, `Tovar ${id}`]))],
      [loadWarehousesFx, () => ({ "w-1": "Asosiy ombor" })],
    ],
  });
  return { s, entryCalls, recostCalls };
}

describe("BO-08 journal model (20 #9, US-M11-01)", () => {
  it("mount: current month up to today → first page; «Dt oboroti = Kt oboroti» is Σ amount", async () => {
    const { s, entryCalls } = scope({
      first: { items: [entry("e1", "120000.00"), entry("e2", "15400.50")], next_cursor: null },
    });
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canViewRecost: false } });

    expect(entryCalls).toEqual([{ filters: defaultFilters(TODAY), cursor: null }]);
    expect(s.getState($filters)).toMatchObject({ dateFrom: "2026-10-01", dateTo: TODAY });
    expect(s.getState($entries)).toHaveLength(2);
    expect(s.getState($turnover)).toBe("135400.50");
    expect(s.getState($status)).toBe("idle");
  });

  it("cursor «Yana yuklash» appends the next page; a filter change starts from the first page", async () => {
    const { s, entryCalls } = scope({
      first: { items: [entry("e1", "10.00")], next_cursor: "c2" },
      c2: { items: [entry("e2", "20.00")], next_cursor: null },
    });
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canViewRecost: false } });
    await allSettled(moreRequested, { scope: s });
    expect(s.getState($entries).map((e) => e.id)).toEqual(["e1", "e2"]);
    expect(s.getState($cursor)).toBeNull();
    expect(s.getState($turnover)).toBe("30.00");

    await allSettled(moreRequested, { scope: s }); // no cursor → no request
    expect(entryCalls).toHaveLength(2);

    await allSettled(filtersChanged, { scope: s, params: { account: "5010", side: "kt", docType: "sales" } });
    expect(entryCalls.at(-1)).toEqual({
      filters: { dateFrom: "2026-10-01", dateTo: TODAY, account: "5010", side: "kt", docType: "sales" },
      cursor: null,
    });
    expect(s.getState($entries).map((e) => e.id)).toEqual(["e1"]);

    await allSettled(filtersReset, { scope: s });
    expect(s.getState($filters)).toEqual(defaultFilters(TODAY));
  });

  it("dateFrom > dateTo: no request, the table is cleared and the range is flagged", async () => {
    const { s, entryCalls } = scope({ first: { items: [entry("e1", "10.00")], next_cursor: null } });
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canViewRecost: false } });
    await allSettled(filtersChanged, { scope: s, params: { dateFrom: "2026-10-20" } });
    expect(entryCalls).toHaveLength(1);
    expect(s.getState($rangeInvalid)).toBe(true);
    expect(s.getState($entries)).toEqual([]);
  });

  it("a failed first page → error state (403 → no-permission in the UI)", async () => {
    const s = fork({
      handlers: [
        [
          listEntriesFx,
          (req: EntriesRequest) =>
            req.filters.docType === "sales"
              ? Promise.reject(new ApiError({ status: 403, code: "PERMISSION_DENIED", messageKey: "x" }))
              : { items: [entry("old", "1.00")], next_cursor: null },
        ],
      ],
    });
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canViewRecost: false } });
    await allSettled(filtersChanged, { scope: s, params: { docType: "sales" } });
    expect(s.getState($status)).toBe("error");
  });
});

describe("«Qayta hisoblash navbati» (19 §18, qaror #56c)", () => {
  it("loads jobs with product/warehouse names only with stock.view", async () => {
    const without = scope({});
    await allSettled(pageMounted, { scope: without.s, params: { today: TODAY, canViewRecost: false } });
    expect(without.recostCalls).toEqual([]);

    const { s, recostCalls } = scope({});
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canViewRecost: true } });
    expect(recostCalls).toEqual([{ status: null, cursor: null }]);
    expect(s.getState($recostJobs).map((j) => j.id)).toEqual(["j-1", "j-2"]);
    expect(s.getState($productNames)).toEqual({ "p-1": "Tovar p-1" });
    expect(s.getState($warehouseNames)).toEqual({ "w-1": "Asosiy ombor" });

    await allSettled(recostFilterChanged, { scope: s, params: "failed" });
    expect(s.getState($recostFilter)).toBe("failed");
    expect(recostCalls.at(-1)).toEqual({ status: "failed", cursor: null });
    expect(s.getState($recostJobs).map((j) => j.id)).toEqual(["j-2"]);
  });

  it("«Qayta urinish»: only a failed job is retried; the answer (queued) replaces the row", async () => {
    const retried: string[] = [];
    const { s } = scope(
      {},
      {
        retry: (id) => {
          retried.push(id);
          return job(id, "queued", { attempts: 3 });
        },
      },
    );
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canViewRecost: true } });
    await allSettled(recostRetryRequested, { scope: s, params: "j-1" }); // done → ignored
    await allSettled(recostRetryRequested, { scope: s, params: "j-2" });
    expect(retried).toEqual(["j-2"]);
    expect(s.getState($recostJobs).find((j) => j.id === "j-2")?.status).toBe("queued");
    expect(s.getState($retrying)).toEqual([]);
  });

  it("a refused retry (409) shows the error and reloads the queue", async () => {
    const { s, recostCalls } = scope(
      {},
      {
        retry: () => {
          throw new ApiError({
            status: 409,
            code: "DOC_INVALID_STATE",
            messageKey: "errors.doc_invalid_state",
          });
        },
      },
    );
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canViewRecost: true } });
    await allSettled(recostRetryRequested, { scope: s, params: "j-2" });
    expect(s.getState($retryError)?.code).toBe("DOC_INVALID_STATE");
    expect(recostCalls).toHaveLength(2);
  });
});

describe("journal lib", () => {
  it("query: column-named filters; the account goes to the chosen side", () => {
    expect(toQuery({ ...defaultFilters(TODAY), account: "2910", side: "dt" }, null)).toEqual({
      entry_date__gte: "2026-10-01",
      entry_date__lte: TODAY,
      account_dt: "2910",
      limit: 50,
    });
    expect(
      toQuery({ ...defaultFilters(TODAY), account: "0000", side: "kt", docType: "stock_openings" }, "c9"),
    ).toEqual({
      entry_date__gte: "2026-10-01",
      entry_date__lte: TODAY,
      account_kt: "0000",
      doc_type: "stock_openings",
      cursor: "c9",
      limit: 50,
    });
  });

  it("turnover is exact decimal arithmetic; retry only for failed", () => {
    expect(turnoverOf([])).toBe("0.00");
    expect(turnoverOf([entry("a", "0.10"), entry("b", "0.20")])).toBe("0.30");
    expect(isRetryable({ status: "failed" })).toBe(true);
    expect(isRetryable({ status: "rejected_period_closed" })).toBe(false);
  });
});

import { allSettled, fork, scopeBind } from "effector";
import { describe, expect, it } from "vitest";

import { $activeBranchId } from "@shared/state/session";

import { $warehouses } from "#/entities/refs/index.ts";

import {
  $counts,
  $detail,
  $drafts,
  $filter,
  $pendingLines,
  $selectedId,
  $totals,
  $visibleLines,
  changedLines,
  countSelected,
  countTotals,
  countedChanged,
  countsOpened,
  draftsAfterSave,
  createCountFx,
  extraLineAdded,
  filterChanged,
  getCountFx,
  isCountedValid,
  lineFilterChanged,
  listCountsFx,
  postCountFx,
  recordLinesFx,
  toQuery,
  type Count,
  type CountLine,
  type CountSummary,
  type ListRequest,
  type PostCountParams,
  type RecordLinesParams,
} from "./index.ts";

function line(id: string, patch: Partial<CountLine> = {}): CountLine {
  return {
    id,
    line_no: 1,
    product_id: `p-${id}`,
    product_name: `Tovar ${id}`,
    snapshot_qty: "10.000",
    expected: "10.000",
    counted: null,
    counted_at: null,
    diff: null,
    amount: null,
    ...patch,
  };
}

function count(id: string, patch: Partial<Count> = {}): Count {
  return {
    id,
    number: "INV-1",
    status: "review",
    doc_date: "2026-10-16",
    branch_id: "b-1",
    warehouse_id: "w-1",
    started_at: "2026-10-16T05:00:00Z",
    responsible_user_id: null,
    comment: null,
    line_count: 3,
    counted_count: 2,
    uncounted_count: 1,
    created_by: "u-1",
    created_at: "2026-10-16T05:00:00Z",
    posted_at: null,
    cancelled_at: null,
    cancel_reason: null,
    lines: [
      line("1", { counted: "8.000", diff: "-2.000", amount: "-24000.00" }),
      line("2", { counted: "11.000", diff: "1.000", amount: "5000.50" }),
      line("3"),
    ],
    ...patch,
  };
}

const summary = (id: string, status: CountSummary["status"]): CountSummary => {
  const { lines: _lines, ...rest } = count(id, { status });
  return rest;
};

describe("Inventarizatsiyalar model (US-M05-02/03, 19 §14)", () => {
  it("opens on `review`, a filter change reloads; a selected count is read with its lines", async () => {
    const calls: ListRequest[] = [];
    const s = fork({
      handlers: [
        [
          listCountsFx,
          (req: ListRequest) => {
            calls.push(req);
            return { items: [summary("c-1", req.status ?? "review")], next_cursor: null };
          },
        ],
        [getCountFx, (id: string) => count(id)],
      ],
    });
    await allSettled(countsOpened, { scope: s });
    expect(calls).toEqual([{ warehouseId: null, status: "review", cursor: null }]);
    expect(s.getState($counts)).toHaveLength(1);

    await allSettled(filterChanged, { scope: s, params: null });
    expect(s.getState($filter)).toBeNull();
    expect(calls.at(-1)).toEqual({ warehouseId: null, status: null, cursor: null });

    await allSettled(countSelected, { scope: s, params: "c-1" });
    expect(s.getState($detail)?.lines).toHaveLength(3);
    expect(s.getState($totals)).toEqual({
      shortage: "24000.00",
      surplus: "5000.50",
      uncounted: 1,
      diffLines: 2,
    });
    await allSettled(lineFilterChanged, { scope: s, params: "uncounted" });
    expect(s.getState($visibleLines).map((l) => l.id)).toEqual(["3"]);
  });

  it("back-office line entry: only changed values are sent, an extra product adds a line", async () => {
    const sent: RecordLinesParams[] = [];
    const s = fork({
      handlers: [
        [listCountsFx, () => ({ items: [], next_cursor: null })],
        [getCountFx, (id: string) => count(id, { status: "counting" })],
        [
          recordLinesFx,
          (p: RecordLinesParams) => {
            sent.push(p);
            return count(p.id, { status: "counting" });
          },
        ],
      ],
    });
    await allSettled(countSelected, { scope: s, params: "c-1" });
    await allSettled(countedChanged, { scope: s, params: { productId: "p-1", value: "8" } }); // unchanged
    await allSettled(countedChanged, { scope: s, params: { productId: "p-3", value: "9.5" } });
    await allSettled(extraLineAdded, { scope: s, params: { productId: "p-9", name: "Topilgan" } });
    await allSettled(countedChanged, { scope: s, params: { productId: "p-9", value: "2" } });
    expect(s.getState($pendingLines)).toEqual([
      { product_id: "p-3", counted: "9.500" },
      { product_id: "p-9", counted: "2.000" },
    ]);
    await allSettled(recordLinesFx, { scope: s, params: { id: "c-1", lines: s.getState($pendingLines) } });
    expect(sent).toHaveLength(1);
    expect(s.getState($drafts)).toEqual({});
  });

  it("the list is the current warehouse's counts (WEB-04)", async () => {
    const calls: ListRequest[] = [];
    const s = fork({
      values: [
        [$activeBranchId, "b-1"],
        [
          $warehouses,
          [
            {
              id: "w-1",
              branch_id: "b-1",
              name: "Asosiy",
              type: "store",
              inventory_account: "2920",
              version: 1,
            },
            {
              id: "w-2",
              branch_id: "b-2",
              name: "Boshqa",
              type: "store",
              inventory_account: "2920",
              version: 1,
            },
          ],
        ],
      ],
      handlers: [
        [
          listCountsFx,
          (req: ListRequest) => {
            calls.push(req);
            return { items: [], next_cursor: null };
          },
        ],
      ],
    });
    await allSettled(countsOpened, { scope: s });
    expect(calls).toEqual([{ warehouseId: "w-1", status: "review", cursor: null }]);
    expect(toQuery(calls[0]!)).toEqual({ warehouse_id: "w-1", status: "review", limit: 50 });
  });

  it("a list opened before the warehouses are known is read again for the warehouse (WEB-04)", async () => {
    const calls: ListRequest[] = [];
    const s = fork({
      values: [[$activeBranchId, "b-1"]],
      handlers: [
        [
          listCountsFx,
          (req: ListRequest) => {
            calls.push(req);
            return { items: [], next_cursor: null };
          },
        ],
      ],
    });
    await allSettled(countsOpened, { scope: s });
    await allSettled($warehouses, {
      scope: s,
      params: [
        { id: "w-1", branch_id: "b-1", name: "Asosiy", type: "store", inventory_account: "2920", version: 1 },
      ],
    });
    expect(calls.map((c) => c.warehouseId)).toEqual([null, "w-1"]);
  });

  it("a value typed while the save is running survives it (WEB-12)", async () => {
    let finish!: (c: Count) => void;
    const s = fork({
      handlers: [
        [getCountFx, (id: string) => count(id, { status: "counting" })],
        [recordLinesFx, () => new Promise<Count>((res) => (finish = res))],
      ],
    });
    await allSettled(countSelected, { scope: s, params: "c-1" });
    await allSettled(countedChanged, { scope: s, params: { productId: "p-3", value: "9" } });
    await allSettled(countedChanged, { scope: s, params: { productId: "p-2", value: "12" } });
    void scopeBind(recordLinesFx, { scope: s })({ id: "c-1", lines: s.getState($pendingLines) });
    // Typed during the request: p-3 changes again, p-2 stays as sent.
    scopeBind(countedChanged, { scope: s })({ productId: "p-3", value: "7" });
    finish(
      count("c-1", {
        status: "counting",
        lines: [
          line("1", { counted: "8.000" }),
          line("2", { counted: "12.000" }),
          line("3", { counted: "9.000" }),
        ],
      }),
    );
    await allSettled(s);
    expect(s.getState($drafts)).toEqual({ "p-3": "7" });
    expect(draftsAfterSave({ a: "1", b: "x" }, [{ product_id: "a", counted: "1.000" }], [])).toEqual({
      b: "x",
    });
  });

  it("post re-reads the document and reloads the list; a new count opens its detail", async () => {
    const posts: PostCountParams[] = [];
    const reads: string[] = [];
    const s = fork({
      handlers: [
        [listCountsFx, () => ({ items: [], next_cursor: null })],
        [
          getCountFx,
          (id: string) => {
            reads.push(id);
            return count(id, { status: "posted" });
          },
        ],
        [
          postCountFx,
          (p: PostCountParams) => {
            posts.push(p);
            return { id: p.id, number: "INV-1", status: "posted", shortage_lines: [], surplus_lines: [] };
          },
        ],
        [createCountFx, () => count("c-new", { status: "counting" })],
      ],
    });
    await allSettled(countSelected, { scope: s, params: "c-1" });
    await allSettled(postCountFx, { scope: s, params: { id: "c-1", treatUncountedAsZero: true } });
    expect(posts).toEqual([{ id: "c-1", treatUncountedAsZero: true }]);
    expect(reads).toEqual(["c-1", "c-1"]);
    expect(s.getState($detail)?.status).toBe("posted");

    await allSettled(createCountFx, {
      scope: s,
      params: { warehouse_id: "w-1", doc_date: "2026-10-16" },
    });
    expect(s.getState($selectedId)).toBe("c-new");
    expect(s.getState($detail)?.status).toBe("counting");
  });
});

describe("stock count lib", () => {
  it("totals, changed lines and validation", () => {
    expect(countTotals([])).toEqual({ shortage: "0.00", surplus: "0.00", uncounted: 0, diffLines: 0 });
    expect(changedLines([line("1", { counted: "1.000" })], [], { "p-1": "1" })).toEqual([]);
    expect(changedLines([line("1")], [], { "p-1": "0" })).toEqual([{ product_id: "p-1", counted: "0.000" }]);
    expect(isCountedValid("")).toBe(true);
    expect(isCountedValid("0")).toBe(true);
    expect(isCountedValid("-1")).toBe(false);
  });
});

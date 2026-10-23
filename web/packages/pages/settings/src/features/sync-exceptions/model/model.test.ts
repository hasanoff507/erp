import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import {
  $exceptions,
  applyReview,
  exceptionDocType,
  exceptionsFilterChanged,
  exceptionsOpened,
  isNoteValid,
  listExceptionsFx,
  reviewExceptionFx,
  toParams,
  type SyncException,
} from "./index.ts";

function ex(id: string, patch: Partial<SyncException> = {}): SyncException {
  return {
    id,
    kind: "price_mismatch",
    device_id: "d-1",
    branch_id: "b-1",
    client_event_id: "e-1",
    doc_type: "sales",
    doc_id: "s-1",
    details: { expected: "19000.00", actual: "18000.00" },
    created_at: "2026-10-16T08:00:00Z",
    reviewed_at: null,
    reviewed_by: null,
    review_note: null,
    ...patch,
  };
}

const reviewed = {
  id: "x-1",
  reviewed_at: "2026-10-17T09:00:00Z",
  reviewed_by: "u-owner",
  review_note: "Narx kech yangilangan",
};

describe("BO-14 «Sinxron istisnolari» (20 #40f/#40g)", () => {
  it("filter → `reviewed` query; open list loses a reviewed row, «Barchasi» updates it in place", async () => {
    const calls: unknown[] = [];
    const s = fork({
      handlers: [
        [
          listExceptionsFx,
          (p: unknown) => {
            calls.push(p);
            return { items: [ex("x-1"), ex("x-2")], next_cursor: null };
          },
        ],
        [reviewExceptionFx, () => reviewed],
      ],
    });
    await allSettled(exceptionsOpened, { scope: s });
    expect(calls).toEqual([{ filter: "open", cursor: null }]);
    await allSettled(reviewExceptionFx, { scope: s, params: { id: "x-1", note: "Narx kech yangilangan" } });
    expect(s.getState($exceptions).map((x) => x.id)).toEqual(["x-2"]);

    await allSettled(exceptionsFilterChanged, { scope: s, params: "all" });
    await allSettled(reviewExceptionFx, { scope: s, params: { id: "x-1", note: "ok" } });
    expect(s.getState($exceptions).find((x) => x.id === "x-1")?.review_note).toBe("Narx kech yangilangan");
  });

  it("query params, note validation, document labels", () => {
    expect(toParams("open", null)).toEqual({ reviewed: false, limit: 20 });
    expect(toParams("reviewed", "c2")).toEqual({ reviewed: true, cursor: "c2", limit: 20 });
    expect(toParams("all", null)).toEqual({ limit: 20 });
    expect(isNoteValid("  ")).toBe(false);
    expect(isNoteValid("x".repeat(500))).toBe(true);
    expect(isNoteValid("x".repeat(501))).toBe(false);
    expect(exceptionDocType("sales")).toBe("sales");
    expect(exceptionDocType("whatever")).toBe("other");
    expect(exceptionDocType(null)).toBeNull();
    expect(applyReview([ex("x-1")], reviewed, "reviewed")[0]?.reviewed_by).toBe("u-owner");
  });
});

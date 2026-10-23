import { allSettled, fork } from "effector";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { ApiError } from "@shared/api";
import { initI18n } from "@shared/i18n";
import type { OpeningOut, WarehouseOut } from "@shared/models";

import {
  $canSubmit,
  $draft,
  $lines,
  $posted,
  $problems,
  $results,
  $submitError,
  cancelStaleDraftFx,
  createDraftFx,
  formOpened,
  lineChanged,
  lineProblem,
  loadWarehouseFx,
  pickWarehouse,
  postDraftFx,
  productPicked,
  searchChanged,
  searchProductsFx,
  submitted,
  toLineIn,
  type StaleDraftCancel,
  type SubmitParams,
} from "./index.ts";

const warehouse = (id: string, type: "store" | "stock"): WarehouseOut => ({
  id,
  branch_id: "b-1",
  name: id,
  type,
  inventory_account: type === "store" ? "2920" : "2910",
  version: 1,
});

function doc(status: string, lineCount = 1): OpeningOut {
  return {
    id: "so-1",
    number: status === "posted" ? "OO-0001" : null,
    status,
    doc_date: "2026-10-17",
    branch_id: "b-1",
    warehouse_id: "w-store",
    comment: null,
    line_count: lineCount,
    total_amount: "98000.00",
    created_at: "2026-10-17T05:00:00Z",
    posted_at: status === "posted" ? "2026-10-17T05:00:01Z" : null,
    cancelled_at: null,
    cancel_reason: null,
    lines: [],
  };
}

beforeAll(async () => {
  await initI18n("uz").changeLanguage("uz");
});

const milk = { id: "p1", name: "Sut 1 l", unitCode: "pcs" };

async function filled(handlers: {
  create?: (p: SubmitParams) => OpeningOut;
  post?: (id: string) => OpeningOut;
  cancel?: (p: StaleDraftCancel) => OpeningOut;
}) {
  const create = vi.fn(handlers.create ?? (() => doc("draft")));
  const post = vi.fn(handlers.post ?? (() => doc("posted")));
  const cancel = vi.fn(handlers.cancel ?? (() => doc("cancelled")));
  const scope = fork({
    handlers: [
      [loadWarehouseFx, () => warehouse("w-store", "store")],
      [createDraftFx, create],
      [postDraftFx, post],
      [cancelStaleDraftFx, cancel],
    ],
  });
  await allSettled(formOpened, { scope, params: { today: "2026-10-17" } });
  await allSettled(productPicked, { scope, params: milk });
  const key = scope.getState($lines)[0]?.key ?? "";
  await allSettled(lineChanged, { scope, params: { key, patch: { qty: "10", unitCost: "9800.5" } } });
  return { scope, create, post, cancel, key };
}

describe("BO-21 ③b opening stock — manual (19 §16)", () => {
  it("a valid line → POST /stock-openings (draft) → /post; the posted document is shown, lines cleared", async () => {
    const { scope, create, post } = await filled({});
    expect(scope.getState($canSubmit)).toBe(true);
    await allSettled(submitted, { scope });

    expect(create).toHaveBeenCalledTimes(1);
    expect(create.mock.calls[0]?.[0]).toMatchObject({ warehouseId: "w-store", docDate: "2026-10-17" });
    const sent = create.mock.calls[0]?.[0].lines[0];
    if (!sent) throw new Error("no line sent");
    expect(toLineIn(sent)).toEqual({
      product_id: "p1",
      qty: "10.000",
      unit_cost: "9800.5000",
    });
    expect(post).toHaveBeenCalledWith("so-1");
    expect(scope.getState($posted)?.status).toBe("posted");
    expect(scope.getState($lines)).toEqual([]);
    expect(scope.getState($draft)).toBeNull();
  });

  it("a failed post keeps the draft: «Saqlash» again re-posts it without a new draft", async () => {
    let attempts = 0;
    const { scope, create, post } = await filled({
      post: () => {
        attempts += 1;
        if (attempts === 1) {
          throw new ApiError({
            status: 422,
            code: "VALIDATION_ERROR",
            messageKey: "errors.validation",
            details: [{ field: "", messageKey: "validation.go_live_date_missing" }],
          });
        }
        return doc("posted");
      },
    });
    await allSettled(submitted, { scope });
    expect(scope.getState($submitError)?.code).toBe("VALIDATION_ERROR");
    expect(scope.getState($draft)?.id).toBe("so-1");

    await allSettled(submitted, { scope });
    expect(create).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledTimes(2);
    expect(scope.getState($posted)?.number).toBe("OO-0001");
  });

  it("changed lines after a failed post: the stale draft is cancelled before the new draft is created", async () => {
    let created = 0;
    const { scope, create, cancel, key } = await filled({
      create: () => {
        created += 1;
        return { ...doc("draft"), id: `so-${created}` };
      },
      post: () => {
        throw new ApiError({ status: 500, code: "INTERNAL_ERROR", messageKey: "errors.internal_error" });
      },
    });
    await allSettled(submitted, { scope });
    expect(cancel).not.toHaveBeenCalled();
    await allSettled(lineChanged, { scope, params: { key, patch: { qty: "12" } } });
    await allSettled(submitted, { scope });

    expect(cancel).toHaveBeenCalledTimes(1);
    expect(cancel.mock.calls[0]?.[0]).toMatchObject({
      id: "so-1",
      reason: "Qatorlar o'zgartirildi — yangi qoralama bilan almashtirildi",
    });
    expect(create).toHaveBeenCalledTimes(2);
    expect(cancel.mock.invocationCallOrder[0]).toBeLessThan(create.mock.invocationCallOrder[1] ?? 0);
    expect(create.mock.calls[1]?.[0].lines[0]?.qty).toBe("12");
    expect(scope.getState($draft)).toEqual({ id: "so-2", key: expect.any(String) as string });
  });

  it("a failed cancel of the stale draft is ignored — the new draft is still created", async () => {
    const { scope, create, cancel, key } = await filled({
      post: () => {
        throw new ApiError({ status: 500, code: "INTERNAL_ERROR", messageKey: "errors.internal_error" });
      },
      cancel: () => {
        throw new ApiError({
          status: 409,
          code: "DOC_INVALID_STATE",
          messageKey: "errors.doc_invalid_state",
        });
      },
    });
    await allSettled(submitted, { scope });
    await allSettled(lineChanged, { scope, params: { key, patch: { qty: "12" } } });
    await allSettled(submitted, { scope });
    expect(cancel).toHaveBeenCalledTimes(1);
    expect(create).toHaveBeenCalledTimes(2);
    expect(scope.getState($submitError)?.code).toBe("INTERNAL_ERROR");
  });

  it("validation: qty > 0 and unit_cost ≥ 0 — an invalid line blocks the submit", async () => {
    const { scope, create, key } = await filled({});
    await allSettled(lineChanged, { scope, params: { key, patch: { qty: "0" } } });
    expect(scope.getState($problems)[key]).toBe("qty");
    expect(scope.getState($canSubmit)).toBe(false);
    await allSettled(submitted, { scope });
    expect(create).not.toHaveBeenCalled();

    expect(lineProblem({ qty: "1.5", unitCost: "0" })).toBeNull();
    expect(lineProblem({ qty: "2", unitCost: "" })).toBe("unitCost");
    expect(lineProblem({ qty: "2", unitCost: "-1" })).toBe("unitCost");
  });

  it("product search: ≥ 2 characters, only the answer for the current query is kept", async () => {
    const search = vi.fn((q: string) => [
      {
        id: `p-${q}`,
        name: q,
        name_ru: null,
        category_id: null,
        unit_code: "pcs",
        mxik_code: null,
        package_code: null,
        vat_rate: "12.00",
        vat_exemption_code: null,
        is_marked: false,
        marking_group_code: null,
        is_weighed: false,
        min_stock: null,
        archived_at: null,
        version: 1,
        barcodes: [],
        current_price: null,
        current_cost: null,
        markup_pct: null,
      },
    ]);
    const scope = fork({ handlers: [[searchProductsFx, search]] });
    await allSettled(searchChanged, { scope, params: "s" });
    expect(search).not.toHaveBeenCalled();
    await allSettled(searchChanged, { scope, params: "sut" });
    expect(scope.getState($results).map((p) => p.id)).toEqual(["p-sut"]);
    await allSettled(searchChanged, { scope, params: "" });
    expect(scope.getState($results)).toEqual([]);
  });

  it("the store warehouse is preferred", () => {
    expect(pickWarehouse([warehouse("w-stock", "stock"), warehouse("w-store", "store")])?.id).toBe("w-store");
    expect(pickWarehouse([warehouse("w-stock", "stock")])?.id).toBe("w-stock");
    expect(pickWarehouse([])).toBeNull();
  });
});

import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";
import type { StockSettingsOut } from "@shared/models";

import {
  $scaleConflict,
  $scaleDirty,
  $scaleDraft,
  $scaleErrors,
  $scaleSaved,
  draftErrors,
  expiryDaysChanged,
  loadStockSettingsFx,
  saveStockSettingsFx,
  scaleSaveRequested,
  scaleTemplatesOpened,
  templateAdded,
  templateChanged,
  toDraft,
  toPatch,
} from "./index.ts";

const SERVER: StockSettingsOut = {
  weight_barcode_templates: [
    { prefixes: ["22"], item_code_len: 5, value_len: 5, value_kind: "WEIGHT", decimals: 3, enabled: true },
    { prefixes: ["21"], item_code_len: 5, value_len: 5, value_kind: "AMOUNT", decimals: 0, enabled: true },
  ],
  low_stock_check_enabled: true,
  expiry_warning_days: 7,
  version: 4,
};

describe("BO-14 scale templates (19 §17)", () => {
  it("draft ↔ PATCH body: value_len follows the PLU length (EAN-13), version sent back", () => {
    const draft = toDraft(SERVER);
    expect(draft.templates[0]).toEqual({
      prefixes: "22",
      itemCodeLen: 5,
      valueKind: "WEIGHT",
      decimals: 3,
      enabled: true,
    });
    const patch = toPatch(
      {
        ...draft,
        templates: [{ ...draft.templates[0]!, prefixes: "27, 28", itemCodeLen: 4 }],
        expiryDays: "10",
      },
      SERVER.version,
    );
    expect(patch).toEqual({
      weight_barcode_templates: [
        {
          prefixes: ["27", "28"],
          item_code_len: 4,
          value_len: 6,
          value_kind: "WEIGHT",
          decimals: 3,
          enabled: true,
        },
      ],
      low_stock_check_enabled: true,
      expiry_warning_days: 10,
      version: 4,
    });
  });

  it("validation: prefix 20–29, no duplicates, at least one, days 0..365", () => {
    const base = toDraft(SERVER);
    expect(draftErrors(base)).toEqual([]);
    const bad = {
      ...base,
      templates: [
        { ...base.templates[0]!, prefixes: "19" },
        { ...base.templates[1]!, prefixes: "21, 21" },
        { ...base.templates[1]!, prefixes: "" },
      ],
      expiryDays: "400",
    };
    expect(draftErrors(bad)).toEqual([
      { field: "templates.0.prefixes", key: "prefix_format" },
      { field: "templates.1.prefixes", key: "prefix_duplicate" },
      { field: "templates.2.prefixes", key: "prefix_required" },
      { field: "expiryDays", key: "range" },
    ]);
  });

  it("load → edit → save; 409 VERSION_CONFLICT is flagged for a reload", async () => {
    const saved: unknown[] = [];
    const scope = fork({
      handlers: [
        [loadStockSettingsFx, () => SERVER],
        [
          saveStockSettingsFx,
          (patch: { version: number }) => {
            saved.push(patch);
            if (saved.length === 2) {
              throw new ApiError({ status: 409, code: "VERSION_CONFLICT", messageKey: "errors.version_conflict",
                params: { current_version: 6 } }); // prettier-ignore
            }
            return { ...SERVER, version: 5, expiry_warning_days: 14 };
          },
        ],
      ],
    });
    await allSettled(scaleTemplatesOpened, { scope });
    expect(scope.getState($scaleDirty)).toBe(false);
    await allSettled(expiryDaysChanged, { scope, params: "14" });
    expect(scope.getState($scaleDirty)).toBe(true);
    await allSettled(scaleSaveRequested, { scope });
    expect(saved[0]).toMatchObject({ expiry_warning_days: 14, version: 4 });
    expect(scope.getState($scaleSaved)).toBe(true);
    expect(scope.getState($scaleDraft)?.expiryDays).toBe("14");

    await allSettled(templateAdded, { scope });
    expect(scope.getState($scaleErrors)).toEqual([{ field: "templates.2.prefixes", key: "prefix_required" }]);
    await allSettled(scaleSaveRequested, { scope }); // invalid → not sent
    expect(saved).toHaveLength(1);
    await allSettled(templateChanged, { scope, params: { index: 2, patch: { prefixes: "25" } } });
    await allSettled(scaleSaveRequested, { scope });
    expect(saved[1]).toMatchObject({ version: 5 });
    expect(scope.getState($scaleConflict)).toBe(true);
  });
});

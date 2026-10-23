/**
 * BO-14 «Tarozi shtrix-kodi» (07 BO-14 / POS-16; 19 §17 `GET/PATCH /stock-settings`; US-M09-06): the scale
 * weight-barcode templates (EAN-13 `PP CCCCC VVVVV K`), the low-stock check switch and the expiry warning days.
 * `catalog.manage`; optimistic `version` (= `tenants.version`) — a stale save answers 409 `VERSION_CONFLICT`
 * and the card offers to reload. A template change reaches the POS devices on their next `settings` pull.
 */
import { combine, createEffect, createEvent, createStore, sample } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";
import type { StockSettingsOut, StockSettingsPatch } from "@shared/models";

export type ValueKind = "WEIGHT" | "AMOUNT";

/** Editable template row; `prefixes` as typed ("22, 23"). `value_len` = 10 − `item_code_len` (EAN-13). */
export interface TemplateDraft {
  prefixes: string;
  itemCodeLen: 4 | 5 | 6;
  valueKind: ValueKind;
  decimals: 0 | 1 | 2 | 3;
  enabled: boolean;
}

export interface SettingsDraft {
  templates: TemplateDraft[];
  lowStockCheck: boolean;
  expiryDays: string;
}

export type DraftError =
  | { field: `templates.${number}.prefixes`; key: "prefix_format" | "prefix_duplicate" | "prefix_required" }
  | { field: "templates"; key: "too_many" }
  | { field: "expiryDays"; key: "range" };

export const MAX_TEMPLATES = 10;
export const EAN13_PAYLOAD = 10;

export function parsePrefixes(text: string): string[] {
  return text
    .split(/[\s,;]+/)
    .map((p) => p.trim())
    .filter(Boolean);
}

export function toDraft(s: StockSettingsOut): SettingsDraft {
  return {
    templates: s.weight_barcode_templates.map((t) => ({
      prefixes: t.prefixes.join(", "),
      itemCodeLen: t.item_code_len === 4 || t.item_code_len === 6 ? t.item_code_len : 5,
      valueKind: t.value_kind,
      decimals: (t.decimals >= 0 && t.decimals <= 3 ? t.decimals : 0) as 0 | 1 | 2 | 3,
      enabled: t.enabled !== false,
    })),
    lowStockCheck: s.low_stock_check_enabled,
    expiryDays: String(s.expiry_warning_days),
  };
}

export function draftErrors(d: SettingsDraft): DraftError[] {
  const out: DraftError[] = [];
  if (d.templates.length > MAX_TEMPLATES) out.push({ field: "templates", key: "too_many" });
  const seen = new Set<string>();
  d.templates.forEach((t, i) => {
    const prefixes = parsePrefixes(t.prefixes);
    const field = `templates.${i}.prefixes` as const;
    if (prefixes.length === 0) out.push({ field, key: "prefix_required" });
    else if (prefixes.some((p) => !/^2[0-9]$/.test(p))) out.push({ field, key: "prefix_format" });
    else if (prefixes.some((p) => seen.has(p)) || new Set(prefixes).size !== prefixes.length) {
      out.push({ field, key: "prefix_duplicate" });
    }
    prefixes.forEach((p) => seen.add(p));
  });
  const days = d.expiryDays.trim();
  if (!/^[0-9]{1,3}$/.test(days) || digitsToInt(days) > 365) out.push({ field: "expiryDays", key: "range" });
  return out;
}

/** Days (0..365) as an integer from a digits-only string. */
function digitsToInt(s: string): number {
  let n = 0;
  for (const ch of s) n = n * 10 + "0123456789".indexOf(ch);
  return n;
}

export function toPatch(d: SettingsDraft, version: number): StockSettingsPatch {
  return {
    weight_barcode_templates: d.templates.map((t) => ({
      prefixes: parsePrefixes(t.prefixes),
      item_code_len: t.itemCodeLen,
      value_len: EAN13_PAYLOAD - t.itemCodeLen,
      value_kind: t.valueKind,
      decimals: t.decimals,
      enabled: t.enabled,
    })),
    low_stock_check_enabled: d.lowStockCheck,
    expiry_warning_days: digitsToInt(d.expiryDays.trim()),
    version,
  };
}

export const NEW_TEMPLATE: TemplateDraft = {
  prefixes: "",
  itemCodeLen: 5,
  valueKind: "WEIGHT",
  decimals: 3,
  enabled: true,
};

// --- events ------------------------------------------------------------------------------------------
export const scaleTemplatesOpened = createEvent();
export const templateAdded = createEvent();
export const templateRemoved = createEvent<number>();
export const templateChanged = createEvent<{ index: number; patch: Partial<TemplateDraft> }>();
export const lowStockToggled = createEvent<boolean>();
export const expiryDaysChanged = createEvent<string>();
export const scaleSaveRequested = createEvent();
export const scaleReloadRequested = createEvent();

// --- effects -----------------------------------------------------------------------------------------
export const loadStockSettingsFx = createEffect<void, StockSettingsOut, ApiError>(async () => {
  try {
    return await api.inventory.getStockSettings();
  } catch (e) {
    throw toApiError(e);
  }
});
export const saveStockSettingsFx = createEffect<StockSettingsPatch, StockSettingsOut, ApiError>(
  async (patch) => {
    try {
      return await api.inventory.updateStockSettings(patch);
    } catch (e) {
      throw toApiError(e);
    }
  },
);

// --- stores ------------------------------------------------------------------------------------------
export const $stockSettings = createStore<StockSettingsOut | null>(null, { skipVoid: false })
  .on(loadStockSettingsFx.doneData, (_, s) => s)
  .on(saveStockSettingsFx.doneData, (_, s) => s);
export const $scaleDraft = createStore<SettingsDraft | null>(null, { skipVoid: false })
  .on([loadStockSettingsFx.doneData, saveStockSettingsFx.doneData], (_, s) => toDraft(s))
  .on(templateAdded, (d) => (d ? { ...d, templates: [...d.templates, { ...NEW_TEMPLATE }] } : d))
  .on(templateRemoved, (d, i) => (d ? { ...d, templates: d.templates.filter((_, j) => j !== i) } : d))
  .on(templateChanged, (d, { index, patch }) =>
    d ? { ...d, templates: d.templates.map((t, j) => (j === index ? { ...t, ...patch } : t)) } : d,
  )
  .on(lowStockToggled, (d, v) => (d ? { ...d, lowStockCheck: v } : d))
  .on(expiryDaysChanged, (d, v) => (d ? { ...d, expiryDays: v.replace(/[^0-9]/g, "").slice(0, 3) } : d));
export const $scaleErrors = $scaleDraft.map((d) => (d ? draftErrors(d) : []));
export const $scaleDirty = combine($scaleDraft, $stockSettings, (d, s) =>
  d !== null && s !== null ? JSON.stringify(d) !== JSON.stringify(toDraft(s)) : false,
);
export const $scaleLoadError = createStore<ApiError | null>(null, { skipVoid: false })
  .on(loadStockSettingsFx.failData, (_, e) => e)
  .reset(loadStockSettingsFx);
export const $scaleSaveError = createStore<ApiError | null>(null, { skipVoid: false })
  .on(saveStockSettingsFx.failData, (_, e) => e)
  .reset(saveStockSettingsFx, loadStockSettingsFx.done);
/** 409 VERSION_CONFLICT — someone saved meanwhile: reload before saving again (17 §8). */
export const $scaleConflict = $scaleSaveError.map((e) => e?.code === "VERSION_CONFLICT");
export const $scaleSaved = createStore(false)
  .on(saveStockSettingsFx.done, () => true)
  .reset(
    templateAdded,
    templateRemoved,
    templateChanged,
    lowStockToggled,
    expiryDaysChanged,
    saveStockSettingsFx,
  );
export const $scaleSaving = saveStockSettingsFx.pending;
export const $scaleLoading = loadStockSettingsFx.pending;

// --- wiring ------------------------------------------------------------------------------------------
sample({ clock: [scaleTemplatesOpened, scaleReloadRequested], target: loadStockSettingsFx });
sample({
  clock: scaleSaveRequested,
  source: {
    draft: $scaleDraft,
    server: $stockSettings,
    errors: $scaleErrors,
    saving: saveStockSettingsFx.pending,
  },
  filter: ({ draft, server, errors, saving }) =>
    draft !== null && server !== null && errors.length === 0 && !saving,
  fn: ({ draft, server }) => toPatch(draft as SettingsDraft, (server as StockSettingsOut).version),
  target: saveStockSettingsFx,
});

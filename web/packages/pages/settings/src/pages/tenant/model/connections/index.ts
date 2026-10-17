import { sample } from "effector";

import { toApiError } from "@shared/api";

import {
  createConsentFx,
  createTaxRegimeFx,
  fetchRecostSummaryFx,
  fetchSettingsFx,
  fetchTermsFx,
  fetchValuationFx,
  updateSettingsFx,
  updateValuationFx,
} from "../effects/index.ts";
import {
  pageMounted,
  recostSummaryOpened,
  settingsReloadRequested,
  valuationOpened,
} from "../events/index.ts";
import {
  $lastConsent,
  $recostSummary,
  $recostSummaryError,
  $settings,
  $settingsError,
  $terms,
  $termsError,
  $valuation,
  $valuationError,
} from "../stores/index.ts";

sample({ clock: [pageMounted, settingsReloadRequested], target: fetchSettingsFx });
sample({ clock: pageMounted, target: fetchTermsFx });
$lastConsent.reset(pageMounted);

$settings.on(fetchSettingsFx.doneData, (_, settings) => settings);
$settingsError.on(fetchSettingsFx.failData, (_, e) => e).reset(fetchSettingsFx.done);
$terms.on(fetchTermsFx.doneData, (_, list) => list.items);
$termsError.on(fetchTermsFx.failData, (_, e) => e).reset(fetchTermsFx.done);

// PATCH answers the TenantSettings part (no tax_regime / integrations) → merge.
$settings.on(updateSettingsFx.doneData, (current, updated) =>
  current ? { ...current, ...updated } : current,
);

// Tax-regime history and the consent flag (+ version) come back through GET.
sample({ clock: [createTaxRegimeFx.done, createConsentFx.done], target: fetchSettingsFx });
$settings.on(createConsentFx.doneData, (current, consent) =>
  current
    ? {
        ...current,
        settings: { ...current.settings, ai_cross_border_enabled: consent.ai_cross_border_enabled },
      }
    : current,
);
$lastConsent.on(createConsentFx.doneData, (_, consent) => consent);

// The consent text changed meanwhile (VALIDATION_ERROR terms_version, params.current_version) → reload it.
sample({
  clock: createConsentFx.failData,
  filter: (error) => toApiError(error).details.some((d) => d.field.endsWith("terms_version")),
  target: fetchTermsFx,
});

// --- zaxira baholash usuli (19 §17) ------------------------------------------------------------------
sample({ clock: valuationOpened, target: fetchValuationFx });
$valuation.on(fetchValuationFx.doneData, (_, v) => v);
$valuationError.on(fetchValuationFx.failData, (_, e) => e).reset(fetchValuationFx.done);
// PATCH answers `{current_method, pending_change}` (19 §17) — keep `effective_from` when it is absent.
$valuation.on(updateValuationFx.doneData, (current, updated) => ({
  ...updated,
  effective_from: updated.effective_from ?? current?.effective_from ?? null,
}));
// Refused (already changed this year) — show what the server has now.
sample({
  clock: updateValuationFx.failData,
  filter: (e) => e.code === "VALUATION_METHOD_CHANGE_NOT_ALLOWED",
  fn: () => undefined,
  target: fetchValuationFx,
});

// --- «Qayta hisoblash navbati» holat qatori (qaror #56c) ---------------------------------------------
sample({ clock: recostSummaryOpened, target: fetchRecostSummaryFx });
$recostSummary.on(fetchRecostSummaryFx.doneData, (_, s) => s);
$recostSummaryError.on(fetchRecostSummaryFx.failData, (_, e) => e).reset(fetchRecostSummaryFx.done);

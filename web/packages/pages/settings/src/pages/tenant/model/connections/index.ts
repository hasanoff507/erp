import { sample } from "effector";

import { toApiError } from "@shared/api";

import {
  createConsentFx,
  createTaxRegimeFx,
  fetchSettingsFx,
  fetchTermsFx,
  updateSettingsFx,
} from "../effects/index.ts";
import { pageMounted, settingsReloadRequested } from "../events/index.ts";
import { $lastConsent, $settings, $settingsError, $terms, $termsError } from "../stores/index.ts";

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

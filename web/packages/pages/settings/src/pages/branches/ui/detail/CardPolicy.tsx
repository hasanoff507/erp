import { useUnit } from "effector-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { Button, Card, ConfirmDialog, ErrorState, RadioCard, RadioGroup, toast } from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $tenantSettings,
  $tenantSettingsError,
  fetchTenantSettingsFx,
  updateCardFallbackFx,
  type CardManualFallback,
} from "../../model/index.ts";

const OPTIONS: readonly CardManualFallback[] = ["allow", "manager_approval", "forbid"];

/**
 * «Terminalsiz karta (rekvizitsiz)» — store-level `card_manual_fallback` (07 BO-12, qaror #71,
 * `settings.tenant`). Applies only to registers with an active integrated terminal; card data is never typed in.
 */
export function CardPolicy() {
  const { t } = useTranslation("settings");
  const [settings, error, reload, save, saving] = useUnit([
    $tenantSettings,
    $tenantSettingsError,
    fetchTenantSettingsFx,
    updateCardFallbackFx,
    updateCardFallbackFx.pending,
  ]);
  const online = useOnline();
  const [choice, setChoice] = useState<CardManualFallback | null>(null);
  const [confirmForbid, setConfirmForbid] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  if (error) {
    return (
      <Card>
        <ErrorState
          message={errorText(error)}
          onRetry={() => void reload().catch(() => undefined)}
          className="py-6"
        />
      </Card>
    );
  }
  if (!settings) return null;

  const current = settings.settings.card_manual_fallback;
  const value = choice ?? current;

  const persist = async () => {
    setSaveError(null);
    try {
      await save({ value, version: settings.version });
      setChoice(null);
      toast.success(t("branches.cardPolicy.saved"));
    } catch (e) {
      setSaveError(errorText(e));
      throw e;
    }
  };

  return (
    <Card className="flex flex-col gap-3">
      <div>
        <h2 className="text-[15px] font-bold">{t("branches.cardPolicy.title")}</h2>
        <p className="text-small text-foreground-secondary">{t("branches.cardPolicy.hint")}</p>
      </div>
      <RadioGroup
        aria-label={t("branches.cardPolicy.title")}
        value={value}
        onValueChange={(v) => setChoice(OPTIONS.find((o) => o === v) ?? current)}
        className="grid gap-2 sm:grid-cols-3"
        disabled={!online}
      >
        {OPTIONS.map((o) => (
          <RadioCard
            key={o}
            value={o}
            title={t(`branches.cardPolicy.${o}`)}
            description={t(`branches.cardPolicy.${o}Hint`)}
          />
        ))}
      </RadioGroup>
      <p className="text-[12px] text-muted-foreground">{t("branches.cardPolicy.noTerminalNote")}</p>
      {saveError && !confirmForbid ? (
        <p role="alert" className="text-small font-semibold text-destructive">
          {saveError}
        </p>
      ) : null}
      <div className="flex justify-end">
        <Button
          disabled={!online || saving || value === current}
          onClick={() =>
            value === "forbid" ? setConfirmForbid(true) : void persist().catch(() => undefined)
          }
        >
          {t("branches.cardPolicy.save")}
        </Button>
      </div>
      {confirmForbid ? (
        <ConfirmDialog
          open
          onOpenChange={(o) => (o ? undefined : setConfirmForbid(false))}
          title={t("branches.cardPolicy.forbidConfirmTitle")}
          description={t("branches.cardPolicy.forbidConfirm")}
          onConfirm={persist}
          error={saveError}
        />
      ) : null}
    </Card>
  );
}

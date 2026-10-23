/**
 * BO-14 «Tarozi shtrix-kodi» card (07 BO-14; 19 §17): template table (prefixes 20–29, PLU length 4–6 — the
 * value length follows, EAN-13 = 2 + PLU + value + check digit; WEIGHT/AMOUNT, decimals, enabled), low-stock
 * check, expiry warning days, «Saqlash». Shown only with `catalog.manage` (the server checks again).
 */
import { useUnit } from "effector-react";
import { Plus, RotateCcw, Scale, Trash2, TriangleAlert } from "lucide-react";
import { useEffect } from "react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { useCan } from "@shared/state/permissions";
import { Banner, Button, Card, Icon, Input, NativeSelect, Switch } from "@shared/ui";

import {
  $scaleConflict,
  $scaleDirty,
  $scaleDraft,
  $scaleErrors,
  $scaleLoadError,
  $scaleSaved,
  $scaleSaveError,
  $scaleSaving,
  EAN13_PAYLOAD,
  MAX_TEMPLATES,
  expiryDaysChanged,
  lowStockToggled,
  scaleReloadRequested,
  scaleSaveRequested,
  scaleTemplatesOpened,
  templateAdded,
  templateChanged,
  templateRemoved,
  type TemplateDraft,
  type ValueKind,
} from "../model/index.ts";

export function ScaleTemplatesCard() {
  const { t } = useTranslation("settings");
  const allowed = useCan({ permission: "catalog.manage" });
  const [draft, errors, dirty, saving, saved, saveError, conflict, loadError] = useUnit([
    $scaleDraft, $scaleErrors, $scaleDirty, $scaleSaving, $scaleSaved, $scaleSaveError, $scaleConflict, $scaleLoadError,
  ]); // prettier-ignore

  useEffect(() => {
    if (allowed) scaleTemplatesOpened();
  }, [allowed]);

  if (!allowed) return null;

  const prefixError = (i: number) => errors.find((e) => e.field === `templates.${i}.prefixes`)?.key ?? null;
  const daysError = errors.some((e) => e.field === "expiryDays");

  return (
    <Card className="flex flex-col gap-4 p-5" data-testid="scale-templates-card">
      <header className="flex items-center gap-2">
        <Icon as={Scale} size="md" className="text-muted-foreground" />
        <div className="flex-1">
          <h2 className="text-[16px] font-extrabold">{t("scaleTemplates.title")}</h2>
          <p className="text-[12px] text-muted-foreground">{t("scaleTemplates.format")}</p>
        </div>
      </header>

      {loadError ? (
        <Banner tone="destructive" icon={TriangleAlert}>
          {serverErrorText(loadError)}
        </Banner>
      ) : null}
      {conflict ? (
        <Banner
          tone="warning"
          icon={TriangleAlert}
          action={
            <Button size="sm" variant="secondary" onClick={() => scaleReloadRequested()}>
              <Icon as={RotateCcw} size="sm" />
              {t("scaleTemplates.reload")}
            </Button>
          }
        >
          {t("scaleTemplates.conflict")}
        </Banner>
      ) : saveError ? (
        <Banner tone="destructive" icon={TriangleAlert}>
          {serverErrorText(saveError)}
        </Banner>
      ) : null}
      {saved ? (
        <Banner tone="success" icon={Scale}>
          {t("scaleTemplates.saved")}
        </Banner>
      ) : null}

      {draft ? (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="text-left text-[12px] text-muted-foreground">
                <tr>
                  <th className="py-1 pr-2">{t("scaleTemplates.cols.prefixes")}</th>
                  <th className="py-1 pr-2">{t("scaleTemplates.cols.kind")}</th>
                  <th className="py-1 pr-2">{t("scaleTemplates.cols.plu")}</th>
                  <th className="py-1 pr-2">{t("scaleTemplates.cols.value")}</th>
                  <th className="py-1 pr-2">{t("scaleTemplates.cols.decimals")}</th>
                  <th className="py-1 pr-2">{t("scaleTemplates.cols.enabled")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {draft.templates.map((tpl, i) => (
                  <TemplateRow key={i} index={i} tpl={tpl} error={prefixError(i)} />
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <Button
              variant="dashed"
              size="sm"
              onClick={() => templateAdded()}
              disabled={draft.templates.length >= MAX_TEMPLATES}
            >
              <Icon as={Plus} size="sm" />
              {t("scaleTemplates.add")}
            </Button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex items-center gap-3 text-[14px]">
              <Switch checked={draft.lowStockCheck} onCheckedChange={(v) => lowStockToggled(v)} />
              {t("scaleTemplates.lowStock")}
            </label>
            <label className="flex flex-col gap-1 text-[14px]">
              {t("scaleTemplates.expiryDays")}
              <Input
                inputMode="numeric"
                value={draft.expiryDays}
                onChange={(e) => expiryDaysChanged(e.target.value)}
                className="w-28"
                aria-invalid={daysError}
              />
              {daysError ? (
                <span className="text-[12px] text-destructive-strong">
                  {t("scaleTemplates.errors.range")}
                </span>
              ) : null}
            </label>
          </div>
          <p className="text-[12px] text-muted-foreground">{t("scaleTemplates.posNote")}</p>
          <div className="flex justify-end">
            <Button
              onClick={() => scaleSaveRequested()}
              disabled={!dirty || saving || errors.length > 0}
              data-testid="scale-templates-save"
            >
              {t("scaleTemplates.save")}
            </Button>
          </div>
        </>
      ) : null}
    </Card>
  );
}

function TemplateRow({ index, tpl, error }: { index: number; tpl: TemplateDraft; error: string | null }) {
  const { t } = useTranslation("settings");
  const patch = (p: Partial<TemplateDraft>) => templateChanged({ index, patch: p });
  return (
    <tr className="border-t border-border align-top">
      <td className="py-2 pr-2">
        <Input
          aria-label={t("scaleTemplates.cols.prefixes")}
          value={tpl.prefixes}
          maxLength={40}
          placeholder="22, 23"
          onChange={(e) => patch({ prefixes: e.target.value })}
          className="w-32 font-mono"
          aria-invalid={error !== null}
        />
        {error ? (
          <p className="mt-1 text-[12px] text-destructive-strong">
            {t(`scaleTemplates.errors.${error}` as "scaleTemplates.errors.prefix_format")}
          </p>
        ) : null}
      </td>
      <td className="py-2 pr-2">
        <NativeSelect
          aria-label={t("scaleTemplates.cols.kind")}
          value={tpl.valueKind}
          onChange={(e) => {
            const kind = e.target.value as ValueKind;
            patch({ valueKind: kind, decimals: kind === "WEIGHT" ? 3 : 0 });
          }}
          options={[
            { value: "WEIGHT", label: t("scaleTemplates.kinds.WEIGHT") },
            { value: "AMOUNT", label: t("scaleTemplates.kinds.AMOUNT") },
          ]}
        />
      </td>
      <td className="py-2 pr-2">
        <NativeSelect
          aria-label={t("scaleTemplates.cols.plu")}
          value={String(tpl.itemCodeLen)}
          onChange={(e) =>
            patch({ itemCodeLen: e.target.value === "4" ? 4 : e.target.value === "6" ? 6 : 5 })
          }
          options={["4", "5", "6"].map((v) => ({ value: v, label: v }))}
        />
      </td>
      <td className="py-2 pr-2 pt-4 font-mono">{EAN13_PAYLOAD - tpl.itemCodeLen}</td>
      <td className="py-2 pr-2">
        <NativeSelect
          aria-label={t("scaleTemplates.cols.decimals")}
          value={String(tpl.decimals)}
          onChange={(e) => {
            const v = e.target.value;
            patch({ decimals: v === "1" ? 1 : v === "2" ? 2 : v === "3" ? 3 : 0 });
          }}
          options={["0", "1", "2", "3"].map((v) => ({ value: v, label: v }))}
        />
      </td>
      <td className="py-2 pr-2 pt-3">
        <Switch
          aria-label={t("scaleTemplates.cols.enabled")}
          checked={tpl.enabled}
          onCheckedChange={(v) => patch({ enabled: v })}
        />
      </td>
      <td className="py-2">
        <Button
          size="icon"
          variant="ghost"
          aria-label={t("scaleTemplates.remove")}
          onClick={() => templateRemoved(index)}
        >
          <Icon as={Trash2} size="sm" />
        </Button>
      </td>
    </tr>
  );
}

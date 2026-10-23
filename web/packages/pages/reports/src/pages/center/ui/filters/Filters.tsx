/**
 * BO-09 report filters (07): period — Bugun / Hafta / Oy / Chorak + «Dan» / «Gacha» (Boshqa); filial —
 * «Barcha filiallar» (consolidated, only for a user with several branches) or one branch. The default
 * branch is the topbar choice.
 */
import { useUnit } from "effector-react";
import { CloudOff } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { $branches } from "@shared/state/session";
import { Banner, Button, FormField, Input, SimpleSelect } from "@shared/ui";

import {
  $branchFilter,
  $range,
  $rangeInvalid,
  $today,
  QUICK_RANGES,
  branchFilterChanged,
  matchQuickRange,
  quickRange,
  rangeChanged,
} from "../../model/index.ts";

const ALL = "all";

export function BranchFilter() {
  const { t } = useTranslation("reports");
  const [branches, value, onChange] = useUnit([$branches, $branchFilter, branchFilterChanged]);
  if (branches.length < 2) return null;
  return (
    <FormField label={t("filters.branch")} className="w-56">
      <SimpleSelect
        options={[
          { value: ALL, label: t("filters.allBranches") },
          ...branches.map((b) => ({ value: b.id, label: b.name })),
        ]}
        value={value ?? ALL}
        onValueChange={(v) => onChange(v === ALL ? null : v)}
      />
    </FormField>
  );
}

export function PeriodFilter({ asOf = false }: { asOf?: boolean }) {
  const { t } = useTranslation("reports");
  const [range, invalid, today, onRange] = useUnit([$range, $rangeInvalid, $today, rangeChanged]);
  const quick = matchQuickRange(range, today);
  if (asOf) {
    return (
      <FormField label={t("filters.asOf")}>
        <Input
          type="date"
          value={range.to}
          max={today}
          className="w-40"
          onChange={(e) =>
            onRange({ from: range.from <= e.target.value ? range.from : e.target.value, to: e.target.value })
          }
        />
      </FormField>
    );
  }
  return (
    <>
      <div role="group" aria-label={t("filters.period")} className="flex flex-wrap gap-1.5 self-end">
        {QUICK_RANGES.map((k) => (
          <Button
            key={k}
            size="sm"
            variant={quick === k ? "default" : "secondary"}
            aria-pressed={quick === k}
            onClick={() => onRange(quickRange(k, today))}
          >
            {t(`filters.quick.${k}`)}
          </Button>
        ))}
      </div>
      <FormField label={t("filters.from")} error={invalid ? t("filters.rangeInvalid") : undefined}>
        <Input
          type="date"
          value={range.from}
          max={today}
          className="w-40"
          onChange={(e) => onRange({ ...range, from: e.target.value })}
        />
      </FormField>
      <FormField label={t("filters.to")}>
        <Input
          type="date"
          value={range.to}
          max={today}
          className="w-40"
          onChange={(e) => onRange({ ...range, to: e.target.value })}
        />
      </FormField>
    </>
  );
}

/** QT-M12-04: some devices have not synced — the figures are not complete. */
export function IncompleteBanner({ complete, count }: { complete: boolean; count: number }) {
  const { t } = useTranslation("reports");
  if (complete) return null;
  return (
    <Banner tone="warning" icon={CloudOff}>
      {t("incomplete", { count })}
    </Banner>
  );
}

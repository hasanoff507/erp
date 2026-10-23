/** BO-08 filters (07): sana (dan/gacha), hisob (+ tomon), hujjat turi; «Filtrlarni tozalash». */
import { useUnit } from "effector-react";
import { RotateCcw } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { Button, FormField, Icon, Input, SegmentedControl, SimpleSelect } from "@shared/ui";

import {
  $filters,
  $rangeInvalid,
  ACCOUNT_CODES,
  ALL,
  DOC_TYPES,
  filtersChanged,
  filtersReset,
  type AccountSide,
} from "../../model/index.ts";

export function Filters() {
  const { t } = useTranslation("finance");
  const [filters, rangeInvalid, change, reset] = useUnit([
    $filters,
    $rangeInvalid,
    filtersChanged,
    filtersReset,
  ]);

  const accountOptions = [
    { value: ALL, label: t("journal.filters.allAccounts") },
    ...ACCOUNT_CODES.map((code) => ({ value: code, label: `${code} — ${t(`accounts.${code}`)}` })),
  ];
  const docOptions = [
    { value: ALL, label: t("journal.filters.allDocs") },
    ...DOC_TYPES.map((type) => ({ value: type, label: t(`docTypes.${type}`) })),
  ];
  const sideOptions: { value: AccountSide; label: string }[] = [
    { value: "dt", label: t("journal.filters.sideDt") },
    { value: "kt", label: t("journal.filters.sideKt") },
  ];

  return (
    <div role="search" aria-label={t("journal.filters.label")} className="flex flex-wrap items-end gap-3">
      <FormField
        label={t("journal.filters.dateFrom")}
        className="w-44"
        error={rangeInvalid ? t("journal.filters.rangeInvalid") : null}
      >
        <Input
          type="date"
          value={filters.dateFrom}
          max={filters.dateTo || undefined}
          onChange={(e) => change({ dateFrom: e.target.value })}
        />
      </FormField>
      <FormField label={t("journal.filters.dateTo")} className="w-44">
        <Input
          type="date"
          value={filters.dateTo}
          min={filters.dateFrom || undefined}
          onChange={(e) => change({ dateTo: e.target.value })}
        />
      </FormField>
      <FormField label={t("journal.filters.account")} className="w-72">
        <SimpleSelect
          options={accountOptions}
          value={filters.account ?? ALL}
          onValueChange={(v) => change({ account: v === ALL ? null : v })}
        />
      </FormField>
      {filters.account ? (
        <SegmentedControl
          label={t("journal.filters.side")}
          options={sideOptions}
          value={filters.side}
          onChange={(side) => change({ side })}
        />
      ) : null}
      <FormField label={t("journal.filters.docType")} className="w-64">
        <SimpleSelect
          options={docOptions}
          value={filters.docType ?? ALL}
          onValueChange={(v) => change({ docType: v === ALL ? null : v })}
        />
      </FormField>
      <Button variant="ghost" onClick={() => reset()}>
        <Icon as={RotateCcw} size="sm" />
        {t("journal.filters.reset")}
      </Button>
    </div>
  );
}

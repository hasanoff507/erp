/**
 * BO-09 catalogue (07 BO-09, mockup Bo09Hisobotlar): report cards grouped Savdo / Ombor / Moliya / Soliq;
 * a report the user has no right to is not shown. Built: Bosqich 3 — «Kassa / smena tarixi», «QQS
 * registri (qaytarishlar bilan)»; Bosqich 4 — kunlik savdo, top tovarlar, kassirlar bo'yicha savdo,
 * ombor qoldig'i, kam qolgan tovarlar, foyda va zarar, chegirmalar va marja, qarzdorlik muddati; Bosqich 5 —
 * sinov balansi, buxgalteriya balansi, ombor qoldig'i (sana holatiga). The rest carry the «Tez orada» chip.
 */
import { ChevronRight, Hourglass } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { hasPermissions, useGrantedAccess, type PermissionRequirement } from "@shared/state/permissions";
import { Card, Icon, StatusChip, cn } from "@shared/ui";

import { REPORT_ACCESS, isReportKey, type ReportKey } from "../../model/index.ts";

type GroupKey = "sales" | "stock" | "finance" | "tax";
type CatalogKey =
  | ReportKey
  | "stock-moves"
  | "count-diffs"
  | "vat-form"
  | "turnover-form"
  | "financial-form";

interface CatalogItem {
  key: CatalogKey;
  requires: PermissionRequirement;
}

const STOCK: PermissionRequirement = { permission: "stock.view" };
const FINANCE: PermissionRequirement = { permission: "reports.finance.view" };
const TAX: PermissionRequirement = { permission: "tax.vat.view" };

const item = (key: ReportKey): CatalogItem => ({ key, requires: REPORT_ACCESS[key] });

export const CATALOG: readonly { group: GroupKey; items: readonly CatalogItem[] }[] = [
  {
    group: "sales",
    items: [item("daily-sales"), item("top-products"), item("cash-history"), item("cashier-sales")],
  },
  {
    group: "stock",
    items: [
      item("stock"),
      { key: "stock-moves", requires: STOCK },
      item("low-stock"),
      { key: "count-diffs", requires: STOCK },
      item("stock-as-of"),
    ],
  },
  {
    group: "finance",
    items: [
      item("profit-and-loss"),
      item("discounts"),
      item("trial-balance"),
      item("balance-sheet"),
      item("debts-aging"),
    ],
  },
  {
    group: "tax",
    items: [
      item("vat-returns"),
      { key: "vat-form", requires: TAX },
      { key: "turnover-form", requires: TAX },
      { key: "financial-form", requires: FINANCE },
    ],
  },
];

export function Catalog({ onOpen }: { onOpen: (key: ReportKey) => void }) {
  const { t } = useTranslation("reports");
  const granted = useGrantedAccess();
  const groups = CATALOG.map((g) => ({
    ...g,
    items: g.items.filter((i) => hasPermissions(granted, i.requires)),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="flex flex-col gap-[18px]">
      {groups.map((g) => (
        <section key={g.group} aria-labelledby={`reports-group-${g.group}`} className="flex flex-col gap-2.5">
          <h2 id={`reports-group-${g.group}`} className="text-overline text-foreground-secondary">
            {t(`center.groups.${g.group}`)}
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {g.items.map((entry) => {
              const key = entry.key;
              const ready = isReportKey(key);
              const body = (
                <>
                  <div className="flex items-start gap-2">
                    <h3 className="min-w-0 flex-1 text-[14px] font-bold">{t(`center.items.${key}.title`)}</h3>
                    {ready ? (
                      <Icon as={ChevronRight} size="sm" className="text-muted-foreground" />
                    ) : (
                      <StatusChip tone="neutral" icon={Hourglass}>
                        {t("center.soon")}
                      </StatusChip>
                    )}
                  </div>
                  <p className="text-[12px] text-foreground-secondary">
                    {t(`center.items.${key}.description`)}
                  </p>
                </>
              );
              return ready ? (
                <button
                  key={key}
                  type="button"
                  onClick={() => onOpen(key)}
                  className={cn(
                    "flex flex-col gap-1.5 rounded-2xl border border-border bg-card p-5 text-left shadow-card transition-colors",
                    "hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  )}
                >
                  {body}
                </button>
              ) : (
                <Card key={key} className="flex flex-col gap-1.5 opacity-75" aria-disabled="true">
                  {body}
                </Card>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

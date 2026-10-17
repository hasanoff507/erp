/**
 * BO-09 catalogue (07 BO-09, mockup Bo09Hisobotlar): report cards grouped Savdo / Ombor / Moliya / Soliq;
 * a report the user has no right to is not shown. Built in Bosqich 3: «Kassa / smena tarixi» and
 * «QQS registri (qaytarishlar bilan)»; the rest carry the «Tez orada» chip (not clickable).
 */
import { ChevronRight, Hourglass } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { hasPermissions, useGrantedAccess, type PermissionRequirement } from "@shared/state/permissions";
import { Card, Icon, StatusChip, cn } from "@shared/ui";

import type { ReportKey } from "../../model/index.ts";

type GroupKey = "sales" | "stock" | "finance" | "tax";
type CatalogKey =
  | ReportKey
  | "daily-sales"
  | "top-products"
  | "cashier-sales"
  | "stock"
  | "stock-moves"
  | "low-stock"
  | "count-diffs"
  | "profit-and-loss"
  | "trial-balance"
  | "balance-sheet"
  | "debts-aging"
  | "vat-form"
  | "turnover-form"
  | "financial-form";

interface CatalogItem {
  key: CatalogKey;
  requires: PermissionRequirement;
  /** Built in this stage (opens the report). */
  ready: boolean;
}

const SALES: PermissionRequirement = { permission: "reports.sales.view" };
const FINANCE: PermissionRequirement = { permission: "reports.finance.view" };
const TAX: PermissionRequirement = { permission: "tax.vat.view" };

export const CATALOG: readonly { group: GroupKey; items: readonly CatalogItem[] }[] = [
  {
    group: "sales",
    items: [
      { key: "daily-sales", requires: SALES, ready: false },
      { key: "top-products", requires: SALES, ready: false },
      {
        key: "cash-history",
        requires: { anyOf: ["reports.sales.view", "cash.count.shift"] },
        ready: true,
      },
      { key: "cashier-sales", requires: SALES, ready: false },
    ],
  },
  {
    group: "stock",
    items: [
      { key: "stock", requires: SALES, ready: false },
      { key: "stock-moves", requires: SALES, ready: false },
      { key: "low-stock", requires: SALES, ready: false },
      { key: "count-diffs", requires: SALES, ready: false },
    ],
  },
  {
    group: "finance",
    items: [
      { key: "profit-and-loss", requires: FINANCE, ready: false },
      { key: "trial-balance", requires: FINANCE, ready: false },
      { key: "balance-sheet", requires: FINANCE, ready: false },
      { key: "debts-aging", requires: FINANCE, ready: false },
    ],
  },
  {
    group: "tax",
    items: [
      { key: "vat-returns", requires: TAX, ready: true },
      { key: "vat-form", requires: TAX, ready: false },
      { key: "turnover-form", requires: TAX, ready: false },
      { key: "financial-form", requires: FINANCE, ready: false },
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
            {g.items.map((item) => {
              const body = (
                <>
                  <div className="flex items-start gap-2">
                    <h3 className="min-w-0 flex-1 text-[14px] font-bold">
                      {t(`center.items.${item.key}.title`)}
                    </h3>
                    {item.ready ? (
                      <Icon as={ChevronRight} size="sm" className="text-muted-foreground" />
                    ) : (
                      <StatusChip tone="neutral" icon={Hourglass}>
                        {t("center.soon")}
                      </StatusChip>
                    )}
                  </div>
                  <p className="text-[12px] text-foreground-secondary">
                    {t(`center.items.${item.key}.description`)}
                  </p>
                </>
              );
              const key = item.key;
              return item.ready && (key === "cash-history" || key === "vat-returns") ? (
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

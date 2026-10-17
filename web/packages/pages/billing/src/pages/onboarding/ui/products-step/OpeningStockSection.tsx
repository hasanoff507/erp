/**
 * BO-21 ③b «Boshlang'ich qoldiq» (07 `openingStockMethod`, optional): Excel/CSV — the catalog import
 * flow with `kind="opening_stock"` injected by the shell (19 §6), or «Qo'lda» — stock-opening lines
 * (19 §16). Nothing here blocks «Davom».
 */
import { useUnit } from "effector-react";
import { Boxes, CircleCheck, FileSpreadsheet, PenLine, type LucideIcon } from "lucide-react";
import type { ComponentType } from "react";

import { useTranslation } from "@shared/i18n";
import { $isOnline } from "@shared/state/network";
import { Banner, Card, Icon, StatusChip, cn } from "@shared/ui";

import { OpeningStockForm } from "#/features/opening-stock/ui/OpeningStockForm.tsx";

import {
  $openingStockLines,
  $openingStockMethod,
  openingStockMethodSelected,
  openingStockSaved,
  type OpeningStockImportSlotProps,
  type OpeningStockMethod,
} from "../../model/index.ts";

const METHODS: readonly { id: OpeningStockMethod; icon: LucideIcon }[] = [
  { id: "import", icon: FileSpreadsheet },
  { id: "manual", icon: PenLine },
];

export function OpeningStockSection({
  openingStockImport: OpeningStockImport,
}: {
  openingStockImport?: ComponentType<OpeningStockImportSlotProps>;
}) {
  const { t } = useTranslation("onboarding");
  const [method, lines, online, select, saved] = useUnit([
    $openingStockMethod,
    $openingStockLines,
    $isOnline,
    openingStockMethodSelected,
    openingStockSaved,
  ]);
  const available = (id: OpeningStockMethod) => (id === "import" ? OpeningStockImport !== undefined : true);

  return (
    <Card role="region" className="flex flex-col gap-3" aria-labelledby="opening-stock-title">
      <div className="flex items-start gap-3">
        <Icon as={Boxes} size="lg" className="mt-0.5 text-primary" />
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <h3 id="opening-stock-title" className="flex flex-wrap items-center gap-2 text-[15px] font-bold">
            {t("products.openingStock.title")}
            <StatusChip tone="neutral">{t("products.openingStock.badge")}</StatusChip>
          </h3>
          <p className="text-[13px] text-foreground-secondary">{t("products.openingStock.text")}</p>
        </div>
      </div>

      <div role="group" aria-label={t("openingStock.methodLabel")} className="grid gap-3 sm:grid-cols-2">
        {METHODS.map(({ id, icon }) => {
          const selected = method === id;
          return (
            <button
              key={id}
              type="button"
              aria-pressed={selected}
              disabled={!available(id)}
              onClick={() => select(selected ? null : id)}
              className={cn(
                "flex items-start gap-3 rounded-xl border bg-card p-3.5 text-left transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                "disabled:cursor-not-allowed disabled:opacity-60",
                selected ? "border-2 border-primary bg-primary-soft" : "border-input hover:bg-accent",
              )}
            >
              <Icon as={icon} size="lg" className="text-primary" />
              <span className="flex flex-col gap-0.5">
                <span className="text-[14px] font-extrabold">{t(`openingStock.methods.${id}.title`)}</span>
                <span className="text-[12px] text-foreground-secondary">
                  {t(`openingStock.methods.${id}.text`)}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      {lines !== null ? (
        <Banner tone="success" icon={CircleCheck}>
          {t("openingStock.saved", { count: lines })}
        </Banner>
      ) : null}

      {method === "import" && OpeningStockImport ? (
        <div className="border-t border-divider pt-3">
          <OpeningStockImport embedded onDone={(result) => saved(result.lineCount)} />
        </div>
      ) : null}
      {method === "manual" ? (
        <div className="border-t border-divider pt-3">
          <OpeningStockForm online={online} />
        </div>
      ) : null}
    </Card>
  );
}

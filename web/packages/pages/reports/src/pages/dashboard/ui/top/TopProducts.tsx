/** «Eng ko'p sotilgan» (07 BO-02): top-5 by quantity, a bar relative to the first. */
import { ShoppingCart } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { Card, CardTitle, EmptyState } from "@shared/ui";

import { sharePercent } from "#/shared/lib/chart.ts";
import { formatUnitQty } from "#/shared/lib/units.ts";

import type { Dashboard } from "../../model/index.ts";

export function TopProducts({ items }: { items: Dashboard["top_products"] }) {
  const { t } = useTranslation("reports");
  const max = items[0]?.qty ?? "0";
  return (
    <Card className="min-w-0 flex-[1_1_420px]">
      <CardTitle className="mb-2.5">{t("dashboard.topProducts.title")}</CardTitle>
      {items.length === 0 ? (
        <EmptyState icon={ShoppingCart} title={t("dashboard.topProducts.empty")} />
      ) : (
        <ol aria-label={t("dashboard.topProducts.title")} className="flex flex-col">
          {items.map((p, i) => (
            <li
              key={p.product_id}
              className="flex items-center gap-3 border-b border-divider py-2.5 last:border-0"
            >
              <span className="w-7 text-[13px] font-extrabold text-muted-foreground">{i + 1}</span>
              <span className="min-w-0 flex-1 truncate text-[14px] font-semibold">{p.name}</span>
              <svg
                viewBox="0 0 100 8"
                preserveAspectRatio="none"
                className="hidden h-2 w-[120px] shrink-0 sm:block"
                aria-hidden="true"
                focusable="false"
              >
                <rect x="0" y="0" width="100" height="8" rx="4" className="fill-muted" />
                <rect
                  x="0"
                  y="0"
                  width={sharePercent(p.qty, max)}
                  height="8"
                  rx="4"
                  className="fill-primary"
                />
              </svg>
              <span className="w-[90px] text-right text-[13px] font-bold tabular-nums">
                {formatUnitQty(p.qty, p.unit_code)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

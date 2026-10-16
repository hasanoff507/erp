import { Bell, ChartColumn, Package, Receipt, ShoppingCart, Sparkles, TrendingUp, Users } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { Can } from "@shared/state/permissions";
import { Button, Card, CardTitle, EmptyState, Icon, Input, KpiCard } from "@shared/ui";

const PLACEHOLDER_VALUE = "—";

/**
 * BO-02 body — layout per design/canvas/project/Bo02Dashboard.dc.html; content is a Bosqich 0
 * placeholder (values arrive with GET /api/v1/reports/dashboard).
 */
export function Main() {
  const { t } = useTranslation("reports");
  const pending = t("dashboard.pending");

  return (
    <>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(210px,1fr))] gap-3.5">
        <KpiCard
          label={t("dashboard.kpi.sales")}
          value={PLACEHOLDER_VALUE}
          icon={ChartColumn}
          tone="primary"
        />
        <KpiCard label={t("dashboard.kpi.receipts")} value={PLACEHOLDER_VALUE} icon={Receipt} tone="info" />
        <KpiCard
          label={t("dashboard.kpi.customerDebt")}
          value={PLACEHOLDER_VALUE}
          icon={Users}
          tone="warning"
        />
        <KpiCard
          label={t("dashboard.kpi.stockValue")}
          value={PLACEHOLDER_VALUE}
          icon={Package}
          tone="destructive"
        />
      </div>

      <div className="flex flex-wrap gap-3.5">
        <Card className="min-w-0 flex-[2_1_520px]">
          <div className="mb-4 flex items-baseline justify-between">
            <CardTitle>{t("dashboard.salesChart.title")}</CardTitle>
            <span className="text-small text-muted-foreground">{t("dashboard.salesChart.unit")}</span>
          </div>
          <div className="flex h-[230px] items-end justify-center border-b border-border">
            <EmptyState icon={TrendingUp} title={pending} className="py-6" />
          </div>
        </Card>
        <Card className="flex min-w-0 flex-[1_1_320px] flex-col gap-2.5">
          <CardTitle>{t("dashboard.alerts.title")}</CardTitle>
          <EmptyState icon={Bell} title={pending} />
        </Card>
      </div>

      <div className="flex flex-wrap gap-3.5">
        <Card className="min-w-0 flex-[1_1_420px]">
          <CardTitle className="mb-2.5">{t("dashboard.topProducts.title")}</CardTitle>
          <EmptyState icon={ShoppingCart} title={pending} />
        </Card>
        <Can permission="ai.chat.use">
          <section className="flex min-w-0 flex-[1_1_420px] flex-col gap-3 rounded-2xl bg-sidebar p-5 text-sidebar-accent-foreground">
            <div className="flex items-center gap-2">
              <Icon as={Sparkles} size="lg" className="text-sidebar-ring" />
              <h2 className="text-h2 font-extrabold">{t("dashboard.ai.title")}</h2>
            </div>
            <p className="text-[14px] leading-relaxed text-sidebar-foreground">{pending}</p>
            <div className="mt-auto flex gap-2">
              <Input
                aria-label={t("dashboard.ai.placeholder")}
                placeholder={t("dashboard.ai.placeholder")}
                disabled
                className="border-sidebar-border bg-sidebar-accent text-sidebar-accent-foreground placeholder:text-sidebar-muted-foreground"
              />
              <Button disabled>{t("dashboard.ai.ask")}</Button>
            </div>
          </section>
        </Can>
      </div>
    </>
  );
}

import { useUnit } from "effector-react";
import { ChartColumn, MapPin, Package, Pencil, TriangleAlert } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { Banner, Button, Card, ErrorState, Icon, KpiCard, StatusChip } from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $addressReminders,
  $branchDetail,
  $branchDetailError,
  $verifyHints,
  addressReminderDismissed,
  branchDataReloadRequested,
  verifyHintDismissed,
  type Branch,
} from "../../model/index.ts";

/** Selected branch head: category (rate), address, today's sales and stock value (US-M14-01). */
export function BranchSummary({
  branch,
  canEdit,
  onEdit,
}: {
  branch: Branch;
  canEdit: boolean;
  onEdit: () => void;
}) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const [detail, error, verifyHints, reminders, reload, dismissHint, dismissReminder] = useUnit([
    $branchDetail,
    $branchDetailError,
    $verifyHints,
    $addressReminders,
    branchDataReloadRequested,
    verifyHintDismissed,
    addressReminderDismissed,
  ]);
  const online = useOnline();

  return (
    <div className="flex flex-col gap-3">
      <Card className="flex flex-col gap-3">
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="flex flex-wrap items-center gap-2 text-h2">
              {branch.name}
              <span className="text-[13px] font-semibold text-muted-foreground">#{branch.code}</span>
              {branch.is_default ? <StatusChip tone="info">{t("branches.default")}</StatusChip> : null}
            </h2>
            <p className="mt-1 flex items-center gap-1.5 text-small text-foreground-secondary">
              <Icon as={MapPin} size="sm" />
              {branch.address ?? t("branches.noAddress")}
            </p>
            <p className="mt-1 text-small">
              <span className="text-foreground-secondary">{t("branches.fields.settlementCategory")}: </span>
              <strong>{t(`branches.category.${branch.settlement_category}`)}</strong>
            </p>
          </div>
          {canEdit ? (
            <Button variant="secondary" size="sm" disabled={!online} onClick={onEdit}>
              <Icon as={Pencil} size="sm" />
              {tc("actions.edit")}
            </Button>
          ) : null}
        </div>
        {error ? (
          <ErrorState message={errorText(error)} onRetry={reload} className="py-4" />
        ) : (
          <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
            <KpiCard
              label={t("branches.kpi.todaySales")}
              value={detail ? formatMoney(detail.today_sales) : "—"}
              icon={ChartColumn}
              tone="primary"
            />
            <KpiCard
              label={t("branches.kpi.stockValue")}
              value={detail ? formatMoney(detail.stock_value) : "—"}
              icon={Package}
              tone="info"
            />
          </div>
        )}
      </Card>
      {verifyHints.includes(branch.id) ? (
        <Banner
          tone="warning"
          icon={TriangleAlert}
          action={
            canEdit ? (
              <Button size="sm" variant="secondary" onClick={onEdit}>
                {t("branches.verifyHint.check")}
              </Button>
            ) : (
              <Button size="sm" variant="ghost" onClick={() => dismissHint(branch.id)}>
                {tc("actions.close")}
              </Button>
            )
          }
        >
          {t("branches.verifyHint.text")}
        </Banner>
      ) : null}
      {reminders.includes(branch.id) ? (
        <Banner
          tone="warning"
          icon={TriangleAlert}
          live="assertive"
          action={
            <Button size="sm" variant="ghost" onClick={() => dismissReminder(branch.id)}>
              {tc("actions.close")}
            </Button>
          }
        >
          {t("branches.addressReminder")}
        </Banner>
      ) : null}
    </div>
  );
}

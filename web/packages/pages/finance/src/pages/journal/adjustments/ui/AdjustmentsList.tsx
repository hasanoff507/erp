/**
 * «Tuzatuvchi yozuvlar» (20 #10b): number, date, Dt / Kt, amount, corrected month, comment, status; a posted
 * entry is cancelled with a reason (20 #10a — storno in the open period; a consumed 6310 advance refuses the
 * storno with `validation.adjustment_exceeds_balance`). «Tuzatuvchi yozuv» opens the dialog.
 */
import { useUnit } from "effector-react";
import { FilePenLine, Plus, Undo2 } from "lucide-react";
import { useEffect, useState } from "react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatDate, formatMoney } from "@shared/lib/format";
import { $branches } from "@shared/state/session";
import { Button, Card, DataTable, EmptyState, Icon, StatusChip, type DataTableColumn } from "@shared/ui";

import { ReasonDialog } from "#/shared/ui/ReasonDialog.tsx";
import { useMonthLabel } from "#/shared/ui/useMonthLabel.ts";

import { reloadRequested } from "../../model/index.ts";
import {
  $adjustments,
  $adjustmentsCursor,
  $adjustmentsError,
  $adjustmentsMoreLoading,
  $adjustmentsStatus,
  adjustmentsMoreRequested,
  adjustmentsMounted,
  adjustmentsReloadRequested,
  cancelAdjustmentFx,
  type LedgerAdjustment,
} from "../model/index.ts";
import { AdjustmentDialog } from "./AdjustmentDialog.tsx";

export function AdjustmentsList({ online }: { online: boolean }) {
  const { t } = useTranslation("finance");
  const monthLabel = useMonthLabel();
  const [items, status, error, cursor, moreLoading, branches] = useUnit([
    $adjustments,
    $adjustmentsStatus,
    $adjustmentsError,
    $adjustmentsCursor,
    $adjustmentsMoreLoading,
    $branches,
  ]);
  const [mounted, more, reload, cancel, reloadJournal] = useUnit([
    adjustmentsMounted,
    adjustmentsMoreRequested,
    adjustmentsReloadRequested,
    cancelAdjustmentFx,
    reloadRequested,
  ]);
  const [creating, setCreating] = useState(false);
  const [cancelling, setCancelling] = useState<LedgerAdjustment | null>(null);

  useEffect(() => {
    mounted();
  }, [mounted]);

  const branchName = (id: string) => branches.find((b) => b.id === id)?.name ?? "—";
  const columns: DataTableColumn<LedgerAdjustment>[] = [
    {
      id: "doc",
      header: t("adjustments.columns.doc"),
      width: "170px",
      cell: (a) => (
        <span className="flex flex-col">
          <span className="font-semibold tabular-nums">{a.number ?? t("journal.table.noNumber")}</span>
          <span className="text-[12px] text-muted-foreground">
            {formatDate(a.doc_date)} · {branchName(a.branch_id)}
          </span>
        </span>
      ),
    },
    {
      id: "posting",
      header: t("adjustments.columns.posting"),
      width: "150px",
      cell: (a) => (
        <span className="font-bold tabular-nums">
          {t("adjustments.dtKt", { dt: a.account_dt, kt: a.account_kt })}
        </span>
      ),
    },
    {
      id: "comment",
      header: t("adjustments.columns.comment"),
      cell: (a) => (
        <span className="flex flex-col">
          <span>{a.comment}</span>
          {a.correction_of_period ? (
            <span className="text-[12px] text-muted-foreground">
              {t("adjustments.corrects", { period: monthLabel(a.correction_of_period) })}
            </span>
          ) : null}
          {a.cancel_reason ? (
            <span className="text-[12px] text-muted-foreground">
              {t("adjustments.cancelReason", { reason: a.cancel_reason })}
            </span>
          ) : null}
        </span>
      ),
    },
    {
      id: "status",
      header: t("adjustments.columns.status"),
      width: "130px",
      cell: (a) => (
        <StatusChip tone={a.status === "posted" ? "success" : "destructive"} dot>
          {t(`adjustments.status.${a.status}`)}
        </StatusChip>
      ),
    },
    {
      id: "amount",
      header: t("adjustments.columns.amount"),
      numeric: true,
      width: "150px",
      cell: (a) => formatMoney(a.amount, { precision: 2, withCurrency: false }),
    },
  ];

  return (
    <Card role="region" aria-labelledby="adjustments-title" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="adjustments-title" className="text-h2">
          {t("adjustments.title")}
        </h2>
        <span className="grow" />
        <Button size="sm" disabled={!online} onClick={() => setCreating(true)} data-testid="adjustment-new">
          <Icon as={Plus} size="sm" />
          {t("adjustments.new")}
        </Button>
      </div>
      <p className="text-small text-foreground-secondary">{t("adjustments.hint")}</p>
      <DataTable
        label={t("adjustments.title")}
        columns={columns}
        data={items}
        getRowId={(a) => a.id}
        status={status}
        errorMessage={error ? serverErrorText(error) : undefined}
        onRetry={reload}
        minWidth={760}
        rowActions={(a) =>
          a.status === "posted" && online
            ? [{ id: "cancel", label: t("adjustments.cancel"), icon: Undo2, destructive: true, onSelect: setCancelling }]
            : []
        }
        empty={
          <EmptyState
            icon={FilePenLine}
            title={t("adjustments.empty.title")}
            description={t("adjustments.empty.description")}
          />
        }
        pagination={{ kind: "cursor", hasMore: cursor !== null, loadingMore: moreLoading, onLoadMore: more }}
      />
      <AdjustmentDialog open={creating} onClose={() => setCreating(false)} />
      <ReasonDialog
        open={cancelling !== null}
        onOpenChange={(open) => (open ? undefined : setCancelling(null))}
        title={t("adjustments.cancelTitle", { number: cancelling?.number ?? "" })}
        description={t("adjustments.cancelDescription")}
        confirmLabel={t("adjustments.cancel")}
        onConfirm={async (reason) => {
          if (!cancelling) return;
          await cancel({ id: cancelling.id, reason });
          setCancelling(null);
          reloadJournal();
        }}
      />
    </Card>
  );
}

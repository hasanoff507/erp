/**
 * «E-ishonchnomalar» tab (07 BO-15, 19 §8a): powers of attorney the shop issued (created on BO-04) —
 * statuses draft … failed; «Imzolash va yuborish» (`einvoice.sign`, `pending_signature`/`failed` — E-IMZO →
 * `poa_send`), «Bekor qilish» (`purchases.create`, only before signing, reason required).
 */
import { useUnit } from "effector-react";
import { PenLine, X } from "lucide-react";
import { useState } from "react";

import { formatDate } from "@shared/lib/format";
import { useCan } from "@shared/state/permissions";
import { DataTable, type DataTableColumn, type DataTableRowAction } from "@shared/ui";

import { errorText } from "#/shared/lib/effect.ts";
import { useTx } from "#/shared/lib/i18n.ts";

import {
  $busy,
  $hasMore,
  $key,
  $poaError,
  $poaStatus,
  $poas,
  moreRequested,
  poaCancelSubmitted,
  poaSignRequested,
  reloadRequested,
  type Poa,
} from "../../model/index.ts";
import { ReasonDialog } from "../dialogs/ReasonDialog.tsx";
import { DocStatusChip } from "../shared/chips.tsx";

export function PoaTab() {
  const { t } = useTx();
  const canSign = useCan({ permission: "einvoice.sign" });
  const canCancel = useCan({ permission: "purchases.create" });
  const [rows, status, error, hasMore, key, busy] = useUnit([
    $poas,
    $poaStatus,
    $poaError,
    $hasMore,
    $key,
    $busy,
  ]);
  const [sign, cancel, more, reload] = useUnit([
    poaSignRequested,
    poaCancelSubmitted,
    moreRequested,
    reloadRequested,
  ]);
  const [cancelling, setCancelling] = useState<string | null>(null);

  const columns: DataTableColumn<Poa>[] = [
    {
      id: "supplier",
      header: t("columns.supplier"),
      cell: (p) => (
        <span className="flex flex-col">
          <span className="font-bold">{p.supplier.name ?? "—"}</span>
          <span className="text-[13px] text-foreground-secondary">{p.number ?? t("detail.noNumber")}</span>
        </span>
      ),
    },
    { id: "employee", header: t("columns.employee"), width: "180px", cell: (p) => p.employee_name ?? "—" },
    {
      id: "valid",
      header: t("columns.valid"),
      width: "200px",
      cell: (p) => `${formatDate(p.valid_from)} — ${formatDate(p.valid_to)}`,
    },
    {
      id: "status",
      header: t("columns.status"),
      width: "170px",
      cell: (p) => (
        <span className="flex flex-col gap-1">
          <DocStatusChip status={p.status} scope="poa" />
          {p.last_error && p.status === "failed" ? (
            <span className="text-[12px] text-destructive-strong">{p.last_error}</span>
          ) : null}
        </span>
      ),
    },
  ];
  const actions = (p: Poa): DataTableRowAction<Poa>[] => [
    ...(canSign && (p.status === "pending_signature" || p.status === "failed")
      ? [
          {
            id: "sign",
            label: t("actions.poaSign"),
            icon: PenLine,
            disabled: busy || key === null,
            onSelect: () => sign(p.id),
          },
        ]
      : []),
    ...(canCancel && (p.status === "draft" || p.status === "pending_signature")
      ? [
          {
            id: "cancel",
            label: t("actions.poaCancel"),
            icon: X,
            destructive: true,
            disabled: busy,
            onSelect: () => setCancelling(p.id),
          },
        ]
      : []),
  ];

  return (
    <>
      <DataTable
        label={t("tabs.poa")}
        columns={columns}
        data={rows}
        getRowId={(p) => p.id}
        status={status}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={() => reload("poa")}
        rowActions={actions}
        pagination={{ kind: "cursor", hasMore: hasMore.poa, onLoadMore: () => more("poa") }}
      />
      <ReasonDialog
        open={cancelling !== null}
        onOpenChange={(open) => (open ? undefined : setCancelling(null))}
        title={t("actions.poaCancel")}
        confirmLabel={t("actions.poaCancel")}
        pending={busy}
        onSubmit={(reason) => (cancelling ? cancel({ id: cancelling, reason }) : undefined)}
      />
    </>
  );
}

/**
 * BO-03 «Ko'chirishlar» tab (07, US-M06-03, task B2-T11): status filter, list (hujjat, yo'nalish, tashish
 * usuli, yuborilgan, pozitsiyalar, summa, holat + kechikkan, e-TTN), row actions «O'tkazish» /
 * «Jo'natish» (e-TTN `registered` yoki piyoda) / «Qabul qilish» / «Bekor qilish», detail sheet.
 * E-TTN signing and manual registration are Bosqich 5 — only the status is shown (posted vehicle
 * transfers say «E-TTN kutilmoqda» with a refresh).
 */
import { useUnit } from "effector-react";
import { ArrowLeftRight, Check, Info, PackageCheck, Send, TriangleAlert, X } from "lucide-react";
import { useEffect, useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatDateTime, formatMoney } from "@shared/lib/format";
import {
  Banner,
  Button,
  ConfirmDialog,
  DataTable,
  EmptyState,
  FormField,
  SimpleSelect,
  toast,
  type DataTableColumn,
  type DataTableRowAction,
} from "@shared/ui";

import { useBranchName, useQtyFormat } from "#/entities/refs/index.ts";
import { errorText } from "#/shared/lib/errors.ts";
import { ReasonDialog } from "#/shared/ui/ReasonDialog.tsx";

import {
  $acting,
  $actionError,
  $cursor,
  $error,
  $filter,
  $moreLoading,
  $notice,
  $status,
  $transfers,
  TRANSFER_STATUSES,
  actionErrorDismissed,
  actionsOf,
  cancelTransferFx,
  filterChanged,
  isTransferStatus,
  moreRequested,
  noticeDismissed,
  postRequested,
  postTransferFx,
  reloadRequested,
  sendTransferFx,
  transferSelected,
  transferValue,
  type Transfer,
  type TransferAction,
  type TransferRights,
} from "../model/index.ts";

import { EttnChip, TransferStatusChip } from "./chips.tsx";
import { ReceiveDialog } from "./ReceiveDialog.tsx";
import { TransferDetail } from "./TransferDetail.tsx";

const ALL = "all";

export interface TransfersTabProps {
  rights: TransferRights;
  online: boolean;
}

/** Number or «Qoralama» for a draft (the number is given on post). */
export function useTransferTitle(): (t: Transfer) => string {
  const { t } = useTranslation("warehouse");
  return (tr) => tr.number ?? t("transfers.draftNumber", { date: formatDate(tr.doc_date) });
}

/** Row action runner shared by the table and the detail sheet. */
export function useTransferActions() {
  const { t } = useTranslation("warehouse");
  const [requestPost, send, cancel] = useUnit([postRequested, sendTransferFx, cancelTransferFx]);
  const [receiving, setReceiving] = useState<Transfer | null>(null);
  const [cancelling, setCancelling] = useState<Transfer | null>(null);
  const [confirmSend, setConfirmSend] = useState<Transfer | null>(null);

  const run = (action: TransferAction, tr: Transfer) => {
    if (action === "receive") return setReceiving(tr);
    if (action === "cancel") return setCancelling(tr);
    if (action === "send") return setConfirmSend(tr);
    requestPost(tr.id);
  };

  useEffect(
    () =>
      postTransferFx.doneData.watch((res) =>
        toast.success(t("transfers.toast.posted", { number: res.number ?? "" })),
      ),
    [t],
  );

  const dialogs = (
    <>
      <ReceiveDialog transfer={receiving} onClose={() => setReceiving(null)} />
      <ConfirmDialog
        open={confirmSend !== null}
        onOpenChange={(open) => (open ? undefined : setConfirmSend(null))}
        title={t("transfers.send.title")}
        description={t("transfers.send.description")}
        confirmLabel={t("transfers.actions.send")}
        onConfirm={() => {
          const tr = confirmSend;
          setConfirmSend(null);
          if (!tr) return;
          send(tr.id)
            .then((res) => toast.success(t("transfers.toast.sent", { number: res.number ?? "" })))
            .catch(() => undefined);
        }}
      />
      <ReasonDialog
        open={cancelling !== null}
        onOpenChange={(open) => (open ? undefined : setCancelling(null))}
        title={t("transfers.cancel.title")}
        description={t("transfers.cancel.description")}
        onConfirm={async (reason) => {
          if (!cancelling) return;
          await cancel({ id: cancelling.id, reason });
          toast.success(t("transfers.toast.cancelled"));
        }}
      />
    </>
  );
  return { run, dialogs };
}

const ACTION_ICON = { post: Check, send: Send, receive: PackageCheck, cancel: X } as const;

export function TransfersTab({ rights, online }: TransfersTabProps) {
  const { t } = useTranslation("warehouse");
  const [items, status, error, cursor, moreLoading, filter, actionError, notice, acting] = useUnit([
    $transfers,
    $status,
    $error,
    $cursor,
    $moreLoading,
    $filter,
    $actionError,
    $notice,
    $acting,
  ]);
  const [onFilter, more, reload, select, dismissError, dismissNotice] = useUnit([
    filterChanged,
    moreRequested,
    reloadRequested,
    transferSelected,
    actionErrorDismissed,
    noticeDismissed,
  ]);
  const branchName = useBranchName();
  const formatQty = useQtyFormat();
  const title = useTransferTitle();
  const { run, dialogs } = useTransferActions();

  const columns: DataTableColumn<Transfer>[] = [
    {
      id: "doc",
      header: t("transfers.columns.doc"),
      width: "170px",
      cell: (tr) => (
        <span className="flex flex-col">
          <span className="font-semibold">{title(tr)}</span>
          <span className="text-[12px] text-muted-foreground">{formatDate(tr.doc_date)}</span>
        </span>
      ),
    },
    {
      id: "route",
      header: t("transfers.columns.route"),
      cell: (tr) => (
        <span className="flex flex-col">
          <span className="font-semibold">
            {branchName(tr.from_branch_id)} → {branchName(tr.to_branch_id)}
          </span>
          <span className="text-[12px] text-muted-foreground">
            {t(`transfers.mode.${tr.transport_mode}`)}
            {tr.vehicle_plate ? ` · ${tr.vehicle_plate}` : ""}
          </span>
        </span>
      ),
    },
    {
      id: "sent",
      header: t("transfers.columns.sent"),
      width: "140px",
      cell: (tr) => (tr.sent_at ? <span className="tabular-nums">{formatDateTime(tr.sent_at)}</span> : "—"),
    },
    {
      id: "positions",
      header: t("transfers.columns.positions"),
      numeric: true,
      width: "70px",
      cell: (tr) => formatQty(String(tr.lines.length)),
    },
    {
      id: "sum",
      header: t("transfers.columns.sum"),
      numeric: true,
      width: "130px",
      cell: (tr) => {
        const value = transferValue(tr);
        return value ? formatMoney(value, { withCurrency: false }) : "—";
      },
    },
    {
      id: "status",
      header: t("transfers.columns.status"),
      width: "150px",
      cell: (tr) => <TransferStatusChip transfer={tr} />,
    },
    {
      id: "ettn",
      header: t("transfers.columns.ettn"),
      width: "160px",
      cell: (tr) => <EttnChip transfer={tr} />,
    },
  ];

  const rowActions = (tr: Transfer): DataTableRowAction<Transfer>[] =>
    actionsOf(tr, rights).map((action) => ({
      id: action,
      label: t(`transfers.actions.${action}`),
      icon: ACTION_ICON[action],
      destructive: action === "cancel",
      disabled: !online || acting,
      onSelect: (row: Transfer) => run(action, row),
    }));

  return (
    <section className="flex flex-col gap-3" aria-label={t("tabs.transfers")}>
      <div className="flex flex-wrap items-end gap-3">
        <FormField label={t("transfers.filter")} className="w-56">
          <SimpleSelect
            options={[
              { value: ALL, label: t("transfers.allStatuses") },
              ...TRANSFER_STATUSES.map((s) => ({ value: s, label: t(`transfers.status.${s}`) })),
            ]}
            value={filter ?? ALL}
            onValueChange={(v) => onFilter(isTransferStatus(v) ? v : null)}
          />
        </FormField>
      </div>
      {actionError ? (
        <Banner
          tone="destructive"
          icon={TriangleAlert}
          live="assertive"
          action={
            <Button size="sm" variant="secondary" onClick={() => dismissError()}>
              {t("actions.close")}
            </Button>
          }
        >
          {errorText(actionError)}
        </Banner>
      ) : null}
      {notice ? (
        <Banner
          tone="warning"
          icon={Info}
          action={
            <Button size="sm" variant="secondary" onClick={() => dismissNotice()}>
              {t("actions.close")}
            </Button>
          }
        >
          {t("transfers.ettnCancelInOperator")}
        </Banner>
      ) : null}
      <DataTable
        label={t("transfers.tableLabel")}
        columns={columns}
        data={items}
        getRowId={(tr) => tr.id}
        status={status}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={reload}
        onRowClick={(tr) => select(tr.id)}
        rowActions={rowActions}
        minWidth={1060}
        empty={
          <EmptyState
            icon={ArrowLeftRight}
            title={t("transfers.empty.title")}
            description={t("transfers.empty.description")}
          />
        }
        pagination={{ kind: "cursor", hasMore: cursor !== null, loadingMore: moreLoading, onLoadMore: more }}
      />
      <TransferDetail rights={rights} online={online} onAction={run} />
      {dialogs}
    </section>
  );
}

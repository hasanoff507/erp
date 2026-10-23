/**
 * BO-04 «Xaridnomalar» (07): ro'yxat–tafsilot — left: list (qidiruv: raqam yoki yetkazib beruvchi;
 * raqam, sana, summa, yetkazib beruvchi, holat chipi); right: the selected order (sarlavha — yetkazib
 * beruvchi, STIR, sana, kim tuzdi; holat bosqichlari; qatorlar; jami; qabul qilingan miqdorlar;
 * «Joriy qarzimiz»), actions «Tahrirlash» / «Yuborish» / «Bekor qilish» / «Kirim yaratish».
 * The payment panel and e-ishonchnoma card are later stages (B4/B5) — not rendered.
 */
import { useUnit } from "effector-react";
import { FileText, PackagePlus, Pencil, Send, TriangleAlert, X } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatDateTime, formatMoney } from "@shared/lib/format";
import {
  Banner,
  Button,
  Card,
  ConfirmDialog,
  DataTable,
  EmptyState,
  FormField,
  Icon,
  SearchInput,
  SimpleSelect,
  StatusChip,
  StepList,
  toast,
  type DataTableColumn,
  type StepItem,
  type Tone,
} from "@shared/ui";

import { useQtyFormat, type Warehouse } from "#/entities/refs/index.ts";
import { compareQty } from "#/shared/lib/decimal.ts";
import { errorText } from "#/shared/lib/errors.ts";
import { ReasonDialog } from "#/shared/ui/ReasonDialog.tsx";

import {
  $acting,
  $actionError,
  $cursor,
  $debt,
  $detail,
  $error,
  $filters,
  $moreLoading,
  $orders,
  $selectedId,
  $status,
  ORDER_STATUSES,
  actionErrorDismissed,
  canCancel,
  canEdit,
  canReceive,
  cancelOrderFx,
  isOrderStatus,
  moreRequested,
  orderSelected,
  reloadRequested,
  searchChanged,
  sendOrderFx,
  statusChanged,
  type Order,
  type OrderRow,
  type OrderStatus,
} from "../model/index.ts";

import { OrderSheet } from "./OrderSheet.tsx";

const ALL = "all";
const STATUS_TONE: Readonly<Record<string, Tone>> = {
  draft: "neutral",
  sent: "info",
  partially_received: "awaiting-approval",
  closed: "success",
  cancelled: "neutral",
};

export function OrderStatusChip({ status }: { status: string }) {
  const { t } = useTranslation("warehouse");
  return (
    <StatusChip tone={STATUS_TONE[status] ?? "neutral"}>
      {t(`orders.status.${status as OrderStatus}`)}
    </StatusChip>
  );
}

export interface OrderRights {
  create: boolean;
  /** `purchases.receive` — «Kirim yaratish» from a sent order. */
  receive: boolean;
}

export interface OrdersTabProps {
  rights: OrderRights;
  online: boolean;
  warehouse: Warehouse | null;
  /** «Yangi xaridnoma» requested from outside (BO-03 «Xaridnoma tuzish»). */
  createOpen: boolean;
  onCreateOpenChange: (open: boolean) => void;
  onCreateReceipt: (order: Order) => void;
}

export function OrdersTab({
  rights,
  online,
  warehouse,
  createOpen,
  onCreateOpenChange,
  onCreateReceipt,
}: OrdersTabProps) {
  const { t } = useTranslation("warehouse");
  const [rows, status, error, cursor, moreLoading, filters, selectedId] = useUnit([
    $orders,
    $status,
    $error,
    $cursor,
    $moreLoading,
    $filters,
    $selectedId,
  ]);
  const [onSearch, onStatus, more, reload, select] = useUnit([
    searchChanged,
    statusChanged,
    moreRequested,
    reloadRequested,
    orderSelected,
  ]);
  const [editing, setEditing] = useState<Order | null>(null);

  const columns: DataTableColumn<OrderRow>[] = [
    {
      id: "doc",
      header: t("orders.columns.doc"),
      cell: (o) => (
        <span className="flex flex-col">
          <span className="font-semibold">{o.number ?? t("orders.draftNumber")}</span>
          <span className="text-[12px] text-muted-foreground">
            {formatDate(o.doc_date)} · {o.supplier.name ?? "—"}
          </span>
        </span>
      ),
    },
    {
      id: "sum",
      header: t("orders.columns.sum"),
      numeric: true,
      width: "120px",
      cell: (o) => (o.total ? formatMoney(o.total, { withCurrency: false }) : "—"),
    },
    {
      id: "status",
      header: t("orders.columns.status"),
      width: "150px",
      cell: (o) => <OrderStatusChip status={o.status} />,
    },
  ];

  return (
    <section className="flex flex-col gap-3" aria-label={t("purchases.tabs.orders")}>
      <div className="flex flex-wrap items-end gap-3">
        <SearchInput
          className="w-72"
          value={filters.search}
          onSearch={onSearch}
          aria-label={t("orders.search")}
          placeholder={t("orders.searchPlaceholder")}
        />
        <FormField label={t("orders.filter")} className="w-56">
          <SimpleSelect
            options={[
              { value: ALL, label: t("orders.allStatuses") },
              ...ORDER_STATUSES.map((s) => ({ value: s, label: t(`orders.status.${s}`) })),
            ]}
            value={filters.status ?? ALL}
            onValueChange={(v) => onStatus(isOrderStatus(v) ? v : null)}
          />
        </FormField>
      </div>
      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        <DataTable
          label={t("orders.tableLabel")}
          columns={columns}
          data={rows}
          getRowId={(o) => o.id}
          status={status}
          errorMessage={error ? errorText(error) : undefined}
          onRetry={reload}
          onRowClick={(o) => select(o.id)}
          selectedRowId={selectedId}
          minWidth={380}
          empty={
            <EmptyState
              icon={FileText}
              title={t("orders.empty.title")}
              description={t("orders.empty.description")}
            />
          }
          pagination={{
            kind: "cursor",
            hasMore: cursor !== null,
            loadingMore: moreLoading,
            onLoadMore: more,
          }}
        />
        <OrderDetail rights={rights} online={online} onEdit={setEditing} onCreateReceipt={onCreateReceipt} />
      </div>
      <OrderSheet
        open={createOpen || editing !== null}
        onClose={() => {
          setEditing(null);
          onCreateOpenChange(false);
        }}
        order={editing}
        warehouse={warehouse}
        online={online}
      />
    </section>
  );
}

function OrderDetail({
  rights,
  online,
  onEdit,
  onCreateReceipt,
}: {
  rights: OrderRights;
  online: boolean;
  onEdit: (o: Order) => void;
  onCreateReceipt: (o: Order) => void;
}) {
  const { t } = useTranslation("warehouse");
  const formatQty = useQtyFormat();
  const [order, debt, acting, actionError, send, cancel, dismissError] = useUnit([
    $detail,
    $debt,
    $acting,
    $actionError,
    sendOrderFx,
    cancelOrderFx,
    actionErrorDismissed,
  ]);
  const [confirmSend, setConfirmSend] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  if (!order) {
    return (
      <Card className="hidden xl:block">
        <EmptyState icon={FileText} title={t("orders.selectHint")} />
      </Card>
    );
  }

  const steps: StepItem[] = [
    { id: "draft", title: t("orders.steps.draft"), state: "done" },
    {
      id: "sent",
      title: t("orders.steps.sent"),
      description: order.sent_at ? formatDateTime(order.sent_at) : undefined,
      state: order.status === "draft" ? "current" : "done",
    },
    {
      id: "received",
      title: t("orders.steps.received"),
      state:
        order.status === "closed"
          ? "done"
          : order.status === "partially_received" || order.status === "sent"
            ? "current"
            : "next",
    },
  ];

  return (
    <Card className="flex flex-col gap-4" role="region" aria-label={t("orders.detailLabel")}>
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-h2">{order.number ?? t("orders.draftNumber")}</h2>
          <p className="text-small text-foreground-secondary">
            {[
              order.supplier.name,
              order.supplier.stir ? t("suppliers.stirValue", { stir: order.supplier.stir }) : null,
              formatDate(order.doc_date),
              order.created_by_name ? t("orders.createdBy", { name: order.created_by_name }) : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <OrderStatusChip status={order.status} />
      </div>
      {order.status !== "cancelled" ? (
        <StepList steps={steps} tone="light" label={t("orders.stepsLabel")} />
      ) : null}
      {actionError ? (
        <Banner tone="destructive" icon={TriangleAlert} live="assertive">
          {errorText(actionError)}
        </Banner>
      ) : null}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[520px] text-[13px]" aria-label={t("orders.linesLabel")}>
          <thead className="bg-muted text-caption text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left">{t("orders.lines.product")}</th>
              <th className="px-3 py-2 text-right">{t("orders.lines.qty")}</th>
              <th className="px-3 py-2 text-right">{t("orders.lines.received")}</th>
              <th className="px-3 py-2 text-right">{t("orders.lines.price")}</th>
              <th className="px-3 py-2 text-right">{t("orders.lines.amount")}</th>
            </tr>
          </thead>
          <tbody>
            {order.lines.map((l) => {
              const received =
                order.received_lines.find((r) => r.product_id === l.product_id)?.received_qty ?? "0.000";
              const full = compareQty(received, l.qty) >= 0;
              return (
                <tr key={l.id} className="border-t border-divider">
                  <td className="px-3 py-2 font-semibold">{l.product_name ?? "—"}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatQty(l.qty, l.unit_code)}</td>
                  <td className={`px-3 py-2 text-right tabular-nums ${full ? "text-success-strong" : ""}`}>
                    {formatQty(received, l.unit_code)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {l.price ? formatMoney(l.price, { withCurrency: false }) : "—"}
                  </td>
                  <td className="px-3 py-2 text-right font-bold tabular-nums">
                    {l.amount ? formatMoney(l.amount, { withCurrency: false }) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-muted px-4 py-3">
        <span className="text-small text-foreground-secondary">
          {t("orders.payable")}: <b className="tabular-nums">{debt ? formatMoney(debt.payable) : "…"}</b>
        </span>
        <span className="text-[15px] font-extrabold">
          {t("orders.total")}:{" "}
          <span className="tabular-nums">{order.total ? formatMoney(order.total) : "—"}</span>
        </span>
      </div>
      {order.cancel_reason ? (
        <p className="text-small text-foreground-secondary">
          {t("cancel.reason")}: {order.cancel_reason}
        </p>
      ) : null}
      <div className="flex flex-wrap justify-end gap-2">
        {rights.create && canCancel(order) ? (
          <Button
            variant="destructive-outline"
            disabled={!online || acting}
            onClick={() => setCancelling(true)}
          >
            <Icon as={X} size="sm" />
            {t("actions.cancelDoc")}
          </Button>
        ) : null}
        {rights.create && canEdit(order) ? (
          <Button variant="secondary" disabled={!online || acting} onClick={() => onEdit(order)}>
            <Icon as={Pencil} size="sm" />
            {t("actions.edit")}
          </Button>
        ) : null}
        {rights.receive && canReceive(order) ? (
          <Button variant="secondary" disabled={!online} onClick={() => onCreateReceipt(order)}>
            <Icon as={PackagePlus} size="sm" />
            {t("orders.createReceipt")}
          </Button>
        ) : null}
        {rights.create && order.status === "draft" ? (
          <Button
            disabled={!online || acting}
            onClick={() => {
              dismissError();
              setConfirmSend(true);
            }}
          >
            <Icon as={Send} size="sm" />
            {t("orders.send")}
          </Button>
        ) : null}
      </div>
      <ConfirmDialog
        open={confirmSend}
        onOpenChange={setConfirmSend}
        title={t("orders.sendConfirm.title")}
        description={t("orders.sendConfirm.description")}
        confirmLabel={t("orders.send")}
        error={actionError ? errorText(actionError) : null}
        onConfirm={() =>
          send(order.id).then((o) => toast.success(t("orders.toast.sent", { number: o.number ?? "" })))
        }
      />
      <ReasonDialog
        open={cancelling}
        onOpenChange={setCancelling}
        title={t("orders.cancelTitle")}
        onConfirm={async (reason) => {
          await cancel({ id: order.id, reason });
          toast.success(t("orders.toast.cancelled"));
        }}
      />
    </Card>
  );
}

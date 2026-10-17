/**
 * BO-04 «Kirimlar» (07): list (holat, qidiruv), detail sheet (qatorlar, QQSsiz summa / QQS / jami,
 * partiyalar), «Yangi kirim» (qo'lda yoki xaridnomadan), «Tahrirlash» (draft, `purchases.receive`),
 * «O'tkazish» (`purchases.post` — qoldiq shu paytda oshadi), «Bekor qilish» (`purchases.post`),
 * «Qaytarish» (posted, `purchases.return`).
 */
import { useUnit } from "effector-react";
import { Check, PackagePlus, Pencil, Plus, TriangleAlert, Undo2, X } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatDateTime, formatMoney } from "@shared/lib/format";
import {
  Banner,
  Button,
  ConfirmDialog,
  DataTable,
  EmptyState,
  ErrorState,
  FormField,
  Icon,
  SearchInput,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SimpleSelect,
  Skeleton,
  StatusChip,
  toast,
  type DataTableColumn,
  type Tone,
} from "@shared/ui";

import { useQtyFormat, type Warehouse } from "#/entities/refs/index.ts";
import { errorText } from "#/shared/lib/errors.ts";
import { ReasonDialog } from "#/shared/ui/ReasonDialog.tsx";

import {
  $acting,
  $actionError,
  $cursor,
  $detail,
  $detailError,
  $error,
  $filters,
  $moreLoading,
  $receipts,
  $selectedId,
  $status,
  RECEIPT_STATUSES,
  cancelReceiptFx,
  formOpened,
  isReceiptStatus,
  moreRequested,
  postReceiptFx,
  receiptSelected,
  reloadRequested,
  searchChanged,
  statusChanged,
  type Receipt,
  type ReceiptRow,
  type ReceiptStatus,
} from "../model/index.ts";

import { ReceiptSheet } from "./ReceiptSheet.tsx";

const ALL = "all";
const TONE: Readonly<Record<string, Tone>> = {
  draft: "awaiting-approval",
  posted: "success",
  cancelled: "neutral",
};

export function ReceiptStatusChip({ status }: { status: string }) {
  const { t } = useTranslation("warehouse");
  return (
    <StatusChip tone={TONE[status] ?? "neutral"}>
      {t(`receipts.status.${status as ReceiptStatus}`)}
    </StatusChip>
  );
}

export interface ReceiptRights {
  receive: boolean;
  post: boolean;
  /** `purchases.return` — «Qaytarish» from a posted receipt. */
  ret: boolean;
}

export function ReceiptsTab({
  rights,
  online,
  warehouse,
  onCreateReturn,
}: {
  rights: ReceiptRights;
  online: boolean;
  warehouse: Warehouse | null;
  onCreateReturn: (receipt: Receipt) => void;
}) {
  const { t } = useTranslation("warehouse");
  const [rows, status, error, cursor, moreLoading, filters] = useUnit([
    $receipts,
    $status,
    $error,
    $cursor,
    $moreLoading,
    $filters,
  ]);
  const [onSearch, onStatus, more, reload, select, open] = useUnit([
    searchChanged,
    statusChanged,
    moreRequested,
    reloadRequested,
    receiptSelected,
    formOpened,
  ]);

  const columns: DataTableColumn<ReceiptRow>[] = [
    {
      id: "doc",
      header: t("receipts.columns.doc"),
      width: "170px",
      cell: (r) => (
        <span className="flex flex-col">
          <span className="font-semibold">{r.number ?? t("receipts.draftNumber")}</span>
          <span className="text-[12px] text-muted-foreground">{formatDate(r.doc_date)}</span>
        </span>
      ),
    },
    {
      id: "supplier",
      header: t("receipts.columns.supplier"),
      cell: (r) => (
        <span className="flex flex-col">
          <span className="font-semibold">{r.supplier.name ?? "—"}</span>
          <span className="text-[12px] text-muted-foreground">
            {r.po_id ? t("receipts.fromOrder") : t("receipts.manual")}
            {r.kind === "gratuitous" ? ` · ${t("receipts.kind.gratuitous")}` : ""}
          </span>
        </span>
      ),
    },
    {
      id: "positions",
      header: t("receipts.columns.positions"),
      numeric: true,
      width: "80px",
      cell: (r) => r.line_count,
    },
    {
      id: "total",
      header: t("receipts.columns.total"),
      numeric: true,
      width: "150px",
      cell: (r) => formatMoney(r.total, { withCurrency: false }),
    },
    {
      id: "status",
      header: t("receipts.columns.status"),
      width: "140px",
      cell: (r) => <ReceiptStatusChip status={r.status} />,
    },
  ];

  return (
    <section className="flex flex-col gap-3" aria-label={t("purchases.tabs.receipts")}>
      <div className="flex flex-wrap items-end gap-3">
        <SearchInput
          className="w-72"
          value={filters.search}
          onSearch={onSearch}
          aria-label={t("receipts.search")}
          placeholder={t("receipts.searchPlaceholder")}
        />
        <FormField label={t("receipts.filter")} className="w-48">
          <SimpleSelect
            options={[
              { value: ALL, label: t("receipts.allStatuses") },
              ...RECEIPT_STATUSES.map((s) => ({ value: s, label: t(`receipts.status.${s}`) })),
            ]}
            value={filters.status ?? ALL}
            onValueChange={(v) => onStatus(isReceiptStatus(v) ? v : null)}
          />
        </FormField>
        <div className="grow" />
        {rights.receive ? (
          <Button disabled={!online || !warehouse} onClick={() => open({ mode: "new" })}>
            <Icon as={Plus} size="sm" />
            {t("receipts.create")}
          </Button>
        ) : null}
      </div>
      <DataTable
        label={t("receipts.tableLabel")}
        columns={columns}
        data={rows}
        getRowId={(r) => r.id}
        status={status}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={reload}
        onRowClick={(r) => select(r.id)}
        minWidth={820}
        empty={
          <EmptyState
            icon={PackagePlus}
            title={t("receipts.empty.title")}
            description={t("receipts.empty.description")}
          />
        }
        pagination={{ kind: "cursor", hasMore: cursor !== null, loadingMore: moreLoading, onLoadMore: more }}
      />
      <ReceiptDetail rights={rights} online={online} onCreateReturn={onCreateReturn} />
      <ReceiptSheet warehouse={warehouse} online={online} />
    </section>
  );
}

function ReceiptDetail({
  rights,
  online,
  onCreateReturn,
}: {
  rights: ReceiptRights;
  online: boolean;
  onCreateReturn: (r: Receipt) => void;
}) {
  const { t } = useTranslation("warehouse");
  const formatQty = useQtyFormat();
  const [selectedId, receipt, detailError, acting, actionError, select, post, cancel, open] = useUnit([
    $selectedId,
    $detail,
    $detailError,
    $acting,
    $actionError,
    receiptSelected,
    postReceiptFx,
    cancelReceiptFx,
    formOpened,
  ]);
  const [confirmPost, setConfirmPost] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  return (
    <Sheet open={selectedId !== null} onOpenChange={(next) => (next ? undefined : select(null))}>
      <SheetContent wide>
        {!receipt ? (
          <>
            <SheetHeader>
              <SheetTitle>{t("receipts.detailTitle")}</SheetTitle>
            </SheetHeader>
            {detailError ? (
              <SheetBody>
                <ErrorState
                  message={errorText(detailError)}
                  onRetry={() => (selectedId ? select(selectedId) : undefined)}
                />
              </SheetBody>
            ) : (
              <SheetBody aria-busy="true">
                <Skeleton className="h-40 w-full" />
              </SheetBody>
            )}
          </>
        ) : (
          <>
            <SheetHeader>
              <SheetTitle>{receipt.number ?? t("receipts.draftNumber")}</SheetTitle>
              <SheetDescription>
                {[
                  receipt.supplier.name,
                  receipt.supplier.stir ? t("suppliers.stirValue", { stir: receipt.supplier.stir }) : null,
                  formatDate(receipt.doc_date),
                  receipt.created_by_name ? t("orders.createdBy", { name: receipt.created_by_name }) : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </SheetDescription>
              <div className="flex flex-wrap gap-2 pt-1">
                <ReceiptStatusChip status={receipt.status} />
                {receipt.paid_immediately ? (
                  <StatusChip tone="info">{t("receipts.paidChip")}</StatusChip>
                ) : null}
                {receipt.kind === "gratuitous" ? (
                  <StatusChip tone="neutral">{t("receipts.kind.gratuitous")}</StatusChip>
                ) : null}
                {receipt.ettn_status === "none" ? (
                  <StatusChip tone="neutral">{t("receipts.noEttn")}</StatusChip>
                ) : null}
              </div>
            </SheetHeader>
            <SheetBody>
              {actionError ? (
                <Banner tone="destructive" icon={TriangleAlert} live="assertive">
                  {errorText(actionError)}
                </Banner>
              ) : null}
              {receipt.status === "draft" ? (
                <p className="text-small text-foreground-secondary">{t("receipts.postHint")}</p>
              ) : null}
              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full min-w-[640px] text-[13px]" aria-label={t("receipts.linesLabel")}>
                  <thead className="bg-muted text-caption text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left">{t("receipts.lines.product")}</th>
                      <th className="px-3 py-2 text-right">{t("receipts.lines.qty")}</th>
                      <th className="px-3 py-2 text-right">{t("receipts.lines.cost")}</th>
                      <th className="px-3 py-2 text-right">{t("receipts.lines.vat")}</th>
                      <th className="px-3 py-2 text-right">{t("receipts.lines.total")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {receipt.lines.map((l) => (
                      <tr key={l.id} className="border-t border-divider align-top">
                        <td className="px-3 py-2">
                          <span className="font-semibold">{l.product_name ?? "—"}</span>
                          <span className="block text-[12px] text-muted-foreground">
                            {[
                              l.expiry_date
                                ? t("receipts.expiryValue", { date: formatDate(l.expiry_date) })
                                : null,
                              l.discrepancy_reason ? t(`receipts.reasons.${l.discrepancy_reason}`) : null,
                              l.is_marked
                                ? t("receipts.codesValue", { count: l.marking_codes.length })
                                : null,
                              l.returned_qty !== "0.000"
                                ? t("receipts.returnedValue", { qty: formatQty(l.returned_qty, l.unit_code) })
                                : null,
                            ]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">{formatQty(l.qty, l.unit_code)}</td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {formatMoney(l.cost, { withCurrency: false })}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {formatMoney(l.vat_amount, { precision: 2, withCurrency: false })}
                        </td>
                        <td className="px-3 py-2 text-right font-bold tabular-nums">
                          {formatMoney(l.total_amount, { precision: 2, withCurrency: false })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 self-end text-[13px]">
                <dt className="text-muted-foreground">{t("receipts.net")}</dt>
                <dd className="text-right tabular-nums">
                  {formatMoney(receipt.net_total, { precision: 2 })}
                </dd>
                <dt className="text-muted-foreground">{t("receipts.vatTotal")}</dt>
                <dd className="text-right tabular-nums">
                  {formatMoney(receipt.vat_total, { precision: 2 })}
                </dd>
                <dt className="font-bold">{t("receipts.total")}</dt>
                <dd className="text-right font-extrabold tabular-nums">
                  {formatMoney(receipt.total, { precision: 2 })}
                </dd>
              </dl>
              {receipt.posted_at ? (
                <p className="text-[12px] text-muted-foreground">
                  {t("receipts.postedAt", { at: formatDateTime(receipt.posted_at) })}
                </p>
              ) : null}
              {receipt.cancel_reason ? (
                <p className="text-small text-foreground-secondary">
                  {t("cancel.reason")}: {receipt.cancel_reason}
                </p>
              ) : null}
            </SheetBody>
            <SheetFooter>
              {rights.post && receipt.status !== "cancelled" ? (
                <Button
                  variant="destructive-outline"
                  disabled={!online || acting}
                  onClick={() => setCancelling(true)}
                >
                  <Icon as={X} size="sm" />
                  {t("actions.cancelDoc")}
                </Button>
              ) : null}
              {rights.ret && receipt.status === "posted" && receipt.kind === "purchase" ? (
                <Button variant="secondary" disabled={!online} onClick={() => onCreateReturn(receipt)}>
                  <Icon as={Undo2} size="sm" />
                  {t("receipts.createReturn")}
                </Button>
              ) : null}
              {rights.receive && receipt.status === "draft" ? (
                <Button
                  variant="secondary"
                  disabled={!online || acting}
                  onClick={() => open({ mode: "edit" })}
                >
                  <Icon as={Pencil} size="sm" />
                  {t("actions.edit")}
                </Button>
              ) : null}
              {rights.post && receipt.status === "draft" ? (
                <Button disabled={!online || acting} onClick={() => setConfirmPost(true)}>
                  <Icon as={Check} size="sm" />
                  {t("receipts.post")}
                </Button>
              ) : null}
            </SheetFooter>
            <ConfirmDialog
              open={confirmPost}
              onOpenChange={setConfirmPost}
              title={t("receipts.postConfirm.title")}
              description={t("receipts.postConfirm.description", { total: formatMoney(receipt.total) })}
              confirmLabel={t("receipts.post")}
              onConfirm={() => {
                setConfirmPost(false);
                post(receipt.id)
                  .then((r) =>
                    toast.success(
                      t("receipts.toast.posted", { number: r.number ?? "", count: r.lots_created.length }),
                    ),
                  )
                  .catch(() => undefined);
              }}
            />
            <ReasonDialog
              open={cancelling}
              onOpenChange={setCancelling}
              title={t("receipts.cancelTitle")}
              description={receipt.status === "posted" ? t("receipts.cancelPosted") : undefined}
              onConfirm={async (reason) => {
                await cancel({ id: receipt.id, reason });
                toast.success(t("receipts.toast.cancelled"));
              }}
            />
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

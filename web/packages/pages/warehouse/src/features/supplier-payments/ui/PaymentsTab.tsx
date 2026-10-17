/**
 * BO-04 «Yetkazib beruvchiga to'lov» tab (07 BO-04; 19 §11 GET/POST /supplier-payments, /{id}/cancel):
 * filters (status, method), the list (date, number, supplier, method, amount, advance, status), «To'lov
 * qayd etish» (`purchases.pay`), the detail sheet (allocations, released VAT credit) with «Bekor qilish»
 * (reason; storno of ledger, debt, cash and VAT — a cash payment only while its shift is open).
 */
import { useUnit } from "effector-react";
import { Ban, CheckCircle2, HandCoins, Plus } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatDateTime, formatMoney } from "@shared/lib/format";
import { compareMoney, money } from "@shared/lib/money";
import {
  Banner,
  Button,
  DataTable,
  EmptyState,
  FormField,
  Icon,
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
  type DataTableColumn,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";
import { ReasonDialog } from "#/shared/ui/ReasonDialog.tsx";

import {
  $lastCreated,
  $paymentDetail,
  $paymentFilters,
  $payments,
  $paymentsCursor,
  $paymentsError,
  $paymentsMoreLoading,
  $paymentsStatus,
  $selectedPaymentId,
  PAYMENT_METHODS,
  PAYMENT_STATUSES,
  cancelPaymentFx,
  isPaymentMethod,
  isPaymentStatus,
  paymentFiltersChanged,
  paymentFormOpened,
  paymentSelected,
  paymentsMoreRequested,
  paymentsReloadRequested,
  type Payment,
} from "../model/index.ts";
import { PaymentSheet } from "./PaymentSheet.tsx";

const ALL = "all";
const money2 = (v: string) => formatMoney(v, { precision: 2 });

export function PaymentsTab({ canPay, online }: { canPay: boolean; online: boolean }) {
  const { t } = useTranslation("warehouse");
  const [rows, status, error, cursor, moreLoading, filters, lastCreated] = useUnit([
    $payments,
    $paymentsStatus,
    $paymentsError,
    $paymentsCursor,
    $paymentsMoreLoading,
    $paymentFilters,
    $lastCreated,
  ]);
  const [change, more, reload, select, openForm] = useUnit([
    paymentFiltersChanged,
    paymentsMoreRequested,
    paymentsReloadRequested,
    paymentSelected,
    paymentFormOpened,
  ]);

  const columns: DataTableColumn<Payment>[] = [
    {
      id: "date",
      header: t("supplierPayments.columns.date"),
      width: "100px",
      cell: (p) => formatDate(p.doc_date),
    },
    {
      id: "number",
      header: t("supplierPayments.columns.number"),
      width: "170px",
      cell: (p) => <span className="font-semibold tabular-nums">{p.number ?? "—"}</span>,
    },
    { id: "supplier", header: t("supplierPayments.columns.supplier"), cell: (p) => p.supplier.name ?? "—" },
    {
      id: "method",
      header: t("supplierPayments.columns.method"),
      width: "120px",
      cell: (p) => t(`supplierPayments.methods.${p.method}`),
    },
    {
      id: "amount",
      header: t("supplierPayments.columns.amount"),
      numeric: true,
      width: "140px",
      cell: (p) => money2(p.amount),
    },
    {
      id: "advance",
      header: t("supplierPayments.columns.advance"),
      numeric: true,
      width: "120px",
      cell: (p) => (compareMoney(money(p.advance_amount), money("0")) > 0 ? money2(p.advance_amount) : "—"),
    },
    {
      id: "status",
      header: t("supplierPayments.columns.status"),
      width: "140px",
      cell: (p) => (
        <StatusChip tone={p.status === "posted" ? "success" : "destructive"} dot>
          {t(`supplierPayments.status.${p.status}`)}
        </StatusChip>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <p className="min-w-0 flex-1 text-small text-foreground-secondary">
          {t("supplierPayments.subtitle")}
        </p>
        <FormField label={t("supplierPayments.filters.status")} className="w-44">
          <SimpleSelect
            options={[
              { value: ALL, label: t("supplierPayments.filters.all") },
              ...PAYMENT_STATUSES.map((s) => ({ value: s, label: t(`supplierPayments.status.${s}`) })),
            ]}
            value={filters.status ?? ALL}
            onValueChange={(v) => change({ status: isPaymentStatus(v) ? v : null })}
          />
        </FormField>
        <FormField label={t("supplierPayments.filters.method")} className="w-40">
          <SimpleSelect
            options={[
              { value: ALL, label: t("supplierPayments.filters.all") },
              ...PAYMENT_METHODS.map((m) => ({ value: m, label: t(`supplierPayments.methods.${m}`) })),
            ]}
            value={filters.method ?? ALL}
            onValueChange={(v) => change({ method: isPaymentMethod(v) ? v : null })}
          />
        </FormField>
        {canPay ? (
          <Button disabled={!online} onClick={() => openForm({ supplierId: null })} data-testid="payment-new">
            <Icon as={Plus} size="sm" />
            {t("supplierPayments.create")}
          </Button>
        ) : null}
      </div>
      {lastCreated ? (
        <Banner tone={lastCreated.warnings.length > 0 ? "warning" : "success"} icon={CheckCircle2}>
          <span data-testid="payment-created">
            {t("supplierPayments.created", {
              number: lastCreated.number ?? "",
              amount: money2(lastCreated.amount),
            })}
            {lastCreated.warnings.some((w) => w.code === "SUPPLIER_OVERPAY_ADVANCE")
              ? ` ${t("supplierPayments.advanceWritten", { amount: money2(lastCreated.advance_amount) })}`
              : ""}
          </span>
        </Banner>
      ) : null}
      <DataTable
        label={t("supplierPayments.title")}
        columns={columns}
        data={rows}
        getRowId={(p) => p.id}
        status={status}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={reload}
        onRowClick={(p) => select(p.id)}
        minWidth={900}
        skeletonRows={4}
        empty={
          <EmptyState
            icon={HandCoins}
            title={t("supplierPayments.empty")}
            description={t("supplierPayments.emptyHint")}
          />
        }
        pagination={{ kind: "cursor", hasMore: cursor !== null, loadingMore: moreLoading, onLoadMore: more }}
      />
      <PaymentSheet />
      <PaymentDetail canPay={canPay && online} />
    </div>
  );
}

function PaymentDetail({ canPay }: { canPay: boolean }) {
  const { t } = useTranslation("warehouse");
  const [selectedId, payment, select, cancel, pending] = useUnit([
    $selectedPaymentId,
    $paymentDetail,
    paymentSelected,
    cancelPaymentFx,
    cancelPaymentFx.pending,
  ]);
  const [cancelling, setCancelling] = useState(false);
  return (
    <Sheet open={selectedId !== null} onOpenChange={(next) => (next ? undefined : select(null))}>
      <SheetContent wide>
        <SheetHeader>
          <SheetTitle>{payment?.number ?? t("supplierPayments.detailTitle")}</SheetTitle>
          {payment ? (
            <SheetDescription>
              {[
                payment.supplier.name,
                formatDate(payment.doc_date),
                t(`supplierPayments.methods.${payment.method}`),
              ]
                .filter(Boolean)
                .join(" · ")}
            </SheetDescription>
          ) : null}
        </SheetHeader>
        {!payment ? (
          <SheetBody aria-busy="true">
            <Skeleton className="h-40 w-full" />
          </SheetBody>
        ) : (
          <>
            <SheetBody className="flex flex-col gap-3">
              <dl
                className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-[13px]"
                data-testid="payment-detail"
              >
                <dt className="text-foreground-secondary">{t("supplierPayments.columns.amount")}</dt>
                <dd className="text-right font-bold tabular-nums">{money2(payment.amount)}</dd>
                <dt className="text-foreground-secondary">{t("supplierPayments.columns.advance")}</dt>
                <dd className="text-right tabular-nums">{money2(payment.advance_amount)}</dd>
                <dt className="text-foreground-secondary">{t("supplierPayments.columns.status")}</dt>
                <dd className="text-right">{t(`supplierPayments.status.${payment.status}`)}</dd>
                {payment.created_by_name ? (
                  <>
                    <dt className="text-foreground-secondary">{t("supplierPayments.createdBy")}</dt>
                    <dd className="text-right">{payment.created_by_name}</dd>
                  </>
                ) : null}
                {payment.cancelled_at ? (
                  <>
                    <dt className="text-foreground-secondary">{t("supplierPayments.cancelledAt")}</dt>
                    <dd className="text-right">{formatDateTime(payment.cancelled_at)}</dd>
                  </>
                ) : null}
              </dl>
              {payment.cancel_reason ? (
                <p className="text-[12px] text-foreground-secondary">
                  {t("supplierPayments.cancelReason", { reason: payment.cancel_reason })}
                </p>
              ) : null}
              <h3 className="text-[14px] font-bold">{t("supplierPayments.form.allocation")}</h3>
              {payment.allocations.length === 0 ? (
                <p className="text-small text-foreground-secondary">{t("supplierPayments.noAllocations")}</p>
              ) : (
                <ul className="flex flex-col gap-1.5 text-[13px]">
                  {payment.allocations.map((a) => (
                    <li
                      key={a.target_doc_id}
                      className="flex justify-between gap-2 border-t border-border pt-1.5"
                    >
                      <span>
                        {t(`supplierPayments.docTypes.${a.target_doc_type}`)} {a.target_number ?? ""}
                        {a.target_doc_date ? ` · ${formatDate(a.target_doc_date)}` : ""}
                        {compareMoney(money(a.vat_credit_unlocked), money("0")) > 0 ? (
                          <span className="block text-[11px] text-foreground-secondary">
                            {t("supplierPayments.vatUnlocked", { amount: money2(a.vat_credit_unlocked) })}
                          </span>
                        ) : null}
                      </span>
                      <span className="font-bold tabular-nums">{money2(a.amount)}</span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-[12px] text-foreground-secondary">
                {t("supplierPayments.form.posting", { kt: payment.method === "cash" ? "5010" : "5110" })}
              </p>
            </SheetBody>
            {canPay && payment.status === "posted" ? (
              <SheetFooter>
                <Button
                  variant="destructive"
                  disabled={pending}
                  onClick={() => setCancelling(true)}
                  data-testid="payment-cancel"
                >
                  <Icon as={Ban} size="sm" />
                  {t("supplierPayments.cancel")}
                </Button>
              </SheetFooter>
            ) : null}
          </>
        )}
        {payment ? (
          <ReasonDialog
            open={cancelling}
            onOpenChange={setCancelling}
            title={t("supplierPayments.cancelTitle")}
            description={t("supplierPayments.cancelDescription")}
            onConfirm={async (reason) => {
              await cancel({ id: payment.id, reason });
              setCancelling(false);
            }}
          />
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

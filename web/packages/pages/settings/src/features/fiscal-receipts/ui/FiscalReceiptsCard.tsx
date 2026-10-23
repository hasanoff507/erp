/**
 * BO-14 «Fiskal» tab: registers' fiscal module state (`fm_state`, unacknowledged receipts) and the
 * «OFD: N ta chek yuborilmagan» list with «Qayta urinish» (07 BO-14, 18 §14). Fiscal sign / QR are not
 * repeated here (POS-04 reprint); a failed receipt's provider error is never shown raw (08 §11).
 */
import { useUnit } from "effector-react";
import { ReceiptText, RotateCcw, TriangleAlert } from "lucide-react";
import { useEffect } from "react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatDateTime } from "@shared/lib/format";
import {
  Banner,
  Button,
  Card,
  DataTable,
  EmptyState,
  FormField,
  Icon,
  SimpleSelect,
  StatusChip,
  type DataTableColumn,
  type Tone,
} from "@shared/ui";

import {
  $fiscalFilter,
  $fiscalRequeued,
  $fiscalRetryError,
  $fiscalRetrying,
  $receipts,
  $receiptsCursor,
  $receiptsError,
  $receiptsMoreLoading,
  $receiptsStatus,
  $registerNames,
  $registers,
  RECEIPT_FILTERS,
  fiscalFilterChanged,
  fiscalMoreRequested,
  fiscalOpened,
  fiscalReloadRequested,
  fiscalRetryDismissed,
  fiscalRetryRequested,
  isReceiptFilter,
  isRetryable,
  registersByAttention,
  type FiscalReceipt,
} from "../model/index.ts";

const ALL = "all";

const STATUS_TONE: Readonly<Record<string, Tone>> = {
  pending: "info",
  sent: "primary",
  fiscalized: "success",
  failed: "destructive",
};
const FM_TONE: Readonly<Record<string, Tone>> = {
  ok: "success",
  locked: "destructive",
  ack_overdue: "warning",
  memory_full: "destructive",
  unknown: "neutral",
};

export interface FiscalReceiptsCardProps {
  /** `integrations.retry` — «Qayta urinish» is shown only then. */
  canRetry: boolean;
  online: boolean;
}

export function FiscalReceiptsCard({ canRetry, online }: FiscalReceiptsCardProps) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const [receipts, status, error, cursor, moreLoading, filter, retrying, requeued, retryError] = useUnit([
    $receipts,
    $receiptsStatus,
    $receiptsError,
    $receiptsCursor,
    $receiptsMoreLoading,
    $fiscalFilter,
    $fiscalRetrying,
    $fiscalRequeued,
    $fiscalRetryError,
  ]);
  const [registers, registerNames] = useUnit([$registers, $registerNames]);
  const [opened, onFilter, more, reload, retry, dismiss] = useUnit([
    fiscalOpened,
    fiscalFilterChanged,
    fiscalMoreRequested,
    fiscalReloadRequested,
    fiscalRetryRequested,
    fiscalRetryDismissed,
  ]);

  useEffect(() => {
    opened();
  }, [opened]);

  const registerName = (r: FiscalReceipt) =>
    (r.cash_register_id ? registerNames.get(r.cash_register_id) : undefined) ?? "—";
  const receiptLabel = (r: FiscalReceipt) =>
    `${t(`fiscal.kind.${r.kind}`)}${r.receipt_seq !== null ? ` #${r.receipt_seq}` : ""}`;
  const unacked = registers.filter((r) => r.last_unacked_receipt_at !== null).length;

  const columns: DataTableColumn<FiscalReceipt>[] = [
    {
      id: "created",
      header: t("fiscal.columns.created"),
      width: "140px",
      cell: (r) => <span className="tabular-nums">{formatDateTime(r.created_at)}</span>,
    },
    { id: "receipt", header: t("fiscal.columns.receipt"), cell: receiptLabel },
    { id: "register", header: t("fiscal.columns.register"), width: "150px", cell: registerName },
    {
      id: "status",
      header: t("fiscal.columns.status"),
      width: "150px",
      cell: (r) =>
        requeued.includes(r.id) ? (
          <StatusChip tone="info">{t("fiscal.requeued")}</StatusChip>
        ) : (
          <StatusChip tone={STATUS_TONE[r.status] ?? "neutral"}>{t(`fiscal.status.${r.status}`)}</StatusChip>
        ),
    },
    {
      id: "attempts",
      header: t("fiscal.columns.attempts"),
      numeric: true,
      width: "80px",
      cell: (r) => r.attempts,
    },
    {
      id: "offline",
      header: t("fiscal.columns.offlineSince"),
      width: "140px",
      cell: (r) =>
        r.ofd_acked_at ? (
          <span className="text-[12px] text-muted-foreground">{t("fiscal.acked")}</span>
        ) : r.offline_since ? (
          <span className="tabular-nums">{formatDateTime(r.offline_since)}</span>
        ) : (
          "—"
        ),
    },
    ...(canRetry
      ? [
          {
            id: "action",
            header: t("fiscal.columns.action"),
            hideHeader: true,
            width: "150px",
            cell: (r: FiscalReceipt) =>
              isRetryable(r) && !requeued.includes(r.id) ? (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!online || retrying.includes(r.id)}
                  aria-busy={retrying.includes(r.id) || undefined}
                  aria-label={t("fiscal.retryFor", { receipt: receiptLabel(r) })}
                  onClick={() => retry(r.id)}
                >
                  <Icon as={RotateCcw} size="sm" />
                  {t("fiscal.retry")}
                </Button>
              ) : null,
          } satisfies DataTableColumn<FiscalReceipt>,
        ]
      : []),
  ];

  return (
    <Card role="region" aria-labelledby="fiscal-receipts-title" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <h3 id="fiscal-receipts-title" className="text-[15px] font-bold">
            {t("fiscal.title")}
          </h3>
          <p className="text-small text-foreground-secondary">{t("fiscal.subtitle")}</p>
        </div>
        <FormField label={t("fiscal.filter")} className="w-56">
          <SimpleSelect
            options={[
              { value: ALL, label: t("fiscal.allStatuses") },
              ...RECEIPT_FILTERS.map((s) => ({ value: s, label: t(`fiscal.status.${s}`) })),
            ]}
            value={filter ?? ALL}
            onValueChange={(v) => onFilter(isReceiptFilter(v) ? v : null)}
          />
        </FormField>
      </div>

      {registers.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          <h4 className="text-[13px] font-bold">
            {t("fiscal.registersTitle", { count: registers.length, unacked })}
          </h4>
          <ul
            aria-label={t("fiscal.registersTitle", { count: registers.length, unacked })}
            className="flex flex-wrap gap-2"
          >
            {registersByAttention(registers).map((r) => (
              <li
                key={r.id}
                className="flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-[13px]"
              >
                <span className="font-semibold">{r.name}</span>
                <StatusChip tone={FM_TONE[r.fm_state] ?? "neutral"} dot>
                  {t(`fiscal.fmState.${r.fm_state}`)}
                </StatusChip>
                {r.last_unacked_receipt_at ? (
                  <span className="text-[12px] text-warning-strong">
                    {t("fiscal.unackedSince", { at: formatDateTime(r.last_unacked_receipt_at) })}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {retryError ? (
        <Banner
          tone="destructive"
          icon={TriangleAlert}
          live="assertive"
          action={
            <Button size="sm" variant="secondary" onClick={() => dismiss()}>
              {tc("actions.close")}
            </Button>
          }
        >
          {serverErrorText(retryError)}
        </Banner>
      ) : null}
      <DataTable
        label={t("fiscal.tableLabel")}
        columns={columns}
        data={receipts}
        getRowId={(r) => r.id}
        status={status}
        errorMessage={error ? serverErrorText(error) : undefined}
        onRetry={reload}
        minWidth={900}
        skeletonRows={3}
        empty={
          <EmptyState
            icon={ReceiptText}
            title={t(filter === "failed" ? "fiscal.empty.failed" : "fiscal.empty.other")}
          />
        }
        pagination={{ kind: "cursor", hasMore: cursor !== null, loadingMore: moreLoading, onLoadMore: more }}
      />
    </Card>
  );
}

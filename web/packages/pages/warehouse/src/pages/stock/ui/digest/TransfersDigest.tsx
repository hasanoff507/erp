/**
 * «Ko'chirishlar va e-TTN» block under «Qoldiq» (07 BO-03, mockup Bo03Ombor): the current branch's
 * transfers of the last 7 days (at most 5) — hujjat, yo'nalish + tashish usuli, yuborilgan,
 * pozitsiyalar, summa, holat, e-TTN. Row actions are «Qabul qilish» and «Farqni ko'rish» only; e-TTN
 * signing and manual registration are Bosqich 5. «Barcha ko'chirishlar» opens the «Ko'chirishlar» tab.
 */
import { useUnit } from "effector-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatDateTime, formatMoney } from "@shared/lib/format";
import { Button, Card, ErrorState, Skeleton } from "@shared/ui";

import { useBranchName, useQtyFormat } from "#/entities/refs/index.ts";
import {
  EttnChip,
  ReceiveDialog,
  TransferDetail,
  TransferStatusChip,
  actionsOf,
  transferShown,
  transferValue,
  useTransferTitle,
  type Transfer,
  type TransferRights,
} from "#/features/transfers/index.ts";
import { errorText } from "#/shared/lib/errors.ts";

import {
  $digest,
  $digestError,
  $transit,
  DIGEST_DAYS,
  summaryRefreshRequested,
  tabChanged,
} from "../../model/index.ts";

export function TransfersDigest({ rights, online }: { rights: TransferRights; online: boolean }) {
  const { t } = useTranslation("warehouse");
  const [rows, error, transit, openTab, retry, show] = useUnit([
    $digest,
    $digestError,
    $transit,
    tabChanged,
    summaryRefreshRequested,
    transferShown,
  ]);
  const branchName = useBranchName();
  const formatQty = useQtyFormat();
  const title = useTransferTitle();
  const [receiving, setReceiving] = useState<Transfer | null>(null);
  // Only receiving is offered here (no post / send / cancel — those live in the «Ko'chirishlar» tab).
  const receiveOnly: TransferRights = { ...rights, create: false };

  return (
    <Card className="flex flex-col gap-0 p-0" role="region" aria-label={t("digest.title")}>
      <div className="flex flex-wrap items-baseline gap-3 px-5 pb-3.5 pt-[18px]">
        <h2 className="text-[17px] font-extrabold">{t("digest.title")}</h2>
        <span className="text-[13px] text-muted-foreground">
          {t("digest.subtitle", {
            days: DIGEST_DAYS,
            inTransit: transit?.inTransit ?? 0,
            overdue: transit?.overdue ?? 0,
          })}
        </span>
        <div className="grow" />
        <Button variant="link" size="sm" className="px-0" onClick={() => openTab("transfers")}>
          {t("digest.all")}
        </Button>
      </div>
      {error ? (
        <ErrorState className="py-5" message={errorText(error)} onRetry={() => retry()} />
      ) : rows === null ? (
        <div className="flex flex-col gap-2 px-5 pb-5" aria-busy="true">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : rows.length === 0 ? (
        <p className="border-t border-divider px-5 py-6 text-center text-small text-muted-foreground">
          {t("digest.empty", { days: DIGEST_DAYS })}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] text-[13px]" aria-label={t("digest.tableLabel")}>
            <thead className="border-t border-border bg-muted text-caption text-muted-foreground">
              <tr>
                <th className="px-5 py-2.5 text-left">{t("transfers.columns.doc")}</th>
                <th className="px-3 py-2.5 text-left">{t("transfers.columns.route")}</th>
                <th className="px-3 py-2.5 text-left">{t("transfers.columns.sent")}</th>
                <th className="px-3 py-2.5 text-right">{t("transfers.columns.positions")}</th>
                <th className="px-3 py-2.5 text-right">{t("transfers.columns.sum")}</th>
                <th className="px-3 py-2.5 text-left">{t("transfers.columns.status")}</th>
                <th className="px-3 py-2.5 text-left">{t("transfers.columns.ettn")}</th>
                <th className="px-5 py-2.5 text-left">{t("digest.action")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((tr) => {
                const value = transferValue(tr);
                const canReceive = actionsOf(tr, receiveOnly).includes("receive");
                return (
                  <tr key={tr.id} className="border-t border-divider">
                    <td className="px-5 py-2.5">
                      <span className="flex flex-col">
                        <span className="font-bold tabular-nums">{title(tr)}</span>
                        <span className="text-[12px] text-muted-foreground">{formatDate(tr.doc_date)}</span>
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="flex flex-col">
                        <span className="font-semibold">
                          {branchName(tr.from_branch_id)} → {branchName(tr.to_branch_id)}
                        </span>
                        <span className="text-[12px] text-muted-foreground">
                          {t(`transfers.mode.${tr.transport_mode}`)}
                          {tr.vehicle_plate ? ` · ${tr.vehicle_plate}` : ""}
                        </span>
                      </span>
                    </td>
                    <td className="px-3 py-2.5 tabular-nums">
                      {tr.sent_at ? formatDateTime(tr.sent_at) : "—"}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {formatQty(String(tr.lines.length))}
                    </td>
                    <td className="px-3 py-2.5 text-right font-bold tabular-nums">
                      {value ? formatMoney(value, { withCurrency: false }) : "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      <TransferStatusChip transfer={tr} />
                    </td>
                    <td className="px-3 py-2.5">
                      <EttnChip transfer={tr} />
                    </td>
                    <td className="px-5 py-2.5">
                      {canReceive ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={!online}
                          aria-label={t("digest.receiveFor", { number: title(tr) })}
                          onClick={() => setReceiving(tr)}
                        >
                          {t("transfers.actions.receive")}
                        </Button>
                      ) : tr.status === "discrepancy" ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          aria-label={t("digest.viewDiffFor", { number: title(tr) })}
                          onClick={() => show(tr)}
                        >
                          {t("digest.viewDiff")}
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <ReceiveDialog transfer={receiving} onClose={() => setReceiving(null)} />
      <TransferDetail
        rights={receiveOnly}
        online={online}
        onAction={(action, tr) => (action === "receive" ? setReceiving(tr) : undefined)}
      />
    </Card>
  );
}

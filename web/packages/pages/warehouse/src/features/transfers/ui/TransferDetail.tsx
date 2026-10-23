/**
 * Transfer detail (07 POS-09 right column, shown in BO-03): number + status, route, transport block,
 * e-TTN state («E-TTN kutilmoqda» + «Yangilash» while a posted vehicle transfer waits for the
 * registration), lines (yuborilgan / qabul qilingan / farq) and the allowed actions.
 */
import { useUnit } from "effector-react";
import { Check, Hourglass, PackageCheck, RefreshCw, Send, TriangleAlert, X } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatDateTime, formatMoney } from "@shared/lib/format";
import {
  Banner,
  Button,
  Icon,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@shared/ui";

import { useBranchName, useQtyFormat } from "#/entities/refs/index.ts";
import { subtractQty, isZero } from "#/shared/lib/decimal.ts";
import { errorText } from "#/shared/lib/errors.ts";

import {
  $acting,
  $actionError,
  $selected,
  actionsOf,
  getTransferFx,
  isWaitingForEttn,
  transferRefreshRequested,
  transferSelected,
  transferValue,
  type Transfer,
  type TransferAction,
  type TransferRights,
} from "../model/index.ts";

import { EttnChip, TransferStatusChip } from "./chips.tsx";

const ACTION_ICON = { post: Check, send: Send, receive: PackageCheck, cancel: X } as const;

export function TransferDetail({
  rights,
  online,
  onAction,
}: {
  rights: TransferRights;
  online: boolean;
  onAction: (action: TransferAction, transfer: Transfer) => void;
}) {
  const { t } = useTranslation("warehouse");
  const [transfer, acting, refreshing, actionError, select, refresh] = useUnit([
    $selected,
    $acting,
    getTransferFx.pending,
    $actionError,
    transferSelected,
    transferRefreshRequested,
  ]);
  const branchName = useBranchName();
  const formatQty = useQtyFormat();

  return (
    <Sheet open={transfer !== null} onOpenChange={(open) => (open ? undefined : select(null))}>
      <SheetContent wide>
        {transfer ? (
          <>
            <SheetHeader>
              <SheetTitle>
                {transfer.number ?? t("transfers.draftNumber", { date: formatDate(transfer.doc_date) })}
              </SheetTitle>
              <SheetDescription>
                {branchName(transfer.from_branch_id)} → {branchName(transfer.to_branch_id)} ·{" "}
                {formatDate(transfer.doc_date)}
              </SheetDescription>
              <div className="flex flex-wrap gap-2 pt-1">
                <TransferStatusChip transfer={transfer} />
                <EttnChip transfer={transfer} />
              </div>
            </SheetHeader>
            <SheetBody>
              {actionError ? (
                <Banner tone="destructive" icon={TriangleAlert} live="assertive">
                  {errorText(actionError)}
                </Banner>
              ) : null}
              {isWaitingForEttn(transfer) ? (
                <Banner
                  tone="awaiting-approval"
                  icon={Hourglass}
                  action={
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={refreshing || !online}
                      aria-busy={refreshing || undefined}
                      onClick={() => refresh(transfer.id)}
                    >
                      <Icon as={RefreshCw} size="sm" />
                      {t("transfers.refresh")}
                    </Button>
                  }
                >
                  {t("transfers.waitingEttn")}
                </Banner>
              ) : null}
              <dl className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] gap-x-4 gap-y-2 text-[13px]">
                <dt className="text-muted-foreground">{t("transfers.fields.transportMode")}</dt>
                <dd className="font-semibold">{t(`transfers.mode.${transfer.transport_mode}`)}</dd>
                {transfer.vehicle_plate ? (
                  <>
                    <dt className="text-muted-foreground">{t("transfers.fields.vehiclePlate")}</dt>
                    <dd className="font-semibold">{transfer.vehicle_plate}</dd>
                  </>
                ) : null}
                {transfer.driver_name ? (
                  <>
                    <dt className="text-muted-foreground">{t("transfers.fields.driverName")}</dt>
                    <dd className="font-semibold">{transfer.driver_name}</dd>
                  </>
                ) : null}
                {transfer.ettn?.operator_doc_id ? (
                  <>
                    <dt className="text-muted-foreground">{t("transfers.fields.ettnRef")}</dt>
                    <dd className="font-semibold tabular-nums">{transfer.ettn.operator_doc_id}</dd>
                  </>
                ) : null}
                {transfer.sent_at ? (
                  <>
                    <dt className="text-muted-foreground">{t("transfers.columns.sent")}</dt>
                    <dd className="font-semibold tabular-nums">{formatDateTime(transfer.sent_at)}</dd>
                  </>
                ) : null}
                {transfer.received_at ? (
                  <>
                    <dt className="text-muted-foreground">{t("transfers.fields.receivedAt")}</dt>
                    <dd className="font-semibold tabular-nums">{formatDateTime(transfer.received_at)}</dd>
                  </>
                ) : null}
                {transfer.comment ? (
                  <>
                    <dt className="text-muted-foreground">{t("transfers.fields.comment")}</dt>
                    <dd>{transfer.comment}</dd>
                  </>
                ) : null}
                {transfer.cancel_reason ? (
                  <>
                    <dt className="text-muted-foreground">{t("cancel.reason")}</dt>
                    <dd>{transfer.cancel_reason}</dd>
                  </>
                ) : null}
              </dl>
              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full min-w-[520px] text-[13px]" aria-label={t("transfers.linesLabel")}>
                  <thead className="bg-muted text-caption text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left">{t("transfers.lines.product")}</th>
                      <th className="px-3 py-2 text-right">{t("transfers.lines.sent")}</th>
                      <th className="px-3 py-2 text-right">{t("transfers.lines.received")}</th>
                      <th className="px-3 py-2 text-right">{t("transfers.lines.diff")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transfer.lines.map((l) => {
                      const diff = l.qty_received === null ? null : subtractQty(l.qty_received, l.qty_sent);
                      return (
                        <tr key={l.id} className="border-t border-divider">
                          <td className="px-3 py-2 font-semibold">{l.product_name}</td>
                          <td className="px-3 py-2 text-right tabular-nums">{formatQty(l.qty_sent)}</td>
                          <td className="px-3 py-2 text-right tabular-nums">
                            {l.qty_received === null ? "—" : formatQty(l.qty_received)}
                          </td>
                          <td
                            className={
                              diff !== null && !isZero(diff)
                                ? "px-3 py-2 text-right font-bold tabular-nums text-destructive-strong"
                                : "px-3 py-2 text-right tabular-nums"
                            }
                          >
                            {diff === null ? "—" : formatQty(diff)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {transferValue(transfer) ? (
                <p className="text-right text-[14px] font-bold">
                  {t("transfers.total")}:{" "}
                  <span className="tabular-nums">{formatMoney(transferValue(transfer) ?? "0")}</span>
                </p>
              ) : null}
            </SheetBody>
            {actionsOf(transfer, rights).length > 0 ? (
              <SheetFooter>
                {actionsOf(transfer, rights).map((action) => (
                  <Button
                    key={action}
                    variant={action === "cancel" ? "destructive-outline" : "default"}
                    disabled={!online || acting}
                    onClick={() => onAction(action, transfer)}
                  >
                    <Icon as={ACTION_ICON[action]} size="sm" />
                    {t(`transfers.actions.${action}`)}
                  </Button>
                ))}
              </SheetFooter>
            ) : null}
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

/**
 * Right panel of the selected e-invoice (07 BO-15): requisites, lines, QQSsiz / QQS / jami; incoming —
 * «Xavf darajasini belgilash» (Yashil / Qizil, izoh majburiy, «Kabinetda tekshirdim»), «Imzolab qabul qilish»,
 * «Rad etish», the previous attempt's error and the hint «Qabul qilingach — «Kirim yaratish»»; outgoing —
 * «E-IMZO imzo va yuborish», «Bekor qilish» (sabab majburiy) and «QQS qayta hisoblanmaydi» for a receipt-based
 * e-invoice (13 §2.22). Signing needs a valid E-IMZO key (21 §5) and the network.
 */
import { useUnit } from "effector-react";
import { CircleAlert, Info, PackagePlus, PenLine, Send, ShieldCheck, X } from "lucide-react";
import { useState } from "react";

import { formatDate, formatMoney } from "@shared/lib/format";
import { $isOnline } from "@shared/state/network";
import { useCan } from "@shared/state/permissions";
import {
  Banner,
  Button,
  Checkbox,
  FormField,
  Label,
  SegmentedControl,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  Skeleton,
  Textarea,
  Icon,
} from "@shared/ui";

import { useTx } from "#/shared/lib/i18n.ts";

import {
  $busy,
  $detail,
  $detailStatus,
  $key,
  $selectedId,
  cancelOutSubmitted,
  einvoiceSelected,
  netOf,
  payloadLines,
  receiptDialogOpened,
  rejectSubmitted,
  riskFlagSubmitted,
  signAcceptRequested,
  signSendRequested,
  type EInvoiceDetail,
} from "../../model/index.ts";
import { ReasonDialog } from "../dialogs/ReasonDialog.tsx";
import { ReceiptDialog } from "../dialogs/ReceiptDialog.tsx";
import { DocStatusChip, RiskChip } from "../shared/chips.tsx";

const m = (v: string | null) => (v === null ? "—" : formatMoney(v, { precision: 2, withCurrency: false }));

function RiskForm({ detail }: { detail: EInvoiceDetail }) {
  const { t } = useTx();
  const [busy, submit] = useUnit([$busy, riskFlagSubmitted]);
  const [flag, setFlag] = useState<"green" | "red">(detail.risk_flag === "red" ? "red" : "green");
  const [note, setNote] = useState("");
  const [checked, setChecked] = useState(false);
  const ready = note.trim().length > 0 && checked;
  return (
    <section
      className="flex flex-col gap-3 rounded-xl border border-border p-4"
      aria-label={t("risk.formTitle")}
    >
      <h3 className="text-[14px] font-bold">{t("risk.formTitle")}</h3>
      <SegmentedControl
        label={t("risk.formTitle")}
        options={[
          { value: "green", label: t("risk.green") },
          { value: "red", label: t("risk.red") },
        ]}
        value={flag}
        onChange={setFlag}
      />
      <FormField label={t("risk.note")} required>
        <Textarea value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} />
      </FormField>
      <div className="flex items-center gap-2">
        <Checkbox id="risk-checked" checked={checked} onCheckedChange={(v) => setChecked(v === true)} />
        <Label htmlFor="risk-checked">{t("risk.checkedInCabinet")}</Label>
      </div>
      <Button
        size="sm"
        variant="secondary"
        disabled={!ready || busy}
        data-testid="risk-save"
        onClick={() => {
          submit({ flag, note: note.trim() });
          setNote("");
          setChecked(false);
        }}
      >
        {t("risk.save")}
      </Button>
    </section>
  );
}

function Lines({ detail }: { detail: EInvoiceDetail }) {
  const { t } = useTx();
  const lines = payloadLines(detail.payload);
  return (
    <table className="w-full text-[13px]" aria-label={t("detail.lines")}>
      <thead>
        <tr className="text-left text-foreground-secondary">
          <th className="py-1 font-semibold">{t("detail.line")}</th>
          <th className="py-1 text-right font-semibold">{t("detail.qty")}</th>
          <th className="py-1 text-right font-semibold">{t("detail.net")}</th>
          <th className="py-1 text-right font-semibold">{t("detail.vat")}</th>
        </tr>
      </thead>
      <tbody>
        {lines.map((ln) => (
          <tr key={ln.line_no} className="border-t border-border">
            <td className="py-1.5">{ln.name}</td>
            <td className="py-1.5 text-right tabular-nums">{ln.qty}</td>
            <td className="py-1.5 text-right tabular-nums">{m(ln.net_amount)}</td>
            <td className="py-1.5 text-right tabular-nums">
              {m(ln.vat_amount)} <span className="text-foreground-secondary">({ln.vat_rate}%)</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function DetailSheet() {
  const { t } = useTx();
  const [selected, detail, status, busy, key, online] = useUnit([
    $selectedId,
    $detail,
    $detailStatus,
    $busy,
    $key,
    $isOnline,
  ]);
  const [close, signAccept, reject, signSend, cancelOut] = useUnit([
    einvoiceSelected,
    signAcceptRequested,
    rejectSubmitted,
    signSendRequested,
    cancelOutSubmitted,
  ]);
  const canPost = useCan({ permission: "purchases.post" });
  const canSign = useCan({ permission: "einvoice.sign" });
  const canReceive = useCan({ permission: "purchases.receive" });
  const [receiptOpen, setReceiptOpen] = useState(false);
  const openReceipt = useUnit(receiptDialogOpened);
  const [dialog, setDialog] = useState<"reject" | "cancel" | null>(null);

  const incoming = detail?.direction === "in";
  const signReady = online && key !== null && !busy;

  return (
    <Sheet open={selected !== null} onOpenChange={(open) => (open ? undefined : close(null))}>
      <SheetContent wide>
        <SheetHeader>
          <SheetTitle>{detail?.number ?? detail?.operator_doc_id ?? t("detail.title")}</SheetTitle>
          <SheetDescription>{detail?.counterparty.name ?? ""}</SheetDescription>
        </SheetHeader>
        <SheetBody>
          {status === "loading" || !detail ? (
            <Skeleton className="h-40 w-full" />
          ) : (
            <div className="flex flex-col gap-4" data-testid="einvoice-detail">
              <div className="flex flex-wrap gap-2">
                <DocStatusChip status={detail.status} scope={incoming ? "in" : "out"} />
                {incoming ? <RiskChip flag={detail.risk_flag} /> : null}
                {detail.factura_type !== "standard" ? (
                  <span className="text-[13px] text-foreground-secondary">
                    {t(`facturaType.${detail.factura_type}`)}
                  </span>
                ) : null}
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-[13px]">
                <dt className="text-foreground-secondary">{t("detail.stir")}</dt>
                <dd>{detail.counterparty.stir ?? "—"}</dd>
                <dt className="text-foreground-secondary">{t("columns.date")}</dt>
                <dd>{detail.doc_date ? formatDate(detail.doc_date) : "—"}</dd>
                <dt className="text-foreground-secondary">{t("detail.operatorId")}</dt>
                <dd>{detail.operator_doc_id ?? "—"}</dd>
              </dl>
              <Lines detail={detail} />
              <dl
                className="grid grid-cols-3 gap-2 rounded-xl bg-accent p-3 text-[13px]"
                data-testid="detail-totals"
              >
                <div>
                  <dt className="text-foreground-secondary">{t("detail.net")}</dt>
                  <dd className="font-bold tabular-nums">{m(netOf(detail))}</dd>
                </div>
                <div>
                  <dt className="text-foreground-secondary">{t("detail.vat")}</dt>
                  <dd className="font-bold tabular-nums">{m(detail.vat_amount)}</dd>
                </div>
                <div>
                  <dt className="text-foreground-secondary">{t("detail.total")}</dt>
                  <dd className="font-bold tabular-nums">{m(detail.total_amount)}</dd>
                </div>
              </dl>
              {detail.last_error ? (
                <Banner tone="destructive" icon={CircleAlert}>
                  {t("detail.lastError", { error: detail.last_error })}
                </Banner>
              ) : null}
              {!online ? (
                <Banner tone="warning" icon={Info}>
                  {t("offlineSign")}
                </Banner>
              ) : null}

              {incoming ? (
                <>
                  {canPost && detail.status !== "rejected" && detail.status !== "cancelled" ? (
                    <RiskForm key={detail.id} detail={detail} />
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    {canPost && canSign && (detail.status === "received" || detail.status === "signed") ? (
                      <Button disabled={!signReady} onClick={() => signAccept()} data-testid="sign-accept">
                        <Icon as={ShieldCheck} size="sm" />
                        {t("actions.signAccept")}
                      </Button>
                    ) : null}
                    {canPost && (detail.status === "received" || detail.status === "signed") ? (
                      <Button
                        variant="destructive-outline"
                        disabled={busy}
                        onClick={() => setDialog("reject")}
                      >
                        <Icon as={X} size="sm" />
                        {t("actions.reject")}
                      </Button>
                    ) : null}
                  </div>
                  {detail.status === "accepted" ? (
                    canReceive ? (
                      <Button
                        variant="secondary"
                        data-testid="create-receipt"
                        onClick={() => {
                          openReceipt();
                          setReceiptOpen(true);
                        }}
                      >
                        <Icon as={PackagePlus} size="sm" />
                        {t("actions.createReceipt")}
                      </Button>
                    ) : null
                  ) : (
                    <p className="text-[13px] text-foreground-secondary">{t("detail.afterAccept")}</p>
                  )}
                </>
              ) : (
                <>
                  {detail.related_doc_type === "sales" ? (
                    <Banner tone="info" icon={Info}>
                      {t("noSecondVat")}
                    </Banner>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    {canSign && (detail.status === "draft" || detail.status === "signed") ? (
                      <Button disabled={!signReady} onClick={() => signSend()} data-testid="sign-send">
                        {detail.status === "draft" ? (
                          <Icon as={PenLine} size="sm" />
                        ) : (
                          <Icon as={Send} size="sm" />
                        )}
                        {detail.status === "draft" ? t("actions.signSend") : t("actions.send")}
                      </Button>
                    ) : null}
                    {canSign && (detail.status === "draft" || detail.status === "signed") ? (
                      <Button
                        variant="destructive-outline"
                        disabled={busy}
                        onClick={() => setDialog("cancel")}
                      >
                        <Icon as={X} size="sm" />
                        {t("actions.cancelOut")}
                      </Button>
                    ) : null}
                  </div>
                </>
              )}
            </div>
          )}
        </SheetBody>
      </SheetContent>
      {detail && detail.direction === "in" ? (
        <ReceiptDialog key={detail.id} detail={detail} open={receiptOpen} onOpenChange={setReceiptOpen} />
      ) : null}
      <ReasonDialog
        open={dialog !== null}
        onOpenChange={(open) => (open ? undefined : setDialog(null))}
        title={dialog === "cancel" ? t("actions.cancelOut") : t("actions.reject")}
        confirmLabel={dialog === "cancel" ? t("actions.cancelOut") : t("actions.reject")}
        pending={busy}
        onSubmit={(reason) => (dialog === "cancel" ? cancelOut(reason) : reject(reason))}
      />
    </Sheet>
  );
}

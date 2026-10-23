/**
 * «Qabul qilish» (07 POS-09 / BO-03, 19 §13 receive): `qty_received` per line (default = yuborilgan,
 * `0 ≤ qabul ≤ yuborilgan`); the shortage is shown before confirming — with a shortage the transfer
 * becomes `discrepancy` (kamomad provodkasi, 13 §2.10).
 */
import { useUnit } from "effector-react";
import { TriangleAlert } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import {
  Banner,
  Button,
  DecimalInput,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  toast,
} from "@shared/ui";

import { useQtyFormat } from "#/entities/refs/index.ts";
import { isZero, qty3, subtractQty, sumQty } from "#/shared/lib/decimal.ts";
import { errorText } from "#/shared/lib/errors.ts";

import { receiveDefaults, receiveLineError, receiveTransferFx, type Transfer } from "../model/index.ts";

export function ReceiveDialog({ transfer, onClose }: { transfer: Transfer | null; onClose: () => void }) {
  return transfer ? <ReceiveForm key={transfer.id} transfer={transfer} onClose={onClose} /> : null;
}

function ReceiveForm({ transfer, onClose }: { transfer: Transfer; onClose: () => void }) {
  const { t } = useTranslation("warehouse");
  const formatQty = useQtyFormat();
  const [receive, pending] = useUnit([receiveTransferFx, receiveTransferFx.pending]);
  const [values, setValues] = useState<Record<string, string>>(() => receiveDefaults(transfer));
  const [error, setError] = useState<string | null>(null);

  const lineErrors = transfer.lines.map((l) => receiveLineError(l.qty_sent, values[l.id] ?? ""));
  const valid = lineErrors.every((e) => e === null);
  const shortage = valid
    ? sumQty(transfer.lines.map((l) => subtractQty(l.qty_sent, values[l.id] ?? "0")))
    : null;

  const submit = () => {
    if (!valid) return;
    setError(null);
    receive({
      id: transfer.id,
      lines: transfer.lines.map((l) => ({ transfer_line_id: l.id, qty_received: qty3(values[l.id] ?? "0") })),
    })
      .then((res) => {
        toast.success(
          res.status === "discrepancy"
            ? t("transfers.toast.receivedShortage", { number: res.number ?? "" })
            : t("transfers.toast.received", { number: res.number ?? "" }),
        );
        onClose();
      })
      .catch((e: unknown) => setError(errorText(e)));
  };

  return (
    <Dialog open onOpenChange={(open) => (open || pending ? undefined : onClose())}>
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle>{t("transfers.receive.title", { number: transfer.number ?? "" })}</DialogTitle>
          <DialogDescription>{t("transfers.receive.description")}</DialogDescription>
        </DialogHeader>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-[13px]" aria-label={t("transfers.linesLabel")}>
            <thead className="bg-muted text-caption text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left">{t("transfers.lines.product")}</th>
                <th className="px-3 py-2 text-right">{t("transfers.lines.sent")}</th>
                <th className="px-3 py-2 text-right">{t("transfers.lines.received")}</th>
                <th className="px-3 py-2 text-right">{t("transfers.lines.shortage")}</th>
              </tr>
            </thead>
            <tbody>
              {transfer.lines.map((l, i) => {
                const value = values[l.id] ?? "";
                const lineError = lineErrors[i];
                const short = lineError === null ? subtractQty(l.qty_sent, value) : null;
                return (
                  <tr key={l.id} className="border-t border-divider align-top">
                    <td className="px-3 py-2 font-semibold">{l.product_name}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{formatQty(l.qty_sent)}</td>
                    <td className="w-40 px-3 py-2">
                      <DecimalInput
                        aria-label={t("transfers.receive.qtyFor", { name: l.product_name })}
                        aria-invalid={lineError !== null || undefined}
                        precision={3}
                        outputScale={3}
                        value={value}
                        onChange={(v) => setValues((prev) => ({ ...prev, [l.id]: v }))}
                      />
                      {lineError ? (
                        <p role="alert" className="mt-1 text-[12px] font-semibold text-destructive">
                          {t(`transfers.receive.error.${lineError}`)}
                        </p>
                      ) : null}
                    </td>
                    <td
                      className={
                        short !== null && !isZero(short)
                          ? "px-3 py-2 text-right font-bold tabular-nums text-destructive-strong"
                          : "px-3 py-2 text-right tabular-nums"
                      }
                    >
                      {short === null ? "—" : formatQty(short)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {shortage !== null && !isZero(shortage) ? (
          <Banner tone="warning" icon={TriangleAlert}>
            {t("transfers.receive.shortage", { qty: formatQty(shortage) })}
          </Banner>
        ) : null}
        {error ? (
          <Banner tone="destructive" icon={TriangleAlert} live="assertive">
            {error}
          </Banner>
        ) : null}
        <DialogFooter>
          <Button variant="secondary" disabled={pending} onClick={onClose}>
            {t("actions.back")}
          </Button>
          <Button disabled={!valid || pending} aria-busy={pending || undefined} onClick={submit}>
            {t("transfers.actions.receive")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

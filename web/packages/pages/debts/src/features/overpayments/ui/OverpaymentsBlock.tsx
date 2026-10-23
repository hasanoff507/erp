/**
 * «Ortiqcha to'lovlar» (07 BO-06, qaror #67): customer · unallocated amount · date · Kt 6310, and the
 * actions (`accounting.post`): «Qaytarish» (RefundDialog — a 6310 cash movement from an open shift) and
 * «Keyingi qarzga hisoblash» (OffsetDialog — `ledger_adjustments` Dt 6310 / Kt 4010). Online only.
 */
import { useUnit } from "effector-react";
import { HandCoins } from "lucide-react";
import { useEffect, useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDateTime, formatMoney } from "@shared/lib/format";
import { $isOnline } from "@shared/state/network";
import { Button, Icon, StatusChip } from "@shared/ui";

import { loadOverpaymentsFx, type Overpayment } from "../model/index.ts";
import { OffsetDialog } from "./OffsetDialog.tsx";
import { RefundDialog } from "./RefundDialog.tsx";

export interface OverpaymentsBlockProps {
  /** counterparty id → name (debtor rows already loaded). */
  names: Readonly<Record<string, string>>;
  /** Changes when the page reloads (re-read the list). */
  version: number;
  /** `accounting.post` + `cash.withdraw` — «Qaytarish» (07 BO-06). */
  canRefund: boolean;
  /** `accounting.post` — «Keyingi qarzga hisoblash» (07 BO-06, B5-T14). */
  canOffset: boolean;
  /** The debt changed (offset posted) — the page re-reads its lists. */
  onChanged?: () => void;
}

export function OverpaymentsBlock({ names, version, canRefund, canOffset, onChanged }: OverpaymentsBlockProps) {
  const { t } = useTranslation("debts");
  const online = useUnit($isOnline);
  const [rows, setRows] = useState<Overpayment[] | null>(null);
  const [refunding, setRefunding] = useState<Overpayment | null>(null);
  const [offsetting, setOffsetting] = useState<Overpayment | null>(null);
  const [reloads, setReloads] = useState(0);
  useEffect(() => {
    let alive = true;
    loadOverpaymentsFx()
      .then((r) => alive && setRows(r))
      // no right to read sync exceptions (BO-14 reviewers) or offline — the block stays hidden
      .catch(() => alive && setRows(null));
    return () => {
      alive = false;
    };
  }, [version, reloads]);
  if (!rows || rows.length === 0) return null;
  const customer = (r: Overpayment) => (r.counterpartyId && names[r.counterpartyId]) || t("overpay.customer");
  return (
    <section
      className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-4"
      data-testid="overpayments"
    >
      <h3 className="flex items-center gap-2 text-[15px] font-extrabold">
        <Icon as={HandCoins} size="md" />
        {t("overpay.title")}
        <StatusChip tone="warning">{rows.length}</StatusChip>
      </h3>
      <ul className="flex flex-col gap-2">
        {rows.map((r) => (
          <li key={r.id} className="flex flex-col rounded-lg bg-muted px-3 py-2 text-[13px]">
            <span className="font-bold">
              {customer(r)} · {formatMoney(r.unallocated, { withCurrency: false })}
            </span>
            <span className="text-[12px] text-muted-foreground">
              {formatDateTime(r.createdAt)} · {t("overpay.account")}
            </span>
            {canRefund || canOffset ? (
              <span className="mt-2 flex flex-wrap gap-2">
                {canRefund ? (
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={!online || !r.counterpartyId}
                    title={r.counterpartyId ? undefined : t("overpay.refund.noCustomer")}
                    onClick={() => setRefunding(r)}
                    data-testid={`overpay-refund-${r.id}`}
                  >
                    {t("overpay.refund.action")}
                  </Button>
                ) : null}
                {canOffset ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={!online || !r.counterpartyId}
                    title={r.counterpartyId ? undefined : t("overpay.refund.noCustomer")}
                    onClick={() => setOffsetting(r)}
                    data-testid={`overpay-offset-${r.id}`}
                  >
                    {t("overpay.offset.action")}
                  </Button>
                ) : null}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
      <p className="text-[12px] text-foreground-secondary">{t("overpay.howTo")}</p>
      {refunding ? (
        <RefundDialog
          row={refunding}
          customer={customer(refunding)}
          onClose={() => setRefunding(null)}
          onDone={() => setReloads((n) => n + 1)}
        />
      ) : null}
      {offsetting ? (
        <OffsetDialog
          row={offsetting}
          customer={customer(offsetting)}
          onClose={() => setOffsetting(null)}
          onDone={() => {
            setReloads((n) => n + 1);
            onChanged?.();
          }}
        />
      ) : null}
    </section>
  );
}

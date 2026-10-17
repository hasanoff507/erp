/**
 * BO-06 right panel — the selected debtor: name, phone, debt, limit · discount, «Qarz daftari», «Mijoz
 * kartasi», «Boshlang'ich qarz», Owner actions (shubhali belgi, qarzni kechish), the reminder draft (a fixed
 * template — AI-06 drafting and Telegram sending come with Bosqich 6; nothing is sent automatically) and the
 * bank-transfer payment form (cash / card / QR debt payments are POS-13 only).
 */
import { useUnit } from "effector-react";
import { BookOpen, Copy, Flag, FlagOff, HandCoins, IdCard, MessageSquareText, Plus } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney, formatPhone } from "@shared/lib/format";
import type { Money } from "@shared/lib/money";
import type { AgingRow } from "@shared/models";
import { $branches, $tenant } from "@shared/state/session";
import { Button, Icon, StatusChip, toast } from "@shared/ui";

import { promiseOf } from "#/entities/debtor/index.ts";
import { BankPaymentForm } from "#/features/bank-payment/index.ts";
import { ledgerOpened } from "#/features/debt-ledger/index.ts";

import { $branchId, $direction } from "../../model/index.ts";

export interface DebtorRights {
  ledger: boolean;
  pay: boolean;
  open: boolean;
  forgive: boolean;
  card: boolean;
}

export type PanelDialog = "card" | "opening" | "writeoff" | "flag";

export interface DebtorPanelProps {
  row: AgingRow;
  rights: DebtorRights;
  online: boolean;
  onDialog: (dialog: PanelDialog) => void;
}

export function DebtorPanel({ row, rights, online, onDialog }: DebtorPanelProps) {
  const { t } = useTranslation("debts");
  const [direction, branches, branchId, tenant, openLedger] = useUnit([
    $direction,
    $branches,
    $branchId,
    $tenant,
    ledgerOpened,
  ]);
  const payable = direction === "payable";
  const promise = promiseOf(row);
  const reminder = t("reminder.template", {
    name: row.name,
    store: tenant?.name ?? "",
    amount: formatMoney(row.balance),
    date: promise ? formatDate(promise) : t("reminder.noDate"),
  });
  return (
    <aside className="flex flex-col gap-3" data-testid="debtor-panel">
      <section className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4">
        <div className="flex flex-col">
          <span className="flex items-center gap-2 text-[17px] font-extrabold" data-testid="panel-name">
            {row.name}
            {row.doubtful_flag ? <StatusChip tone="destructive">{t("table.doubtful")}</StatusChip> : null}
          </span>
          <span className="text-[13px] text-muted-foreground">
            {row.phone ? formatPhone(row.phone) : "—"}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-[13px]">
          <div className="flex flex-col rounded-lg bg-muted px-3 py-2">
            <span className="text-muted-foreground">{t("panel.debt")}</span>
            <span className="text-[18px] font-extrabold tabular-nums" data-testid="panel-balance">
              {formatMoney(row.balance, { withCurrency: false })}
            </span>
          </div>
          {payable ? null : (
            <div className="flex flex-col rounded-lg bg-muted px-3 py-2">
              <span className="text-muted-foreground">{t("panel.limit")}</span>
              <span className="text-[15px] font-bold">
                {row.credit_limit
                  ? formatMoney(row.credit_limit, { withCurrency: false })
                  : t("table.noLimit")}
              </span>
            </div>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {rights.ledger ? (
            <Button
              size="sm"
              variant="secondary"
              data-testid="open-ledger"
              onClick={() => openLedger({ counterpartyId: row.counterparty_id, direction })}
            >
              <Icon as={BookOpen} size="sm" />
              {t("panel.ledger")}
            </Button>
          ) : null}
          {!payable ? (
            <Button size="sm" variant="secondary" data-testid="open-card" onClick={() => onDialog("card")}>
              <Icon as={IdCard} size="sm" />
              {t("panel.card")}
            </Button>
          ) : null}
          {rights.open ? (
            <Button
              size="sm"
              variant="secondary"
              disabled={!online}
              data-testid="panel-opening"
              onClick={() => onDialog("opening")}
            >
              <Icon as={Plus} size="sm" />
              {t("panel.opening")}
            </Button>
          ) : null}
          {rights.forgive && !payable ? (
            <>
              <Button
                size="sm"
                variant="secondary"
                disabled={!online}
                data-testid="panel-flag"
                onClick={() => onDialog("flag")}
              >
                <Icon as={row.doubtful_flag ? FlagOff : Flag} size="sm" />
                {row.doubtful_flag ? t("panel.unflag") : t("panel.flag")}
              </Button>
              <Button
                size="sm"
                variant="destructive-outline"
                disabled={!online}
                data-testid="panel-writeoff"
                onClick={() => onDialog("writeoff")}
              >
                <Icon as={HandCoins} size="sm" />
                {t("panel.writeoff")}
              </Button>
            </>
          ) : null}
        </div>
      </section>

      {payable ? (
        <p className="rounded-2xl border border-border bg-card p-4 text-[13px] text-foreground-secondary">
          {t("panel.payableNote")}
        </p>
      ) : (
        <section
          className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-4"
          data-testid="reminder"
        >
          <h3 className="flex items-center gap-2 text-[15px] font-extrabold">
            <Icon as={MessageSquareText} size="md" />
            {t("reminder.title")}
          </h3>
          <p className="rounded-lg bg-muted px-3 py-2 text-[13px]" data-testid="reminder-text">
            {reminder}
          </p>
          <Button
            size="sm"
            variant="secondary"
            onClick={() =>
              void navigator.clipboard
                ?.writeText(reminder)
                .then(() => toast.success(t("reminder.copied")))
                .catch(() => undefined)
            }
          >
            <Icon as={Copy} size="sm" />
            {t("reminder.copy")}
          </Button>
          <p className="text-[12px] text-muted-foreground">{t("reminder.note")}</p>
        </section>
      )}

      {!payable && rights.pay ? (
        <BankPaymentForm
          key={row.counterparty_id}
          counterpartyId={row.counterparty_id}
          balance={row.balance as Money}
          branches={branches}
          defaultBranchId={branchId}
          disabled={!online}
        />
      ) : null}
    </aside>
  );
}

/**
 * The debt part of a sale (B4, w-debts) — POS-03 «Nasiya» panel and POS-06 body: the customer (pick or «+ Yangi
 * mijoz», offline too), debt summary against the credit limit (last known balance + this device's unsynced debt
 * sales, 16 §5), promise date (7 / 14 / 30 days or a date, ≥ today), and the over-limit step: online a Manager
 * approval (`debts.approve`, local PIN or remote request, 18 §2.4), offline the cashier's explicit confirmation —
 * the sale is not blocked, the server flags `debt_limit_exceeded_offline` and notifies the owner.
 */
import { useUnit } from "effector-react";
import { CircleAlert, UserRound } from "lucide-react";
import { useEffect, useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatPhone } from "@shared/lib/format";
import type { Money } from "@shared/lib/money";
import { pullApplied, type CustomerDebtView } from "@shared/offline";
import { Banner, Button, Checkbox, Icon, Input, Label } from "@shared/ui";

import { $draft, customerSet } from "#/entities/receipt-draft/index.ts";
import { $posCashier, cashierCan } from "#/entities/pos-session/index.ts";
import { CustomerPicker, DebtSummary, limitCheck, loadDebtViewFx } from "#/features/debt-customer/index.ts";
import { ManagerApprovalDialog } from "#/features/manager-approval/index.ts";
import { tashkentDate } from "#/shared/lib/dates.ts";

import { $payment, debtApproved, debtOverLimitConfirmed, dueDateChanged } from "../model/payment.ts";

export function addDays(days: number): string {
  return tashkentDate(new Date(Date.now() + days * 86_400_000));
}

/** The chosen customer's debt view, re-read after a pull (balance / limit change) and on a new customer. */
export function useDebtView(customerId: string | null): CustomerDebtView | null {
  const [view, setView] = useState<CustomerDebtView | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => pullApplied.watch(() => setTick((n) => n + 1)), []);
  useEffect(() => {
    let alive = true;
    if (!customerId) return;
    void loadDebtViewFx(customerId).then((v) => alive && setView(v ?? null));
    return () => {
      alive = false;
    };
  }, [customerId, tick]);
  return view && view.customer.id === customerId ? view : null;
}

/** «Tasdiq so'rash» — a POS touch target (≥ 48 px, 08 §2, WEB-09). */
export function DebtAskApprovalButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button size="pos" variant="warning" onClick={onClick} data-testid="debt-ask-approval">
      {label}
    </Button>
  );
}

export interface DebtSalePanelProps {
  amount: Money;
  online: boolean;
  /** POS-06: open the picker with the quick form when no customer is chosen yet. */
  autoPick?: boolean;
}

export function DebtSalePanel({ amount, online, autoPick = false }: DebtSalePanelProps) {
  const { t } = useTranslation("pos");
  const [p, draft, cashier, setDue, approve, confirmOver, setCustomer] = useUnit([
    $payment,
    $draft,
    $posCashier,
    dueDateChanged,
    debtApproved,
    debtOverLimitConfirmed,
    customerSet,
  ]);
  const view = useDebtView(draft.customerId);
  const [picking, setPicking] = useState(autoPick && !draft.customerId);
  const [approving, setApproving] = useState(false);
  const check = limitCheck(view, amount, online);
  // 18 §11.1: the quick customer exists to keep a debt — `debts.create` only (26 #188)
  const canCreateCustomer = cashierCan(cashier, "debts.create");
  const today = addDays(0);

  return (
    <div className="flex flex-col gap-3" data-testid="debt-panel">
      <div className="flex items-center gap-3 rounded-xl border border-border p-3">
        <Icon as={UserRound} size="lg" className="text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <div className="font-bold" data-testid="debt-customer-name">
            {view?.customer.name ?? t("payment.debtNoCustomer")}
          </div>
          {view?.customer.phone ? (
            <div className="text-[12px] text-muted-foreground">{formatPhone(view.customer.phone)}</div>
          ) : null}
        </div>
        <Button size="pos" variant="secondary" onClick={() => setPicking(true)} data-testid="debt-customer">
          {t("payment.debtPickCustomer")}
        </Button>
      </div>
      {view ? <DebtSummary view={view} amount={amount} check={check} /> : null}

      <Label>{t("payment.dueDate")}</Label>
      <div className="flex flex-wrap items-center gap-2">
        {[7, 14, 30].map((d) => (
          <Button
            key={d}
            size="pos"
            variant={p?.dueDate === addDays(d) ? "default" : "secondary"}
            onClick={() => setDue(addDays(d))}
            data-testid={`due-${d}`}
          >
            {t("payment.dueDays", { n: d })}
          </Button>
        ))}
        <Input
          type="date"
          aria-label={t("payment.dueDate")}
          min={today}
          value={p?.dueDate ?? ""}
          onChange={(e) => setDue(e.target.value && e.target.value >= today ? e.target.value : null)}
          className="h-12 w-48"
        />
      </div>

      {check.needsApproval && !p?.debtApproval ? (
        <Banner
          tone="warning"
          icon={CircleAlert}
          action={
<DebtAskApprovalButton label={t("payment.debtAskApproval")} onClick={() => setApproving(true)} />
          }
        >
          {t("payment.debtOverLimit")}
        </Banner>
      ) : null}
      {check.needsOfflineConfirm ? (
        <Banner tone="warning" icon={CircleAlert} live="assertive">
          <span className="flex flex-col gap-2">
            {t("payment.debtOverLimitOffline")}
            <label className="flex min-h-12 items-center gap-3 font-bold">
              <Checkbox
                checked={p?.debtOverLimitConfirmed === true}
                onCheckedChange={(v) => confirmOver(v === true)}
                data-testid="debt-offline-confirm"
              />
              {t("debts.overLimitConfirm")}
            </label>
          </span>
        </Banner>
      ) : null}
      {p?.debtApproval ? (
        <p className="text-[13px] font-bold text-success-strong">{t("payment.debtApproved")}</p>
      ) : null}
      {!cashierCan(cashier, "debts.create") ? (
        <Banner tone="destructive" icon={CircleAlert}>
          {t("payment.debtNoRight")}
        </Banner>
      ) : null}

      {picking ? (
        <CustomerPicker
          selectedId={draft.customerId}
          actorUserId={cashier?.userId ?? null}
          canCreate={canCreateCustomer}
          startWithNew={false}
          onSelect={(c) => {
            setCustomer(c?.id ?? null);
            approve(null);
            confirmOver(false);
            setPicking(false);
          }}
          onClose={() => setPicking(false)}
        />
      ) : null}
      {approving ? (
        <ManagerApprovalDialog
          kind="debt_over_limit"
          permission="debts.approve"
          amount={amount}
          context={{ amount, counterparty_id: draft.customerId }}
          requesterId={cashier?.userId ?? null}
          reason={t("payment.debtOverLimit")}
          allowRemote={online}
          onApproved={(ref) => {
            approve(ref);
            setApproving(false);
          }}
          onClose={() => setApproving(false)}
        />
      ) : null}
    </div>
  );
}

/** Confirm is allowed: a customer, the right, and the over-limit step done (approval online / confirm offline). */
export function debtReady(
  view: CustomerDebtView | null,
  amount: Money,
  online: boolean,
  approved: boolean,
  confirmed: boolean,
): boolean {
  if (!view) return false;
  const check = limitCheck(view, amount, online);
  if (check.needsApproval && !approved) return false;
  if (check.needsOfflineConfirm && !confirmed) return false;
  return true;
}

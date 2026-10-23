import { useUnit } from "effector-react";
import { ArrowDownToLine, ArrowUpFromLine, CircleAlert, Wallet } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatDateTime, formatMoney } from "@shared/lib/format";
import { subtractMoney, addMoney, type Money } from "@shared/lib/money";
import { $isOnline } from "@shared/state/network";
import {
  Banner,
  Button,
  EmptyState,
  FormField,
  Icon,
  Kbd,
  NoPermissionState,
  SegmentedControl,
  Textarea,
  cn,
} from "@shared/ui";

import {
  $posCashier,
  $posShift,
  NumPad,
  PosScreen,
  cashierCan,
  defaultShiftDataDeps,
  loadShiftSnapshot,
  numPadAppend,
  type ShiftSnapshot,
} from "#/entities/pos-session/index.ts";
import { digitKeys, useHotkeys } from "#/shared/lib/use-hotkeys.ts";
import { ManagerApprovalDialog, type ApprovalRef } from "#/features/manager-approval/index.ts";
import { ExpenseMode } from "#/features/pos-expense/index.ts";

import {
  COMMENT_MAX,
  REASONS,
  cashMovementPayload,
  defaultCashMovementDeps,
  digitsToMoney,
  newMovementId,
  validateMovement,
  withdrawalNeedsApproval,
  type Direction,
  type MovementError,
  type Reason,
} from "../../model/index.ts";

const POS_SALE = "/pos/sale";

/** POS-14 — Kassaga pul qo'yish / kassadan pul olish (07, route /pos/cash-movement; maket Pos14KassaPul). */
function CashMovementPage() {
  const { t } = useTranslation("pos");
  const navigate = useNavigate();
  const [cashier, shift, online] = useUnit([$posCashier, $posShift, $isOnline]);
  const canIn = cashierCan(cashier, "cash.deposit");
  const canOut = cashierCan(cashier, "cash.withdraw");
  // the cashier loads asynchronously — the default mode follows her rights until she picks one
  const [picked, setDirection] = useState<Direction | null>(null);
  const direction: Direction = picked ?? (canOut ? "out" : "in");
  // POS-14 «Xarajat» (B4): a cash expense from the till — `cash.withdraw` (limit), `expense.created`
  const [expenseMode, setExpenseMode] = useState(false);
  const [digits, setDigits] = useState("");
  const [reason, setReason] = useState<Reason | null>(null);
  const [comment, setComment] = useState("");
  const [errors, setErrors] = useState<MovementError[]>([]);
  const [needApproval, setNeedApproval] = useState(false);
  const [ownLimit, setOwnLimit] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<Money | null>(null);
  const [failed, setFailed] = useState(false);
  const [sole, setSole] = useState(true);
  const [snapshot, setSnapshot] = useState<ShiftSnapshot | null>(null);

  const back = useCallback(() => void navigate(POS_SALE), [navigate]);

  const reload = useCallback(() => {
    if (!shift) return;
    void loadShiftSnapshot(
      defaultShiftDataDeps(() => online),
      shift,
    )
      .then(setSnapshot)
      .catch(() => setSnapshot(null));
  }, [shift, online]);

  useEffect(() => {
    reload();
    void defaultCashMovementDeps.soleProprietor().then(setSole);
  }, [reload]);

  const amount = digitsToMoney(digits);
  const form = { direction, digits, reason, comment };

  const commit = async (approval: ApprovalRef | null) => {
    if (!cashier || !shift || !amount || !reason) return;
    setBusy(true);
    setFailed(false);
    try {
      await defaultCashMovementDeps.enqueue(
        cashMovementPayload({
          id: newMovementId(),
          cashRegisterId: shift.cash_register_id,
          shiftId: shift.id,
          direction,
          reason,
          amount,
          comment,
          approval,
        }),
        cashier.userId,
      );
      setDone(amount);
      setDigits("");
      setReason(null);
      setComment("");
      setNeedApproval(false);
      reload();
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    if (busy || !cashier) return;
    const found = validateMovement(form, sole);
    setErrors(found);
    setDone(null);
    if (found.length > 0 || !amount) return;
    if (direction === "out") {
      const own = await defaultCashMovementDeps.ownLimit(cashier.userId);
      if (withdrawalNeedsApproval(cashier, own, amount)) {
        setOwnLimit(own ?? "0.00");
        setNeedApproval(true);
        return;
      }
    }
    await commit(null);
  };

  useHotkeys(
    [
      ...digitKeys((d) => setDigits((v) => numPadAppend(v, d))),
      { key: "Backspace", handler: () => setDigits((v) => v.slice(0, -1)) },
      // while the approval form is open its own Enter (PIN submit) wins
      ...(needApproval ? [] : [{ key: "Enter", handler: () => void submit() }]),
      { key: "Escape", handler: () => (needApproval ? setNeedApproval(false) : back()) },
    ],
    // the «Xarajat» mode has its own keys (ExpenseMode)
    !expenseMode,
  );

  if (!cashier || (!canIn && !canOut)) {
    return (
      <PosScreen title={t("cashMovement.title")} backLabel={t("cashMovement.back")} onBack={back}>
        <NoPermissionState />
      </PosScreen>
    );
  }
  if (!shift) {
    return (
      <PosScreen title={t("cashMovement.title")} backLabel={t("cashMovement.back")} onBack={back}>
        <EmptyState icon={Wallet} title={t("cashMovement.noShift")} />
      </PosScreen>
    );
  }

  const nowCash = snapshot?.expectedCash ?? null;
  const after =
    nowCash && amount
      ? direction === "out"
        ? subtractMoney(nowCash, amount)
        : addMoney(nowCash, amount)
      : nowCash;
  const errorOf = (field: MovementError) =>
    errors.includes(field) ? t(`cashMovement.errors.${field}`) : null;

  return (
    <PosScreen
      testId="pos-cash-movement"
      title={t("cashMovement.title")}
      subtitle={t("cashMovement.shift", { number: shift.shift_no })}
      backLabel={t("cashMovement.back")}
      onBack={back}
    >
      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <div className="flex flex-col gap-4">
          <SegmentedControl<"in" | "out" | "expense">
            density="touch"
            label={t("cashMovement.direction")}
            value={expenseMode ? "expense" : direction}
            onChange={(v) => {
              if (v === "expense") {
                if (canOut) {
                  setExpenseMode(true);
                  setNeedApproval(false);
                  setDone(null);
                }
                return;
              }
              if ((v === "in" && !canIn) || (v === "out" && !canOut)) return;
              setExpenseMode(false);
              setDirection(v);
              setReason(null);
              setErrors([]);
              setNeedApproval(false);
            }}
            options={[
              { value: "in", label: t("cashMovement.modes.in") },
              { value: "out", label: t("cashMovement.modes.out") },
              { value: "expense", label: t("cashMovement.modes.expense") },
            ]}
          />
          {expenseMode ? (
            <ExpenseMode
              onBack={back}
              onDone={reload}
              renderApproval={(slot) => (
                <ManagerApprovalDialog
                  inline
                  kind="cash_withdrawal_over_limit"
                  permission="cash.withdraw"
                  amount={slot.amount}
                  context={slot.context}
                  requesterId={cashier.userId}
                  reason={t("posExpense.overLimit", { limit: formatMoney(slot.ownLimit) })}
                  allowRemote={slot.allowRemote}
                  onApproved={slot.onApproved}
                  onClose={slot.onClose}
                />
              )}
            />
          ) : null}
          {expenseMode ? null : (
            <>
              <FormField label={t("cashMovement.amount")} required error={errorOf("amount")}>
                <output
                  data-testid="movement-amount"
                  className="flex h-16 items-center justify-end rounded-xl border border-input bg-card px-4 text-[30px] font-extrabold tabular-nums"
                >
                  {formatMoney(amount ?? "0.00", { withCurrency: false })}{" "}
                  <span className="ml-2 text-[16px] text-foreground-secondary">{t("cashMovement.som")}</span>
                </output>
              </FormField>
              <NumPad value={digits} onChange={setDigits} backspaceLabel={t("cashMovement.backspace")} />
              <FormField
                label={t("cashMovement.reason")}
                required
                error={errorOf("reason") ?? errorOf("founder")}
              >
                <div role="radiogroup" className="flex flex-wrap gap-2">
                  {REASONS[direction].map((r) => (
                    <button
                      key={r}
                      type="button"
                      role="radio"
                      aria-checked={reason === r}
                      data-testid={`reason-${r}`}
                      onClick={() => setReason(r)}
                      className={cn(
                        "h-12 rounded-xl border px-4 text-[14px] font-bold",
                        reason === r
                          ? "border-primary bg-primary-soft text-primary-strong"
                          : "border-border bg-card",
                      )}
                    >
                      {t(`cashMovement.reasons.${r}`)}
                    </button>
                  ))}
                </div>
              </FormField>
              {reason === "owner_withdrawal" && !sole ? (
                <Banner tone="warning" icon={CircleAlert}>
                  {t("cashMovement.founderBackOffice")}
                </Banner>
              ) : null}
              <FormField
                label={t("cashMovement.comment")}
                required={reason === "other"}
                optional={reason !== "other"}
                error={errorOf("comment")}
              >
                <Textarea
                  value={comment}
                  maxLength={COMMENT_MAX}
                  rows={2}
                  data-testid="movement-comment"
                  onChange={(e) => setComment(e.target.value)}
                />
              </FormField>
              {needApproval && amount ? (
                <ManagerApprovalDialog
                  inline
                  kind="cash_withdrawal_over_limit"
                  permission="cash.withdraw"
                  amount={amount}
                  context={{ amount, reason: reason ?? "other" }}
                  requesterId={cashier.userId}
                  reason={t("cashMovement.overLimit", { limit: formatMoney(ownLimit ?? "0.00") })}
                  allowRemote={online}
                  onApproved={(a) => void commit(a)}
                  onClose={() => setNeedApproval(false)}
                />
              ) : null}
              {done ? (
                <Banner tone="success" icon={Wallet} live="polite">
                  <span data-testid="movement-done">
                    {t("cashMovement.done", { amount: formatMoney(done) })}
                  </span>
                </Banner>
              ) : null}
              {failed ? (
                <Banner tone="destructive" icon={CircleAlert} live="assertive">
                  {t("cashMovement.failed")}
                </Banner>
              ) : null}
              {!needApproval ? (
                <Button
                  size="pos-cta"
                  disabled={busy}
                  onClick={() => void submit()}
                  data-testid="movement-submit"
                >
                  <Icon as={direction === "out" ? ArrowUpFromLine : ArrowDownToLine} size="lg" />
                  {direction === "out"
                    ? t("cashMovement.submitOut", { amount: formatMoney(amount ?? "0.00") })
                    : t("cashMovement.submitIn", { amount: formatMoney(amount ?? "0.00") })}
                  <Kbd keys="Enter" inverted />
                </Button>
              ) : null}
            </>
          )}
        </div>
        <aside className="flex flex-col gap-3 rounded-2xl border border-border bg-background p-4">
          <h2 className="text-[16px] font-extrabold">{t("cashMovement.cashInDrawer")}</h2>
          {snapshot ? (
            <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-[14px]">
              <dt>{t("cashMovement.calc.opening")}</dt>
              <dd className="text-right tabular-nums">+{formatMoney(snapshot.totals.openingCash)}</dd>
              <dt>{t("cashMovement.calc.cashSales")}</dt>
              <dd className="text-right tabular-nums">+{formatMoney(snapshot.totals.cashSales)}</dd>
              <dt>{t("cashMovement.calc.cashReturns")}</dt>
              <dd className="text-right tabular-nums">−{formatMoney(snapshot.totals.cashReturns)}</dd>
              <dt>{t("cashMovement.calc.debtCashIn")}</dt>
              <dd className="text-right tabular-nums" data-testid="debt-cash-in">
                +{formatMoney(snapshot.totals.debtCashIn)}
              </dd>
              <dt>{t("cashMovement.calc.in")}</dt>
              <dd className="text-right tabular-nums">+{formatMoney(snapshot.totals.cashIn)}</dd>
              <dt>{t("cashMovement.calc.out")}</dt>
              <dd className="text-right tabular-nums">−{formatMoney(snapshot.totals.cashOut)}</dd>
              <dt className="font-extrabold">{t("cashMovement.calc.now")}</dt>
              <dd className="text-right font-extrabold tabular-nums" data-testid="cash-now">
                {nowCash ? formatMoney(nowCash) : "—"}
              </dd>
              <dt className="font-extrabold">{t("cashMovement.calc.after")}</dt>
              <dd className="text-right font-extrabold tabular-nums">{after ? formatMoney(after) : "—"}</dd>
            </dl>
          ) : null}
          <h3 className="pt-2 text-[14px] font-extrabold">{t("cashMovement.moves")}</h3>
          <ul className="flex flex-col gap-2" data-testid="movement-list">
            {(snapshot?.totals.movements ?? []).map((m) => (
              <li
                key={m.id}
                className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2"
              >
                <span className="flex flex-col">
                  <span className="text-[13px] font-bold">
                    {t(`cashMovement.reasons.${m.reason}`, { defaultValue: m.reason })}
                  </span>
                  <span className="text-[12px] text-foreground-secondary">
                    {formatDateTime(m.createdAt)}
                    {m.comment ? ` · ${m.comment}` : ""}
                  </span>
                </span>
                <span
                  className={cn(
                    "tabular-nums font-bold",
                    m.direction === "out" ? "text-destructive-strong" : "text-success-strong",
                  )}
                >
                  {m.direction === "out" ? "−" : "+"}
                  {formatMoney(m.amount)}
                </span>
              </li>
            ))}
          </ul>
          <p className="text-[12px] text-foreground-secondary">{t("cashMovement.notFiscal")}</p>
        </aside>
      </div>
    </PosScreen>
  );
}

export const CashMovement = {
  route: "cash-movement",
  titleKey: "pos:cashMovement.title",
  Page: CashMovementPage,
} as const;

/**
 * POS-13 — Qarz daftari (tezkor) (07, route /pos/debts, F7; mockup Pos13Qarz.dc.html). Three columns:
 * - left: search (name / phone, local — works offline), debtors count + total, the debtor list with chips
 *   («muddati o'tgan» / «va'da bugun»);
 * - middle: the chosen customer — debt, limit · free, promise date, «Tezkor qarz yozish» (POS-02 with the
 *   customer chosen → NASIYA, a new debt is always a sale with goods), the paper-book rows (online: the server
 *   ledger; offline: the open documents on this device);
 * - right: «To'lov qabul qilish» — amount, method (naqd / karta / UzQR; bank only in BO-06), «To'lov yopadigan
 *   sotuvlar» (the device allocation, full / partial · rest), debt after the payment, new promise date, «To'langan
 *   N so'mga fiskal chek chiqariladi», «To'lovni qabul qilish» (Enter) → `debt_payment.created` (offline too) →
 *   the `debt_settlement` receipt is printed.
 * Online a payment above the debt is refused (qaror #45, the change is given in cash); offline it is accepted
 * with a warning (the excess → Kt 6310, resolved in BO-06, qaror #67). 48 h fiscal block → viewing only.
 */
import { useUnit } from "effector-react";
import { BookUser, CircleAlert, CreditCard, Printer, ReceiptText, Search, WifiOff } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { newAttemptId } from "@shared/lib/card-terminal";
import { formatDate, formatMoney, formatPhone } from "@shared/lib/format";
import { addMoney, compareMoney, isMoney, money, type Money } from "@shared/lib/money";
import type { ReceiptDoc } from "@shared/lib/receipt";
import {
  $fiscalLadder,
  customerDebts,
  customers,
  outboxChanged,
  pullApplied,
  settings,
  type CustomerDebtView,
} from "@shared/offline";
import type { DebtLedgerOut } from "@shared/models";
import { $isOnline } from "@shared/state/network";
import {
  Banner,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  EmptyState,
  Icon,
  Input,
  Kbd,
  Label,
  MoneyInput,
  NoPermissionState,
  StatusChip,
  cn,
} from "@shared/ui";

import { customerSet } from "#/entities/receipt-draft/index.ts";
import {
  $posCashier,
  $posDevice,
  $posShift,
  PosScreen,
  cashierCan,
  posKeysLocked,
} from "#/entities/pos-session/index.ts";
import {
  $cardPanelLocked,
  $cardPaymentOutcome,
  CardPayment,
  cardOutcomeConsumed,
  cardPaymentClosed,
  cardPaymentStarted,
} from "#/features/card-payment/index.ts";
import { printDoc } from "#/features/ops-print/index.ts";
import { tashkentDate } from "#/shared/lib/dates.ts";
import { dyn, errorText } from "#/shared/lib/i18n-errors.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";
import { ReceiptPreview } from "#/shared/ui/ReceiptPreview.tsx";

import {
  DEBT_PAY_METHODS,
  DebtPaymentError,
  acceptDebtPaymentFx,
  debtReceiptDoc,
  loadLineInfoFx,
  loadRecentLedgerFx,
  planPayment,
  type AcceptInput,
  type FinishedDebtPayment,
  type LineInfo,
  type PayMethodKey,
} from "../../model/index.ts";
import { PROMISE_DAYS, PromiseDatePicker } from "../PromiseDatePicker.tsx";

const SALE_PATH = "/pos/sale";

function addDays(days: number): string {
  return tashkentDate(new Date(Date.now() + days * 86_400_000));
}

function chipOf(view: CustomerDebtView, today: string): "overdue" | "today" | null {
  const date = view.customer.debt_due_date ?? null;
  if (date === today) return "today";
  if (date && date < today) return "overdue";
  return view.openDocs.some((d) => (d.due_date ?? "9999") < today) ? "overdue" : null;
}

interface StoreInfo {
  name: string;
  stir: string | null;
  branchName: string | null;
  registerName: string | null;
}

const obj = (v: unknown): Record<string, unknown> =>
  v && typeof v === "object" ? (v as Record<string, unknown>) : {};
const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);

function useStoreInfo(): StoreInfo {
  const [info, setInfo] = useState<StoreInfo>({ name: "", stir: null, branchName: null, registerName: null });
  useEffect(() => {
    void settings.get().then((s) => {
      const raw = s.raw ?? {};
      setInfo({
        name: str(obj(raw.tenant).name) ?? "",
        stir: str(obj(raw.tenant).stir),
        branchName: str(obj(raw.branch).name),
        registerName: str(obj(raw.cash_register).name),
      });
    });
  }, []);
  return info;
}

/** Re-read on a pull (balances, open documents) and on outbox changes (accepted / rejected events). */
function useRefreshTick(): number {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const a = pullApplied.watch(() => setTick((n) => n + 1));
    const b = outboxChanged.watch(() => setTick((n) => n + 1));
    return () => {
      a();
      b();
    };
  }, []);
  return tick;
}

function DebtBookPage() {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const navigate = useNavigate();
  const [cashier, device, shift, online, ladder, cardOutcome, cardLocked, pending] = useUnit([
    $posCashier,
    $posDevice,
    $posShift,
    $isOnline,
    $fiscalLadder,
    $cardPaymentOutcome,
    $cardPanelLocked,
    acceptDebtPaymentFx.pending,
  ]);
  const canView = cashierCan(cashier, "debts.create") || cashierCan(cashier, "debts.payment.accept");
  const canPay = cashierCan(cashier, "debts.payment.accept");
  const canWrite = cashierCan(cashier, "debts.create");
  const today = tashkentDate();
  const store = useStoreInfo();
  const tick = useRefreshTick();

  // --- left: debtors / search ------------------------------------------------------------------------
  const [query, setQuery] = useState("");
  const [list, setList] = useState<CustomerDebtView[]>([]);
  const [debtors, setDebtors] = useState<CustomerDebtView[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    void customerDebts.debtors().then((d) => alive && setDebtors(d));
    return () => {
      alive = false;
    };
  }, [tick]);
  useEffect(() => {
    let alive = true;
    if (!query.trim()) return;
    void customers.search(query, { limit: 30 }).then(async (rows) => {
      const views = await Promise.all(rows.map((r) => customerDebts.view(r.id)));
      if (alive) setList(views.filter((v): v is CustomerDebtView => v !== undefined));
    });
    return () => {
      alive = false;
    };
  }, [query, debtors]);
  const shown = query.trim() ? list : debtors;
  const total = useMemo(() => addMoney("0.00" as Money, ...debtors.map((v) => v.balance)), [debtors]);

  // --- middle: the customer ------------------------------------------------------------------------------
  const [loadedView, setView] = useState<CustomerDebtView | null>(null);
  const [loadedLedger, setLedger] = useState<DebtLedgerOut | null>(null);
  const view = loadedView && loadedView.customer.id === selectedId ? loadedView : null;
  const ledger = online && loadedLedger && loadedLedger.counterparty.id === selectedId ? loadedLedger : null;
  useEffect(() => {
    let alive = true;
    if (!selectedId) return;
    void customerDebts.view(selectedId).then((v) => alive && setView(v ?? null));
    return () => {
      alive = false;
    };
  }, [selectedId, tick]);
  useEffect(() => {
    let alive = true;
    if (!selectedId || !online) return;
    loadRecentLedgerFx(selectedId)
      .then((l) => alive && setLedger(l))
      .catch(() => alive && setLedger(null));
    return () => {
      alive = false;
    };
  }, [selectedId, online, tick]);

  // --- right: payment --------------------------------------------------------------------------------------
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<PayMethodKey>("cash");
  const [cashReceived, setCashReceived] = useState("");
  const [uzqrRef, setUzqrRef] = useState("");
  const [promiseDate, setPromiseDate] = useState("");
  const [cardEventId, setCardEventId] = useState<string | null>(null);
  const [error, setError] = useState<{ code: string; params: Record<string, unknown> } | null>(null);
  const [done, setDone] = useState<{
    payment: FinishedDebtPayment;
    doc: ReceiptDoc;
    printed: "ok" | "error" | "printing";
  } | null>(null);
  const [uzqrConfirm, setUzqrConfirm] = useState(false);
  const lineInfo = useRef<Record<string, LineInfo>>({});

  const plan = planPayment(view, amount, online);
  const blocked = ladder.level === "blocked48";
  const cardPart =
    method === "card" && cardOutcome && plan.amount && compareMoney(cardOutcome.amount, plan.amount) === 0
      ? cardOutcome
      : null;
  // the received cash defaults to the amount (the field shows it until the cashier types more)
  const received = cashReceived || plan.amount || "";
  const cashOk =
    method !== "cash" ||
    (isMoney(received || "x") && plan.amount !== null && compareMoney(money(received), plan.amount) >= 0);
  const ready =
    canPay &&
    !!view &&
    !!shift &&
    !blocked &&
    plan.error === null &&
    !pending &&
    cashOk &&
    (method !== "card" || cardPart !== null) &&
    (method !== "uzqr" || online);

  const resetPayment = useCallback(() => {
    setAmount("");
    setCashReceived("");
    setUzqrRef("");
    setPromiseDate("");
    setCardEventId(null);
    setError(null);
  }, []);
  const select = (id: string) => {
    if (cardLocked) return;
    cardPaymentClosed();
    setSelectedId(id);
    resetPayment();
  };

  useEffect(() => {
    if (view) void loadLineInfoFx(view).then((i) => (lineInfo.current = i));
  }, [view]);
  // leaving the screen with an idle / failed card attempt resets the card flow (UX-01 rules inside)
  useEffect(() => () => cardPaymentClosed(), []);
  // WEB-02: F-keys of the POS shell (F6/F8/F9/F12 …) must not leave POS-13 while a card attempt is pending,
  // as on POS-05 — leaving would orphan the terminal attempt (UX-01)
  useEffect(() => {
    posKeysLocked(cardLocked);
    return () => {
      posKeysLocked(false);
    };
  }, [cardLocked]);

  const accept = useCallback(async () => {
    if (!ready || !view) return;
    setError(null);
    const card: AcceptInput["card"] = cardPart
      ? cardPart.mode === "integrated"
        ? {
            mode: "integrated",
            attemptId: cardPart.attemptId,
            cardResult: cardPart.cardResult as unknown as Record<string, unknown>,
          }
        : {
            mode: "manual",
            manualReason: cardPart.manualReason,
            approval: cardPart.approval as unknown as Record<string, unknown> | null,
            attemptId: cardPart.attemptId,
          }
      : null;
    try {
      const payment = await acceptDebtPaymentFx({
        view,
        plan,
        method,
        device: device ? { branchId: device.branchId, cashRegisterId: device.cashRegisterId } : null,
        shiftId: shift?.id ?? null,
        cashier: cashier ? { userId: cashier.userId, permissions: cashier.permissions } : null,
        online,
        offlineSince: online ? null : new Date().toISOString(),
        fiscalBlocked: blocked,
        promiseDate: promiseDate || null,
        comment: null,
        cashReceived: method === "cash" ? money(received) : null,
        card,
        ...(cardEventId ? { clientEventId: cardEventId } : {}),
        terminalRef: method === "uzqr" ? uzqrRef : null,
      });
      if (card) cardOutcomeConsumed();
      const doc = debtReceiptDoc(
        payment,
        lineInfo.current,
        store,
        cashier?.fullName ?? "",
        shift?.shift_no ?? null,
      );
      setDone({ payment, doc, printed: "printing" });
      resetPayment();
      const out = await printDoc(doc);
      setDone((d) => (d ? { ...d, printed: out.ok ? "ok" : "error" } : d));
    } catch (e) {
      setError(
        e instanceof DebtPaymentError
          ? { code: e.code, params: e.params }
          : { code: "INTERNAL_ERROR", params: {} },
      );
    }
  }, [
    ready,
    view,
    plan,
    method,
    device,
    shift,
    cashier,
    online,
    blocked,
    promiseDate,
    received,
    cardPart,
    cardEventId,
    uzqrRef,
    store,
    resetPayment,
  ]);

  // an approved integrated card finishes the payment by itself (card approval → receipt → event, 07 POS-03)
  const autoFinished = useRef<string | null>(null);
  useEffect(() => {
    if (cardPart?.mode !== "integrated" || autoFinished.current === cardPart.attemptId) return;
    autoFinished.current = cardPart.attemptId;
    void accept();
  }, [cardPart, accept]);

  const back = () => {
    if (cardLocked || cardOutcome?.mode === "integrated") return;
    void navigate(SALE_PATH);
  };
  useHotkeys(
    [
      { key: "Escape", handler: () => (done ? setDone(null) : back()) },
      {
        key: "Enter",
        allowInInput: true,
        handler: () => {
          if (done) {
            setDone(null);
            return true;
          }
          if (!ready) return false;
          if (method === "uzqr") setUzqrConfirm(true);
          else void accept();
          return true;
        },
      },
    ],
    { enabled: !uzqrConfirm },
  );

  if (cashier && !canView) return <NoPermissionState />;

  const startCard = () => {
    if (!plan.amount || !device?.cashRegisterId) return;
    const id = newAttemptId();
    setCardEventId(id);
    cardPaymentStarted({
      amount: plan.amount,
      clientEventId: id,
      cashRegisterId: device.cashRegisterId,
      shiftId: shift?.id ?? null,
    });
  };
  const chip = (v: CustomerDebtView) => chipOf(v, today);

  return (
    <PosScreen
      title={t("debts.bookTitle")}
      hotkey="F7"
      backLabel={t("payment.back")}
      onBack={back}
      backDisabled={cardLocked}
      testId="debt-book"
    >
      <div className="grid h-full min-h-0 grid-cols-1 gap-4 lg:grid-cols-[300px_minmax(0,1fr)_380px]">
        {/* left */}
        <section className="flex min-h-0 flex-col gap-3">
          <div className="relative">
            <Icon
              as={Search}
              size="md"
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              autoFocus
              className="h-12 pl-10"
              maxLength={64}
              placeholder={t("debts.searchPlaceholder")}
              value={query}
              data-testid="debt-search"
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && shown[0]) {
                  e.preventDefault();
                  select(shown[0].customer.id);
                }
              }}
            />
          </div>
          <p className="text-[13px] text-foreground-secondary" data-testid="debtors-total">
            {t("debts.debtorsTotal", { n: debtors.length, amount: formatMoney(total) })}
          </p>
          <ul className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto" aria-label={t("debts.debtors")}>
            {shown.length === 0 ? (
              <li className="py-6 text-center text-muted-foreground">{t("debts.noDebtors")}</li>
            ) : null}
            {shown.map((v) => {
              const c = chip(v);
              return (
                <li key={v.customer.id}>
                  <button
                    type="button"
                    data-testid="debtor-row"
                    aria-pressed={v.customer.id === selectedId}
                    onClick={() => select(v.customer.id)}
                    className="flex min-h-14 w-full flex-col rounded-xl border border-border px-3 py-2 text-left hover:border-primary aria-pressed:border-primary aria-pressed:bg-primary-soft"
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate font-bold">{v.customer.name}</span>
                      <span className="font-extrabold tabular-nums">
                        {formatMoney(v.balance, { withCurrency: false })}
                      </span>
                    </span>
                    <span className="flex items-center justify-between gap-2 text-[12px] text-muted-foreground">
                      <span>{v.customer.phone ? formatPhone(v.customer.phone) : ""}</span>
                      {c ? (
                        <StatusChip tone={c === "overdue" ? "destructive" : "warning"}>
                          {t(`debts.chip.${c}`)}
                        </StatusChip>
                      ) : v.creditLimit ? (
                        <span>
                          {t("debts.limitShort", {
                            amount: formatMoney(v.creditLimit, { withCurrency: false }),
                          })}
                        </span>
                      ) : null}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>

        {/* middle */}
        <section className="flex min-h-0 flex-col gap-3 overflow-y-auto">
          {!view ? (
            <EmptyState icon={BookUser} title={t("debts.pickTitle")} description={t("debts.pickHint")} />
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-[20px] font-extrabold" data-testid="book-name">
                  {view.customer.name}
                </h2>
                <span className="text-[13px] text-muted-foreground">
                  {view.customer.phone ? formatPhone(view.customer.phone) : ""}
                </span>
                {view.local ? <StatusChip tone="info">{t("debts.notSynced")}</StatusChip> : null}
                <div className="grow" />
                {canWrite ? (
                  <Button
                    size="pos"
                    variant="warning"
                    data-testid="quick-debt"
                    onClick={() => {
                      customerSet(view.customer.id);
                      void navigate(SALE_PATH);
                    }}
                  >
                    {t("debts.quickDebt")}
                  </Button>
                ) : null}
              </div>
              <dl className="grid grid-cols-3 gap-2 text-[13px]">
                <div className="flex flex-col rounded-xl bg-muted px-3 py-2">
                  <dt className="text-muted-foreground">{t("debts.current")}</dt>
                  <dd className="text-[22px] font-extrabold tabular-nums" data-testid="book-balance">
                    {formatMoney(view.balance, { withCurrency: false })}
                  </dd>
                </div>
                <div className="flex flex-col rounded-xl bg-muted px-3 py-2">
                  <dt className="text-muted-foreground">{t("debts.limitFree")}</dt>
                  <dd className="text-[15px] font-bold">
                    {view.creditLimit
                      ? `${formatMoney(view.available ?? "0.00", { withCurrency: false })} / ${formatMoney(view.creditLimit, { withCurrency: false })}`
                      : t("debts.noLimitShort")}
                  </dd>
                </div>
                <div className="flex flex-col rounded-xl bg-muted px-3 py-2">
                  <dt className="text-muted-foreground">{t("debts.promise")}</dt>
                  <dd className="text-[15px] font-bold">
                    {view.customer.debt_due_date ? formatDate(view.customer.debt_due_date) : "—"}
                  </dd>
                </div>
              </dl>
              {compareMoney(view.pendingPayments, "0.00" as Money) > 0 ? (
                <Banner tone="info" icon={CircleAlert}>
                  {t("debts.pendingPayments", { amount: formatMoney(view.pendingPayments) })}
                </Banner>
              ) : null}
              <p className="text-[12px] text-foreground-secondary">{t("debts.quickDebtHint")}</p>
              <h3 className="text-[15px] font-extrabold">{t("debts.ledgerTitle")}</h3>
              {ledger ? (
                <table className="w-full text-[13px]" data-testid="book-ledger">
                  <thead className="text-left text-muted-foreground">
                    <tr>
                      <th className="py-1">{t("debts.col.date")}</th>
                      <th>{t("debts.col.doc")}</th>
                      <th className="text-right">{t("debts.col.amount")}</th>
                      <th className="text-right">{t("debts.col.balance")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ledger.entries.map((e) => (
                      <tr key={e.id} className="border-t border-border">
                        <td className="py-1.5 tabular-nums">{e.doc_date ? formatDate(e.doc_date) : "—"}</td>
                        <td>
                          <span className="font-bold">
                            {t(`debts.kind.${e.kind}`)}
                            {e.number ? ` ${e.number}` : ""}
                          </span>
                          {e.products.length ? (
                            <span className="block text-[12px] text-muted-foreground">
                              {e.products.map((p) => p.name).join(", ")}
                            </span>
                          ) : null}
                        </td>
                        <td
                          className={cn(
                            "text-right font-bold tabular-nums",
                            e.amount.startsWith("-") ? "text-success-strong" : "text-destructive-strong",
                          )}
                        >
                          {e.amount.startsWith("-") ? "" : "+"}
                          {formatMoney(e.amount, { withCurrency: false })}
                        </td>
                        <td className="text-right tabular-nums">
                          {formatMoney(e.running_balance, { withCurrency: false })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <ul className="flex flex-col gap-1 text-[13px]" data-testid="book-open-docs">
                  {view.openDocs.map((d) => (
                    <li
                      key={`${d.doc_type}:${d.doc_id}`}
                      className="flex justify-between border-t border-border py-1.5"
                    >
                      <span>
                        <span className="font-bold">
                          {t(`debts.doc.${d.doc_type}`)} {d.number ?? ""}
                        </span>{" "}
                        <span className="text-muted-foreground">
                          {d.doc_date ? formatDate(d.doc_date) : ""}
                        </span>
                        {d.local ? (
                          <span className="ml-1 text-muted-foreground">· {t("debts.notSynced")}</span>
                        ) : null}
                      </span>
                      <span className="font-bold tabular-nums">
                        {formatMoney(d.open_amount, { withCurrency: false })}
                      </span>
                    </li>
                  ))}
                  {!online ? (
                    <li className="pt-1 text-[12px] text-muted-foreground">{t("debts.offlineLedger")}</li>
                  ) : null}
                </ul>
              )}
            </>
          )}
        </section>

        {/* right */}
        <section
          className="flex min-h-0 flex-col gap-3 overflow-y-auto rounded-2xl bg-background p-4"
          data-testid="pay-panel"
        >
          <h3 className="text-[16px] font-extrabold">{t("debts.payTitle")}</h3>
          {!online ? (
            <Banner tone="warning" icon={WifiOff}>
              {t("debts.offlinePay")}
            </Banner>
          ) : null}
          {blocked ? (
            <Banner tone="destructive" icon={CircleAlert} live="assertive">
              {t("fiscalLadder.blockedBanner")}
            </Banner>
          ) : null}
          {!shift ? (
            <Banner tone="warning" icon={CircleAlert}>
              {t("sale.noShift")}
            </Banner>
          ) : null}
          {!canPay ? (
            <Banner tone="info" icon={CircleAlert}>
              {t("debts.noPayRight")}
            </Banner>
          ) : null}
          <Label htmlFor="debt-amount">{t("debts.amount")}</Label>
          <MoneyInput
            id="debt-amount"
            className="h-14 text-[22px] font-extrabold"
            value={amount}
            onChange={(v) => {
              setAmount(v);
              setError(null);
            }}
            disabled={!view || !canPay || cardLocked || cardPart !== null}
            data-testid="debt-amount"
          />
          {view ? (
            <p className="text-[12px] text-muted-foreground">
              {t("debts.amountHint", { amount: formatMoney(view.payable) })}
            </p>
          ) : null}
          <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label={t("payment.methodsLabel")}>
            {DEBT_PAY_METHODS.map((m) => (
              <Button
                key={m}
                size="pos"
                role="radio"
                aria-checked={method === m}
                variant={method === m ? "default" : "secondary"}
                disabled={(m === "uzqr" && !online) || cardLocked || cardPart !== null}
                data-testid={`pay-method-${m}`}
                onClick={() => {
                  setMethod(m);
                  setError(null);
                  if (m !== "card") cardPaymentClosed();
                }}
              >
                {t(`payment.method.${m}`)}
              </Button>
            ))}
          </div>
          {method === "cash" && plan.amount ? (
            <div className="flex flex-col gap-1">
              <Label htmlFor="debt-cash">{t("payment.cashReceived")}</Label>
              <MoneyInput
                id="debt-cash"
                className="h-12"
                value={cashReceived || plan.amount}
                onChange={setCashReceived}
                data-testid="debt-cash"
              />
            </div>
          ) : null}
          {method === "uzqr" ? (
            <div className="flex flex-col gap-1">
              <Label htmlFor="debt-uzqr">{t("payment.uzqrRef")}</Label>
              <Input
                id="debt-uzqr"
                className="h-12"
                maxLength={40}
                value={uzqrRef}
                onChange={(e) => setUzqrRef(e.target.value)}
              />
            </div>
          ) : null}
          {method === "card" ? (
            <div className="flex flex-col gap-2">
              {cardEventId === null ? (
                <Button
                  size="pos"
                  variant="secondary"
                  disabled={!plan.amount || plan.error !== null || !shift || blocked}
                  onClick={startCard}
                  data-testid="debt-card-start"
                >
                  <Icon as={CreditCard} size="md" />
                  {t("payment.sendToTerminal")}
                </Button>
              ) : (
                <CardPayment />
              )}
            </div>
          ) : null}

          {plan.rows.length > 0 ? (
            <div className="flex flex-col gap-1" data-testid="allocation">
              <h4 className="text-[13px] font-extrabold">{t("debts.closes")}</h4>
              <ul className="flex flex-col gap-1 text-[13px]">
                {plan.rows.map((r) => (
                  <li
                    key={`${r.docType}:${r.docId}`}
                    className="flex items-center justify-between gap-2 rounded-lg bg-muted px-3 py-1.5"
                    data-testid="allocation-row"
                  >
                    <span className="min-w-0">
                      <span className="font-bold">
                        {t(`debts.doc.${r.docType}`)} {r.number ?? ""}
                      </span>{" "}
                      <span className="text-muted-foreground">{r.docDate ? formatDate(r.docDate) : ""}</span>
                    </span>
                    <span className="text-right">
                      <span className="block font-bold tabular-nums">
                        {formatMoney(r.amount, { withCurrency: false })}
                      </span>
                      <span
                        className="block text-[12px] text-muted-foreground"
                        data-testid="allocation-state"
                      >
                        {r.closes
                          ? t("debts.closesFull")
                          : t("debts.closesPart", { amount: formatMoney(r.left, { withCurrency: false }) })}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {plan.error === "debt_payment_exceeds_balance" ? (
            <Banner tone="destructive" icon={CircleAlert}>
              <span data-testid="debt-exceeds">
                {t("debts.exceedsOnline", { amount: formatMoney(view?.payable ?? "0.00") })}
              </span>
            </Banner>
          ) : null}
          {compareMoney(plan.overpay, "0.00" as Money) > 0 ? (
            <Banner tone="warning" icon={CircleAlert}>
              <span data-testid="debt-overpay">
                {t("debts.overpayOffline", { amount: formatMoney(plan.overpay) })}
              </span>
            </Banner>
          ) : null}
          {view ? (
            <div className="flex items-baseline justify-between rounded-xl bg-card px-3 py-2">
              <span className="text-[13px]">{t("debts.afterPayment")}</span>
              <span className="text-[20px] font-extrabold tabular-nums" data-testid="debt-after-payment">
                {formatMoney(plan.after)}
              </span>
            </div>
          ) : null}
          {view && compareMoney(plan.after, "0.00" as Money) > 0 && plan.amount ? (
            <div className="flex flex-col gap-1">
              <Label>{t("debts.newPromise")}</Label>
              <PromiseDatePicker
                value={promiseDate}
                today={today}
                label={t("debts.newPromise")}
                dayLabels={PROMISE_DAYS.map((n) => t("payment.dueDays", { n }))}
                dateFor={(n) => addDays(n)}
                onChange={(d) => setPromiseDate(d)}
              />
            </div>
          ) : null}
          {plan.amount && plan.error === null ? (
            <p className="flex items-center gap-2 text-[13px] text-foreground-secondary">
              <Icon as={ReceiptText} size="sm" />
              {t("debts.receiptNote", { amount: formatMoney(plan.amount) })}
            </p>
          ) : null}
          {error ? (
            <Banner tone="destructive" icon={CircleAlert} live="assertive">
              <span data-testid="debt-pay-error">{errorText(error.code, error.params)}</span>
            </Banner>
          ) : null}
          <div className="grow" />
          <Button
            size="pos-cta"
            className="w-full"
            disabled={!ready}
            data-testid="debt-accept"
            onClick={() => (method === "uzqr" ? setUzqrConfirm(true) : void accept())}
          >
            {t("debts.accept")}
            <Kbd keys="Enter" inverted />
          </Button>
        </section>
      </div>

      {uzqrConfirm && plan.amount ? (
        <Dialog open onOpenChange={(o) => !o && setUzqrConfirm(false)}>
          <DialogContent size="sm" role="alertdialog">
            <DialogHeader>
              <DialogTitle>{t("payment.uzqrConfirmTitle")}</DialogTitle>
              <DialogDescription>
                {t("payment.uzqrConfirmText", { amount: formatMoney(plan.amount) })}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button size="pos" variant="secondary" onClick={() => setUzqrConfirm(false)}>
                {t("sale.cancel")}
              </Button>
              <Button
                size="pos"
                onClick={() => {
                  setUzqrConfirm(false);
                  void accept();
                }}
              >
                {t("payment.uzqrConfirmYes")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      ) : null}

      {done ? (
        <Dialog open onOpenChange={(o) => !o && setDone(null)}>
          <DialogContent className="max-w-[860px]" data-testid="debt-receipt">
            <div className="flex flex-col gap-4 md:flex-row">
              <div className="flex min-w-0 flex-1 flex-col gap-3">
                <DialogTitle className="text-[22px] font-extrabold">{t("debts.paidTitle")}</DialogTitle>
                <DialogDescription>
                  {t("debts.paidText", {
                    name: done.payment.customerName,
                    amount: formatMoney(done.payment.amount),
                  })}
                </DialogDescription>
                {done.payment.change && compareMoney(done.payment.change, "0.00" as Money) > 0 ? (
                  <p className="text-[18px] font-extrabold">
                    {t("payment.change")}: {formatMoney(done.payment.change)}
                  </p>
                ) : null}
                {compareMoney(done.payment.overpay, "0.00" as Money) > 0 ? (
                  <Banner tone="warning" icon={CircleAlert}>
                    {t("debts.overpayOffline", { amount: formatMoney(done.payment.overpay) })}
                  </Banner>
                ) : null}
                <p className="text-[13px] text-foreground-secondary" data-testid="debt-receipt-status">
                  {done.printed === "printing"
                    ? t("debts.printing")
                    : done.printed === "ok"
                      ? t("debts.printed")
                      : t("debts.printFailed")}
                </p>
                <p className="text-[12px] text-muted-foreground">
                  {done.payment.isOffline ? t("debts.fiscalOffline") : t("debts.fiscalPending")}
                </p>
                <div className="grow" />
                {done.printed === "error" ? (
                  <Button
                    size="pos"
                    variant="secondary"
                    onClick={() => {
                      setDone((d) => (d ? { ...d, printed: "printing" } : d));
                      void printDoc(done.doc).then((out) =>
                        setDone((d) => (d ? { ...d, printed: out.ok ? "ok" : "error" } : d)),
                      );
                    }}
                  >
                    <Icon as={Printer} size="md" />
                    {t("debts.printAgain")}
                  </Button>
                ) : null}
                <Button size="pos-cta" onClick={() => setDone(null)} data-testid="debt-receipt-close">
                  {t("debts.next")}
                  <Kbd keys="Enter" inverted />
                </Button>
              </div>
              <div className="max-h-[560px] overflow-y-auto">
                <ReceiptPreview doc={done.doc} />
              </div>
            </div>
          </DialogContent>
        </Dialog>
      ) : null}
    </PosScreen>
  );
}

export const DebtBook = {
  route: "debts",
  titleKey: "pos:debts.bookTitle",
  Page: DebtBookPage,
} as const;

import { useUnit } from "effector-react";
import {
  CircleAlert,
  CreditCard,
  Minus,
  PackageX,
  Plus,
  Printer,
  ScanLine,
  Search,
  Undo2,
  WifiOff,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { toApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { formatDateTime, formatMoney, formatQty } from "@shared/lib/format";
import { compareMoney, toDecimal, type Money } from "@shared/lib/money";
import {
  $fiscalLadder,
  catalog,
  enqueueEvent,
  isOfflineError,
  limits,
  outbox,
  prices,
  salesHistory,
} from "@shared/offline";
import { $isOnline } from "@shared/state/network";
import { $session } from "@shared/state/session";
import {
  Banner,
  Button,
  Checkbox,
  EmptyState,
  Icon,
  Input,
  Kbd,
  NoPermissionState,
  StatusChip,
  cn,
} from "@shared/ui";

import {
  $posCashier,
  $posDevice,
  $posShift,
  PosScreen,
  cashierCan,
  posKeysLocked,
  uuidv7,
} from "#/entities/pos-session/index.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";
import { defaultCardPaymentDeps, type CardPaymentDeps } from "#/features/card-payment/index.ts";
import { Ladder46Modal, needsLadder46 } from "#/features/fiscal-ladder/index.tsx";
import { ManagerApprovalDialog, type ApprovalRef } from "#/features/manager-approval/index.ts";
import { printDoc } from "#/features/ops-print/index.ts";

import {
  REASONS,
  REFUND_METHODS,
  defaultRefundMethod,
  findServerSale,
  fromLocalHistory,
  fromServerSale,
  lineKey,
  localReturnedQty,
  matchesQuery,
  qtyLeft,
  qtyValid,
  refundLine,
  returnApprovalNeed,
  returnPayload,
  returnTotals,
  returnsEscape,
  type ApprovalNeed,
  type LineState,
  type RefundCard,
  type RefundMethod,
  type ReturnReason,
  type ReturnSource,
  type SourceLine,
} from "../../model/index.ts";
import {
  cardRoute,
  manualPolicyNeed,
  manualReasonFor,
  runCardRefund,
  type CardRefundDeps,
  type CardRoute,
} from "../../model/card.ts";
import { returnReceiptDoc } from "../../model/receipt.ts";

const POS_SALE = "/pos/sale";

type StoredAttempt = Parameters<CardPaymentDeps["attempts"]["put"]>[0];
type RecordTxBody = Parameters<CardPaymentDeps["recordTx"]>[0];

function cardDeps(): CardRefundDeps {
  const card = defaultCardPaymentDeps();
  return {
    terminals: (id) => card.terminals(id),
    client: (t) => card.client(t),
    fallbackPolicy: () => card.fallbackPolicy(),
    putAttempt: (a) => card.attempts.put(a as unknown as StoredAttempt),
    updateAttempt: (id, patch) => card.attempts.update(id, patch),
    removeAttempt: (id) => card.attempts.remove(id),
    recordTx: (body) => card.recordTx(body as unknown as RecordTxBody),
    isOnline: () => card.isOnline(),
    now: () => new Date().toISOString(),
    sleep: (ms) => card.sleep(ms),
  };
}

type Phase = "idle" | "searching" | "card" | "saving" | "done";
type ReturnError =
  | "notFound"
  | "noDetails"
  | "searchFailed"
  | "noPrice"
  | "noLines"
  | "qty"
  | "reason"
  | "debtNeedsCustomer"
  | "markedOffline"
  | "fiscalBlocked"
  | "cardUnknown"
  | "cardDeclined"
  | "cardUnavailable"
  | "cardManualForbidden"
  | "saveFailed";

/** POS-05 — Mijozdan tovar qaytarish (07, route /pos/returns; maket Pos05Qaytarish.dc.html). */
function ReturnsPage() {
  const { t } = useTranslation("pos");
  const navigate = useNavigate();
  const [cashier, shift, device, online, ladder, session] = useUnit([
    $posCashier,
    $posShift,
    $posDevice,
    $isOnline,
    $fiscalLadder,
    $session,
  ]);
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<ReturnSource | null>(null);
  const [noReceipt, setNoReceipt] = useState(false);
  const [lines, setLines] = useState<SourceLine[]>([]);
  const [state, setState] = useState<LineState[]>([]);
  const [reason, setReason] = useState<ReturnReason | null>(null);
  const [method, setMethod] = useState<RefundMethod>("cash");
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<ReturnError | null>(null);
  const [need, setNeed] = useState<ApprovalNeed | null>(null);
  const [approval, setApproval] = useState<ApprovalRef | null>(null);
  const [manualCard, setManualCard] = useState<{ reason: string; needsApproval: boolean } | null>(null);
  const [done, setDone] = useState<{ amount: Money; doc: ReturnType<typeof returnReceiptDoc> } | null>(null);
  const [productQuery, setProductQuery] = useState("");
  // UX-07: at the 46 h level a return with a money part (a fiscal receipt) is acknowledged first
  const [ladderAsk, setLadderAsk] = useState(false);
  const [ladderAcked, setLadderAcked] = useState(false);
  const [products, setProducts] = useState<{ id: string; name: string; unit: string; marked: boolean }[]>([]);
  const searchRef = useRef<HTMLInputElement | null>(null);

  const back = useCallback(() => void navigate(POS_SALE), [navigate]);
  const totals = useMemo(() => returnTotals(source, lines, state), [source, lines, state]);

  useEffect(() => searchRef.current?.focus(), []);

  const reset = () => {
    setSource(null);
    setLines([]);
    setState([]);
    setReason(null);
    setNeed(null);
    setApproval(null);
    setManualCard(null);
    setError(null);
    setLadderAcked(false);
  };

  const load = (src: ReturnSource) => {
    setSource(src);
    setNoReceipt(false);
    setLines(src.lines);
    setState(
      src.lines.map((l, i) => ({
        key: lineKey(l, i),
        selected: false,
        qty: qtyLeft(l),
        restock: true,
        expired: false,
      })),
    );
    setMethod(defaultRefundMethod(src));
  };

  const search = async () => {
    const q = query.trim();
    if (!q) return;
    reset();
    setPhase("searching");
    try {
      const events = await outbox.list({ limit: 5000 });
      if (online) {
        try {
          const sale = await findServerSale(q);
          if (sale) {
            load(fromServerSale(sale, localReturnedQty(events, sale.id, true)));
            return;
          }
        } catch (e) {
          if (toApiError(e).code !== "NETWORK_ERROR") throw e;
        }
      }
      const rows = await salesHistory.list({ limit: 2000 });
      const row = rows.find((r) => r.kind === "sale" && matchesQuery(r, q));
      const src = row ? fromLocalHistory(row, localReturnedQty(events, row.id, false)) : null;
      if (src) load(src);
      else setError(row ? "noDetails" : "notFound");
    } catch {
      setError("searchFailed");
    } finally {
      setPhase("idle");
    }
  };

  const startNoReceipt = () => {
    reset();
    setNoReceipt(true);
    setMethod("cash");
  };

  useEffect(() => {
    if (!noReceipt) return;
    let alive = true;
    void catalog.search(productQuery, { limit: 12 }).then((rows) => {
      if (!alive) return;
      setProducts(
        rows.map((v) => ({
          id: v.product.id,
          name: v.product.name,
          unit: v.product.unit_code,
          marked: v.product.is_marked === true,
        })),
      );
    });
    return () => {
      alive = false;
    };
  }, [noReceipt, productQuery]);

  const addProduct = async (productId: string) => {
    const view = await catalog.get(productId);
    const price = view?.price ?? (await prices.current(productId));
    if (!view || !price) {
      setError("noPrice");
      return;
    }
    const line: SourceLine = {
      saleLineId: null,
      productId,
      name: view.product.name,
      unitCode: view.product.unit_code,
      fractional: view.product.is_weighed === true,
      qty: "999999.000",
      returnedQty: "0.000",
      price,
      lineTotal: "0.00" as Money,
      vatRate: view.product.vat_rate ?? "0.00",
      vatExemptionCode:
        typeof view.product.vat_exemption_code === "string" ? view.product.vat_exemption_code : null,
      markingCode: null,
    };
    setLines((l) => [...l, line]);
    setState((s) => [
      ...s,
      { key: `${productId}#${s.length}`, selected: true, qty: "1.000", restock: true, expired: false },
    ]);
  };

  const patch = (i: number, p: Partial<LineState>) =>
    setState((s) => s.map((x, j) => (j === i ? { ...x, ...p } : x)));
  const step = (i: number, delta: 1 | -1) => {
    const line = lines[i];
    const cur = state[i];
    if (!line || !cur) return;
    const n = cur.qty.split(".")[0] ?? "0";
    let v = 0;
    for (const ch of n) v = v * 10 + "0123456789".indexOf(ch);
    v = Math.max(1, v + delta);
    const candidate = `${v}.000`;
    if (qtyValid(line, candidate)) patch(i, { qty: candidate, selected: true });
  };

  const markedBlocked = !online && state.some((s, i) => s.selected && lines[i]?.markingCode);
  const fiscalBlocked = ladder.level === "blocked48" && compareMoney(totals.moneyPart, "0.00" as Money) > 0;
  const selectedOk = state.some((s, i) => s.selected && lines[i] && qtyValid(lines[i], s.qty));

  const validate = (): ReturnError | null => {
    if (!selectedOk) return "noLines";
    if (state.some((s, i) => s.selected && lines[i] && !qtyValid(lines[i], s.qty))) return "qty";
    if (!reason) return "reason";
    if (method === "debt_adjustment" && !source?.counterpartyId) return "debtNeedsCustomer";
    if (markedBlocked) return "markedOffline";
    if (fiscalBlocked) return "fiscalBlocked";
    return null;
  };

  const submit = async (acked = ladderAcked) => {
    if (!cashier || !shift || !device || phase !== "idle") return;
    const v = validate();
    setError(v);
    if (v) return;
    if (needsLadder46(ladder.level, compareMoney(totals.moneyPart, "0.00" as Money) > 0, acked)) {
      setLadderAsk(true);
      return;
    }
    const own = await limits.value(cashier.userId, "returns.approve");
    const n = returnApprovalNeed({
      cashier,
      ownLimit: own,
      amount: totals.amount,
      noReceipt,
      expired: totals.expired,
    });
    if (n.needed && !approval) {
      setNeed(n);
      return;
    }
    await afterApproval(approval);
  };

  const afterApproval = async (appr: ApprovalRef | null) => {
    if (!cashier || !shift || !device) return;
    setNeed(null);
    setApproval(appr);
    if (method === "card" && compareMoney(totals.moneyPart, "0.00" as Money) > 0) {
      const route = await cardRoute(cardDeps(), shift.cash_register_id);
      const policy = await cardDeps().fallbackPolicy();
      const debtSale = (source?.payments ?? []).some((p) => p.method === "debt");
      if (route.kind === "integrated" && !debtSale) {
        setPhase("card");
        const outcome = await runCardRefund(cardDeps(), {
          terminal: route.terminal,
          amount: totals.moneyPart,
          cashRegisterId: shift.cash_register_id,
          shiftId: shift.id,
          originalRrn: source?.payments.find((p) => p.method === "card")?.rrn ?? null,
        });
        setPhase("idle");
        if (outcome.status === "approved") {
          await save(
            appr,
            {
              card_entry_mode: "integrated",
              card_result: outcome.cardResult as unknown as Record<string, unknown>,
              card_type: null,
              card_mask: null,
              rrn: null,
              approval_code: null,
              card_scheme: null,
              manual_reason: null,
              card_manual_approval: null,
            },
            [outcome.attemptId],
          );
          return;
        }
        if (outcome.status === "unknown") {
          setError("cardUnknown");
          return;
        }
        offerManual(
          route,
          policy,
          manualReasonFor(route, outcome),
          outcome.status === "declined" ? "cardDeclined" : "cardUnavailable",
        );
        return;
      }
      offerManual(route, policy, manualReasonFor(route, null), null);
      return;
    }
    await save(appr, null, []);
  };

  const offerManual = (
    route: CardRoute,
    policy: "allow" | "manager_approval" | "forbid",
    reasonCode: string,
    err: ReturnError | null,
  ) => {
    const p = manualPolicyNeed(route, policy);
    if (p === "forbidden") {
      setError(err ?? "cardManualForbidden");
      return;
    }
    setError(err);
    setManualCard({ reason: reasonCode, needsApproval: p === "approval" });
  };

  const confirmManual = async (cardApproval: ApprovalRef | null) => {
    if (!manualCard) return;
    const rc: RefundCard = {
      card_entry_mode: "manual",
      card_result: null,
      card_type: null,
      card_mask: null,
      rrn: null,
      approval_code: null,
      card_scheme: null,
      manual_reason: manualCard.reason,
      card_manual_approval: cardApproval,
    };
    setManualCard(null);
    await save(approval, rc, []);
  };

  const save = async (appr: ApprovalRef | null, refundCard: RefundCard | null, attemptIds: string[]) => {
    if (!cashier || !shift || !device) return;
    setPhase("saving");
    try {
      const id = uuidv7();
      const payload = returnPayload({
        id,
        branchId: device.branchId,
        shiftId: shift.id,
        cashRegisterId: shift.cash_register_id,
        source,
        lines,
        state,
        reason: reason ?? "other",
        refundMethod: method,
        refundCard,
        approval: appr,
        isOffline: !online,
        counterpartyId: method === "debt_adjustment" ? (source?.counterpartyId ?? null) : null,
      });
      const withReceipt = compareMoney(totals.moneyPart, "0.00" as Money) > 0;
      const r = await enqueueEvent("return.created", payload, {
        actorUserId: cashier.userId,
        ...(withReceipt ? { receiptSeq: { cashRegisterId: shift.cash_register_id, shiftId: shift.id } } : {}),
        removeCardAttemptIds: attemptIds,
        history: {
          id,
          kind: "return",
          total: totals.amount,
          number: null,
          customer_id: source?.counterpartyId ?? null,
          summary: {
            sale_id: source?.saleId ?? null,
            refund_method: method,
            money_part: totals.moneyPart,
            card_entry_mode: refundCard?.card_entry_mode ?? null,
          },
        },
      });
      setDone({
        amount: totals.moneyPart,
        doc: returnReceiptDoc({
          storeName: session?.tenant.name ?? "",
          branchName: device.branchName,
          registerName: device.cashRegisterName,
          cashierName: cashier.fullName,
          shiftNo: shift.shift_no,
          receiptSeq: r.receiptSeq,
          number: source?.number ? `${source.number}/R` : `R-${r.seq}`,
          at: r.createdAt,
          lines,
          state,
          source,
          method,
          moneyPart: totals.moneyPart,
          total: totals.amount,
          vat: totals.vat,
        }),
      });
      setPhase("done");
    } catch (e) {
      setPhase("idle");
      setError(
        isOfflineError(e, "FISCAL_OFFLINE_48H_BLOCKED")
          ? "fiscalBlocked"
          : isOfflineError(e, "CARD_OUTCOME_UNKNOWN")
            ? "cardUnknown"
            : "saveFailed",
      );
    }
  };

  // UX-03: while the terminal may move money (card refund) Esc / back / global F-keys are held
  const keysLocked = phase === "card";
  useEffect(() => {
    posKeysLocked(keysLocked);
    return () => {
      posKeysLocked(false);
    };
  }, [keysLocked]);
  useHotkeys([
    // the approval form / done view handle Enter themselves; Enter also searches from the receipt field
    ...(phase === "done" || need?.needed || manualCard || keysLocked
      ? []
      : [
          {
            key: "Enter",
            allowInInput: true,
            handler: () => (!source && !noReceipt ? void search() : void submit()),
          },
        ]),
    {
      key: "Escape",
      handler: () => {
        const action = returnsEscape({
          cardPending: keysLocked,
          approvalOpen: need !== null,
          manualOpen: manualCard !== null,
        });
        if (action === "close_approval") setNeed(null);
        else if (action === "close_manual") setManualCard(null);
        else if (action === "back") back();
      },
    },
  ]);

  if (!cashier || !cashierCan(cashier, "returns.create")) {
    return (
      <PosScreen title={t("returns.title")} backLabel={t("returns.back")} onBack={back}>
        <NoPermissionState />
      </PosScreen>
    );
  }
  if (!shift || !device) {
    return (
      <PosScreen title={t("returns.title")} backLabel={t("returns.back")} onBack={back}>
        <EmptyState icon={Undo2} title={t("cashMovement.noShift")} />
      </PosScreen>
    );
  }

  if (phase === "done" && done) {
    return (
      <PosScreen
        testId="pos-returns-done"
        title={t("returns.title")}
        backLabel={t("returns.back")}
        onBack={back}
      >
        <div className="flex flex-col items-center gap-4 py-10">
          <Banner tone="success" icon={Undo2} live="polite">
            <span data-testid="return-done">{t("returns.done", { amount: formatMoney(done.amount) })}</span>
          </Banner>
          <div className="flex gap-3">
            <Button size="pos" variant="secondary" onClick={() => void printDoc(done.doc)}>
              <Icon as={Printer} size="md" />
              {t("returns.print")}
            </Button>
            <Button
              size="pos"
              onClick={() => {
                reset();
                setDone(null);
                setQuery("");
                setPhase("idle");
              }}
            >
              {t("returns.next")}
            </Button>
          </div>
        </div>
      </PosScreen>
    );
  }

  const approvalReason = need?.needed
    ? t(`returns.approvalReasons.${need.reason}`, { amount: formatMoney(totals.amount) })
    : "";

  return (
    <PosScreen
      testId="pos-returns"
      title={t("returns.title")}
      hotkey="F6"
      backLabel={t("returns.back")}
      onBack={back}

      backDisabled={keysLocked}
    >
      <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        <div className="flex flex-col gap-4">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void search();
            }}
          >
            <Input
              ref={searchRef}
              value={query}
              maxLength={40}
              placeholder={t("returns.searchPlaceholder")}
              aria-label={t("returns.search")}
              data-testid="receipt-query"
              onChange={(e) => setQuery(e.target.value)}
              className="h-14 text-[17px]"
            />
            <Button type="submit" size="pos" disabled={phase === "searching"} data-testid="receipt-search">
              <Icon as={Search} size="md" />
              {t("returns.searchButton")}
              <Kbd keys="Enter" inverted />
            </Button>
            <Button variant="secondary" size="pos" onClick={startNoReceipt} data-testid="no-receipt">
              <Icon as={PackageX} size="md" />
              {t("returns.noReceipt")}
            </Button>
          </form>

          {error === "notFound" || error === "noDetails" ? (
            <EmptyState
              icon={ScanLine}
              title={t(`returns.errors.${error}`)}
              description={t("returns.notFoundHint")}
            />
          ) : null}

          {source ? (
            <div
              className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-background px-4 py-3"
              data-testid="receipt-card"
            >
              <span className="text-[16px] font-extrabold">
                {t("returns.receipt", { number: source.number ?? "—" })}
              </span>
              <span className="text-[13px] text-foreground-secondary">
                {formatDateTime(source.createdAt)} ·{" "}
                {source.payments
                  .map((p) => t(`returns.methods.${p.method}`, { defaultValue: p.method }))
                  .join(", ")}
              </span>
              <StatusChip tone={source.origin === "server" ? "success" : "warning"}>
                {source.origin === "server" ? t("returns.fromServer") : t("returns.fromLocal")}
              </StatusChip>
            </div>
          ) : null}

          {noReceipt ? (
            <div
              className="flex flex-col gap-2 rounded-xl border border-warning-border bg-warning-soft/40 p-3"
              data-testid="no-receipt-panel"
            >
              <span className="text-[14px] font-bold">{t("returns.noReceiptHint")}</span>
              <Input
                value={productQuery}
                onChange={(e) => setProductQuery(e.target.value)}
                placeholder={t("returns.productSearch")}
                data-testid="product-query"
              />
              <div className="flex flex-wrap gap-2">
                {products.map((p) => (
                  <Button
                    key={p.id}
                    variant="secondary"
                    size="sm"
                    disabled={p.marked}
                    title={p.marked ? t("returns.markedNoReceipt") : undefined}
                    onClick={() => void addProduct(p.id)}
                  >
                    {p.name}
                  </Button>
                ))}
              </div>
            </div>
          ) : null}

          {lines.length > 0 ? (
            <table className="w-full text-[14px]" data-testid="return-lines">
              <thead className="text-left text-[12px] text-foreground-secondary">
                <tr>
                  <th className="w-10" />
                  <th>{t("returns.cols.product")}</th>
                  {source ? <th className="text-right">{t("returns.cols.sold")}</th> : null}
                  <th className="text-center">{t("returns.cols.returnQty")}</th>
                  <th className="text-right">{t("returns.cols.sum")}</th>
                  <th className="text-center">{t("returns.cols.restock")}</th>
                  <th className="text-center">{t("returns.cols.expired")}</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line, i) => {
                  const s = state[i];
                  if (!s) return null;
                  const markedOffline = !online && line.markingCode !== null;
                  const left = qtyLeft(line);
                  const none = source !== null && toDecimal(left).lessThanOrEqualTo(0);
                  const valid = qtyValid(line, s.qty);
                  return (
                    <tr
                      key={s.key}
                      className={cn("border-t border-border", markedOffline || none ? "opacity-60" : "")}
                      data-testid={`return-line-${i}`}
                    >
                      <td className="py-2">
                        <Checkbox
                          checked={s.selected}
                          disabled={markedOffline || none}
                          aria-label={t("returns.select", { name: line.name })}
                          onCheckedChange={(v) => patch(i, { selected: v === true })}
                        />
                      </td>
                      <td>
                        <span className="flex flex-col">
                          <span className="font-bold">{line.name}</span>
                          {line.markingCode ? (
                            <span
                              className={cn(
                                "text-[12px]",
                                markedOffline ? "text-destructive-strong" : "text-foreground-secondary",
                              )}
                            >
                              {markedOffline ? t("returns.markedOffline") : t("returns.marked")}
                            </span>
                          ) : null}
                        </span>
                      </td>
                      {source ? (
                        <td className="text-right tabular-nums">
                          {formatQty(line.qty, line.fractional ? "fractional" : "integer")}
                          {toDecimal(line.returnedQty).greaterThan(0)
                            ? ` (−${formatQty(line.returnedQty, line.fractional ? "fractional" : "integer")})`
                            : ""}
                        </td>
                      ) : null}
                      <td>
                        <div className="flex items-center justify-center gap-1">
                          <Button
                            variant="secondary"
                            size="icon-pos"
                            aria-label={t("returns.less")}
                            disabled={!s.selected}
                            onClick={() => step(i, -1)}
                          >
                            <Icon as={Minus} size="md" />
                          </Button>
                          <input
                            className={cn(
                              "h-12 w-20 rounded-lg border bg-card text-center font-bold tabular-nums",
                              valid ? "border-input" : "border-destructive",
                            )}
                            value={s.qty}
                            inputMode="decimal"
                            aria-label={t("returns.cols.returnQty")}
                            data-testid={`return-qty-${i}`}
                            onChange={(e) =>
                              patch(i, {
                                qty: e.target.value.replace(",", ".").replace(/[^\d.]/g, ""),
                                selected: true,
                              })
                            }
                          />
                          <Button
                            variant="secondary"
                            size="icon-pos"
                            aria-label={t("returns.more")}
                            disabled={!s.selected}
                            onClick={() => step(i, 1)}
                          >
                            <Icon as={Plus} size="md" />
                          </Button>
                        </div>
                      </td>
                      <td className="text-right font-bold tabular-nums">
                        {s.selected && valid
                          ? formatMoney(
                              source ? refundLine(line, s.qty) : returnTotals(null, [line], [s]).amount,
                            )
                          : "—"}
                      </td>
                      <td className="text-center">
                        <Checkbox
                          checked={!s.expired && s.restock}
                          disabled={s.expired}
                          aria-label={t("returns.cols.restock")}
                          onCheckedChange={(v) => patch(i, { restock: v === true })}
                        />
                      </td>
                      <td className="text-center">
                        <Checkbox
                          checked={s.expired}
                          aria-label={t("returns.cols.expired")}
                          data-testid={`return-expired-${i}`}
                          onCheckedChange={(v) =>
                            patch(i, { expired: v === true, restock: v === true ? false : s.restock })
                          }
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : null}
          {!online && lines.some((l) => l.markingCode) ? (
            <Banner tone="warning" icon={WifiOff}>
              {t("returns.markedOfflineBanner")}
            </Banner>
          ) : null}
        </div>

        <aside className="flex flex-col gap-4 rounded-2xl border border-border bg-background p-4">
          <div className="flex flex-col gap-2">
            <span className="text-[14px] font-bold">
              {t("returns.reason")} <span className="text-destructive">*</span>
            </span>
            <div role="radiogroup" className="flex flex-wrap gap-2">
              {REASONS.map((r) => (
                <button
                  key={r}
                  type="button"
                  role="radio"
                  aria-checked={reason === r}
                  data-testid={`return-reason-${r}`}
                  onClick={() => setReason(r)}
                  className={cn(
                    "h-12 rounded-xl border px-3 text-[14px] font-bold",
                    reason === r
                      ? "border-primary bg-primary-soft text-primary-strong"
                      : "border-border bg-card",
                  )}
                >
                  {t(`returns.reasons.${r}`)}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-[14px] font-bold">
              {t("returns.refundMethod")}
              {source ? (
                <span className="text-foreground-secondary">
                  {" "}
                  ·{" "}
                  {t("returns.originalMethod", {
                    method: t(`returns.methods.${defaultRefundMethod(source)}`),
                  })}
                </span>
              ) : null}
            </span>
            <div role="radiogroup" className="grid grid-cols-2 gap-2">
              {REFUND_METHODS.filter((m) => m !== "debt_adjustment" || source?.counterpartyId).map((m) => (
                <button
                  key={m}
                  type="button"
                  role="radio"
                  aria-checked={method === m}
                  data-testid={`refund-${m}`}
                  onClick={() => setMethod(m)}
                  className={cn(
                    "flex h-12 items-center justify-center gap-2 rounded-xl border px-3 text-[14px] font-bold",
                    method === m
                      ? "border-primary bg-primary-soft text-primary-strong"
                      : "border-border bg-card",
                  )}
                >
                  {m === "card" ? <Icon as={CreditCard} size="sm" /> : null}
                  {t(`returns.methods.${m}`)}
                </button>
              ))}
            </div>
            {method === "click" || method === "payme" || method === "uzum" || method === "uzqr" ? (
              <span className="text-[12px] text-foreground-secondary">{t("returns.providerManual")}</span>
            ) : null}
          </div>
          <dl className="grid grid-cols-[1fr_auto] gap-y-1 border-t border-border pt-3 text-[14px]">
            <dt>{t("returns.selected")}</dt>
            <dd className="text-right tabular-nums">{totals.count}</dd>
            <dt>{t("returns.vat")}</dt>
            <dd className="text-right tabular-nums" data-testid="return-vat">
              {formatMoney(totals.vat, { precision: 2 })}
            </dd>
            {compareMoney(totals.debtPart, "0.00" as Money) > 0 ? (
              <>
                <dt>{t("returns.debtPart")}</dt>
                <dd className="text-right tabular-nums">{formatMoney(totals.debtPart)}</dd>
              </>
            ) : null}
            <dt>{t("returns.receiptPart")}</dt>
            <dd className="text-right tabular-nums">{formatMoney(totals.moneyPart)}</dd>
            <dt className="pt-1 text-[16px] font-extrabold">{t("returns.total")}</dt>
            <dd
              className="pt-1 text-right text-[22px] font-extrabold tabular-nums"
              data-testid="return-total"
            >
              {formatMoney(totals.amount)}
            </dd>
          </dl>
          {totals.expired ? (
            <Banner tone="warning" icon={CircleAlert}>
              {t("returns.expiredNote")}
            </Banner>
          ) : null}
          {error && error !== "notFound" && error !== "noDetails" ? (
            <Banner tone="destructive" icon={CircleAlert} live="assertive">
              <span data-testid="return-error">{t(`returns.errors.${error}`)}</span>
            </Banner>
          ) : null}
          {fiscalBlocked ? (
            <Banner tone="destructive" icon={CircleAlert}>
              {t("returns.errors.fiscalBlocked")}
            </Banner>
          ) : null}
          {need?.needed ? (
            <ManagerApprovalDialog
              inline
              kind={need.kind}
              permission="returns.approve"
              amount={need.amount}
              context={{
                amount: totals.amount,
                expired_return: need.reason === "expired",
                sale_id: source?.saleId ?? null,
              }}
              requesterId={cashier.userId}
              reason={approvalReason}
              allowRemote={online}
              onApproved={(a) => void afterApproval(a)}
              onClose={() => setNeed(null)}
            />
          ) : null}
          {manualCard ? (
            manualCard.needsApproval ? (
              <ManagerApprovalDialog
                inline
                kind="card_manual_entry"
                permission="card.manual_entry.approve"
                amount="0.00"
                context={{ amount: totals.moneyPart, manual_reason: manualCard.reason }}
                requesterId={cashier.userId}
                reason={t("returns.cardManualApproval")}
                allowRemote={online}
                onApproved={(a) => void confirmManual(a)}
                onClose={() => setManualCard(null)}
              />
            ) : (
              <Banner
                tone="warning"
                icon={CreditCard}
                action={
                  <Button
                    size="sm"
                    variant="warning"
                    onClick={() => void confirmManual(null)}
                    data-testid="card-manual-confirm"
                  >
                    {t("returns.cardManualConfirm")}
                  </Button>
                }
              >
                {t("returns.cardManual", { amount: formatMoney(totals.moneyPart) })}
              </Banner>
            )
          ) : null}
          {phase === "card" ? (
            <Banner tone="info" icon={CreditCard} live="polite">
              {t("returns.cardWaiting", { amount: formatMoney(totals.moneyPart) })}
            </Banner>
          ) : null}
          {!need?.needed && !manualCard ? (
            <Button
              size="pos-cta"
              disabled={phase !== "idle" || !selectedOk}
              onClick={() => void submit()}
              data-testid="return-submit"
            >
              <Icon as={Undo2} size="lg" />
              {t("returns.submit", { amount: formatMoney(totals.amount) })}
              <Kbd keys="Enter" inverted />
            </Button>
          ) : null}
        </aside>
      </div>
      {ladderAsk ? (
        <Ladder46Modal
          onOk={() => {
            setLadderAsk(false);
            setLadderAcked(true);
            void submit(true);
          }}
        />
      ) : null}
    </PosScreen>
  );
}

export const Returns = { route: "returns", titleKey: "pos:returns.title", Page: ReturnsPage } as const;

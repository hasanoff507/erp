import { useUnit } from "effector-react";
import {
  Banknote,
  CircleAlert,
  CreditCard,
  Printer,
  ReceiptText,
  RefreshCw,
  RotateCcw,
  TrendingUp,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatDateTime, formatMoney } from "@shared/lib/format";
import { addMoney, money, subtractMoney } from "@shared/lib/money";
import { cardAttempts, outbox, outboxChanged } from "@shared/offline";
import { $isOnline } from "@shared/state/network";
import { $session } from "@shared/state/session";
import {
  Banner,
  Button,
  ConfirmDialog,
  EmptyState,
  Icon,
  Kbd,
  KpiCard,
  NoPermissionState,
  Skeleton,
  cn,
} from "@shared/ui";

import {
  $closeConfirmedFor,
  $posCashier,
  $posDevice,
  $posShift,
  $shiftCount,
  PosScreen,
  cashierCan,
  defaultShiftDataDeps,
  loadShiftSnapshot,
  shiftCloseCancelled,
  shiftCloseConfirmed,
  shiftClosedLocally,
  type ShiftSnapshot,
} from "#/entities/pos-session/index.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";
import { defaultCardPaymentDeps } from "#/features/card-payment/index.ts";
import { printDoc } from "#/features/ops-print/index.ts";

import {
  closeShiftFx,
  defaultCloseDeps,
  heldCloseCount,
  localZReport,
  zReceiptDoc,
  type ZView,
} from "../../model/index.ts";

const POS_SALE = "/pos/sale";
const POS_SYNC = "/pos/sync";
const POS_COUNT = "/pos/shift/cash-count";
const POS_LOGIN = "/pos/login";

/** POS-07 — Smena yopish, Z-hisobot (07, route /pos/shift/close; maket Pos07Smena.dc.html). */
function ShiftClosePage() {
  const { t } = useTranslation("pos");
  const navigate = useNavigate();
  const [cashier, shift, device, online, confirmedFor, count, session] = useUnit([
    $posCashier,
    $posShift,
    $posDevice,
    $isOnline,
    $closeConfirmedFor,
    $shiftCount,
    $session,
  ]);
  const closing = useUnit(closeShiftFx.pending);
  const [snapshot, setSnapshot] = useState<ShiftSnapshot | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [failed, setFailed] = useState(false);
  const [z, setZ] = useState<ZView | null>(null);
  const [closeEventId, setCloseEventId] = useState<string | null>(null);
  const [printError, setPrintError] = useState<string | null>(null);
  const started = useRef(false);

  const back = useCallback(() => void navigate(z ? POS_LOGIN : POS_SALE), [navigate, z]);

  useEffect(() => {
    if (!shift) return;
    let alive = true;
    void cardAttempts
      .unresolved()
      .then((rows) => alive && setBlocked(rows.length > 0))
      .catch(() => undefined);
    void loadShiftSnapshot(
      defaultShiftDataDeps(() => online),
      shift,
    ).then((s) => alive && setSnapshot(s));
    return () => {
      alive = false;
    };
  }, [shift, online]);

  // POS-15 «Davom etish (Z-hisobot)» → back here with the count → ONE shift.closed (07 POS-07 / POS-15).
  useEffect(() => {
    if (!shift || !cashier || !snapshot || started.current) return;
    if (confirmedFor !== shift.id || count?.shiftId !== shift.id) return;
    started.current = true;
    const deps = defaultCloseDeps(defaultCardPaymentDeps());
    void closeShiftFx({ deps, input: { shift, count, actorUserId: cashier.userId } })
      .then(async (outcome) => {
        if (!outcome.ok) {
          setBlocked(true);
          started.current = false;
          shiftCloseCancelled();
          return;
        }
        setCloseEventId(outcome.clientEventId);
        const local = localZReport(snapshot.totals, count);
        let view: ZView = {
          source: outcome.z ? "server" : "local",
          shiftId: shift.id,
          shiftNo: shift.shift_no,
          report: outcome.z ?? local,
          fiscalStatus: null,
        };
        if (!outcome.z && online) {
          try {
            const server = await deps.zReport(shift.id);
            view = {
              source: "server",
              shiftId: shift.id,
              shiftNo: server.shift_no,
              report: server,
              fiscalStatus: server.fiscal.status,
            };
          } catch {
            /* not synced yet — the local figures stay */
          }
        }
        setZ(view);
        shiftClosedLocally();
      })
      .catch(() => {
        setFailed(true);
        started.current = false;
      });
  }, [shift, cashier, snapshot, confirmedFor, count, online]);

  const startClose = () => {
    if (!shift || blocked || !cashierCan(cashier, "shift.close")) return;
    setConfirm(true);
  };

  const print = async () => {
    if (!z || !cashier) return;
    setPrintError(null);
    const r = await printDoc(
      zReceiptDoc(z, {
        storeName: session?.tenant.name ?? "",
        branchName: device?.branchName ?? null,
        cashierName: cashier.fullName,
        registerName: device?.cashRegisterName ?? null,
        at: new Date().toISOString(),
      }),
    );
    if (!r.ok) setPrintError(r.code);
  };

  // F12 → POS-12 is a global key (PosBootstrap GlobalHotkeys)
  useHotkeys([
    { key: "Escape", handler: () => (confirm ? setConfirm(false) : back()) },
    { key: "Enter", handler: () => (z ? void print() : startClose()) },
  ]);

  if (z)
    return (
      <ZReportView
        z={z}
        closeEventId={closeEventId}
        onPrint={() => void print()}
        printError={printError}
        onBack={back}
      />
    );

  if (!cashier || !cashierCan(cashier, "shift.close")) {
    return (
      <PosScreen title={t("shiftClose.title")} backLabel={t("shiftClose.back")} onBack={back}>
        <NoPermissionState />
      </PosScreen>
    );
  }
  if (!shift) {
    return (
      <PosScreen title={t("shiftClose.title")} backLabel={t("shiftClose.back")} onBack={back}>
        <EmptyState icon={ReceiptText} title={t("shiftClose.noShift")} />
      </PosScreen>
    );
  }

  const totals = snapshot?.totals;
  const net = totals ? subtractMoney(totals.salesTotal, totals.returnsTotal) : null;
  const avg =
    totals && totals.salesCount > 0
      ? formatMoney(money(formatAverage(totals.salesTotal, totals.salesCount)))
      : formatMoney("0.00");

  return (
    <PosScreen
      testId="pos-shift-close"
      title={t("shiftClose.title")}
      hotkey="F8"
      subtitle={t("shiftClose.subtitle", { number: shift.shift_no, from: formatDateTime(shift.opened_at) })}
      backLabel={t("shiftClose.back")}
      onBack={back}
    >
      {/* the card block does not wait for the shift figures (they may need the network) */}
      {blocked ? (
        <Banner tone="destructive" icon={CircleAlert} live="assertive" className="mb-4">
          <span data-testid="close-blocked-card">{t("shiftClose.cardUnknown")}</span>
        </Banner>
      ) : null}
      {!totals || !snapshot ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <div className="flex flex-col gap-4">
          {failed ? (
            <Banner tone="destructive" icon={CircleAlert} live="assertive">
              {t("shiftClose.failed")}
            </Banner>
          ) : null}
          {totals.salesCount === 0 && totals.returnsCount === 0 ? (
            <Banner tone="info" icon={ReceiptText}>
              {t("shiftClose.empty")}
            </Banner>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label={t("shiftClose.kpi.sales")}
              value={formatMoney(totals.salesTotal)}
              icon={TrendingUp}
              tone="primary"
            />
            <KpiCard
              label={t("shiftClose.kpi.receipts")}
              value={String(totals.salesCount)}
              icon={ReceiptText}
              tone="info"
              note={t("shiftClose.kpi.avg", { amount: avg })}
            />
            <KpiCard
              label={t("shiftClose.kpi.returns")}
              value={formatMoney(totals.returnsTotal)}
              icon={RotateCcw}
              tone="warning"
            />
            <KpiCard
              label={t("shiftClose.kpi.net")}
              value={formatMoney(net ?? "0.00")}
              icon={Banknote}
              tone="success"
            />
          </div>
          <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
            <section className="rounded-2xl border border-border p-4">
              <h2 className="pb-2 text-[16px] font-extrabold">{t("shiftClose.byMethod")}</h2>
              <table className="w-full text-[14px]" data-testid="method-table">
                <thead className="text-left text-[12px] text-foreground-secondary">
                  <tr>
                    <th className="py-1">{t("shiftClose.cols.method")}</th>
                    <th className="text-right">{t("shiftClose.cols.count")}</th>
                    <th className="text-right">{t("shiftClose.cols.sales")}</th>
                    <th className="text-right">{t("shiftClose.cols.returns")}</th>
                    <th className="text-right">{t("shiftClose.cols.net")}</th>
                  </tr>
                </thead>
                <tbody>
                  {totals.rows.map((r) => (
                    <tr key={r.key} className="border-t border-border" data-testid={`method-${r.key}`}>
                      <td className="py-2">
                        <span className="flex flex-col">
                          <span className="font-bold">{t(`shiftClose.methods.${r.key}`)}</span>
                          <span className="text-[12px] text-foreground-secondary">
                            {t(`shiftClose.methodNotes.${r.key}`)}
                          </span>
                        </span>
                      </td>
                      <td className="text-right tabular-nums">{r.count}</td>
                      <td className="text-right tabular-nums">
                        {formatMoney(r.sales, { withCurrency: false })}
                      </td>
                      <td className="text-right tabular-nums">
                        {formatMoney(r.returns, { withCurrency: false })}
                      </td>
                      <td className="text-right font-bold tabular-nums">
                        {formatMoney(r.net, { withCurrency: false })}
                      </td>
                    </tr>
                  ))}
                  <tr className="border-t-2 border-foreground font-extrabold">
                    <td className="py-2">{t("shiftClose.total")}</td>
                    <td className="text-right tabular-nums">{totals.salesCount}</td>
                    <td className="text-right tabular-nums">
                      {formatMoney(totals.salesTotal, { withCurrency: false })}
                    </td>
                    <td className="text-right tabular-nums">
                      {formatMoney(totals.returnsTotal, { withCurrency: false })}
                    </td>
                    <td className="text-right tabular-nums">
                      {formatMoney(net ?? "0.00", { withCurrency: false })}
                    </td>
                  </tr>
                </tbody>
              </table>
              <p className="pt-2 text-[12px] text-foreground-secondary">
                {t("shiftClose.debtNote", { voided: totals.voidedCount })}
              </p>
            </section>
            <div className="flex flex-col gap-4">
              <section className="rounded-2xl border border-border p-4">
                <h2 className="pb-2 text-[16px] font-extrabold">{t("shiftClose.cashInDrawer")}</h2>
                <dl className="grid grid-cols-[1fr_auto] gap-y-1 text-[14px]">
                  <dt>{t("cashMovement.calc.opening")}</dt>
                  <dd className="text-right tabular-nums">{formatMoney(totals.openingCash)}</dd>
                  <dt>{t("cashMovement.calc.cashSales")}</dt>
                  <dd className="text-right tabular-nums">+{formatMoney(totals.cashSales)}</dd>
                  <dt>{t("cashMovement.calc.cashReturns")}</dt>
                  <dd className="text-right tabular-nums">−{formatMoney(totals.cashReturns)}</dd>
                  <dt>{t("cashMovement.calc.in")}</dt>
                  <dd className="text-right tabular-nums">+{formatMoney(totals.cashIn)}</dd>
                  <dt>{t("cashMovement.calc.out")}</dt>
                  <dd className="text-right tabular-nums">−{formatMoney(totals.cashOut)}</dd>
                  <dt className="pt-1 font-extrabold">{t("shiftClose.expected")}</dt>
                  <dd
                    className="pt-1 text-right text-[18px] font-extrabold tabular-nums"
                    data-testid="expected-cash"
                  >
                    {formatMoney(snapshot.expectedCash)}
                  </dd>
                </dl>
                <p className="pt-2 text-[12px] text-foreground-secondary">{t("shiftClose.countNext")}</p>
              </section>
              <section className="rounded-2xl border border-border p-4">
                <h2 className="pb-2 text-[16px] font-extrabold">{t("shiftClose.fiscal")}</h2>
                <dl className="grid grid-cols-[1fr_auto] gap-y-1 text-[14px]">
                  <dt>{t("shiftClose.fiscalTotal")}</dt>
                  <dd className="text-right tabular-nums">{snapshot.fiscal.total}</dd>
                  <dt>{t("shiftClose.fiscalAcked")}</dt>
                  <dd className="text-right tabular-nums">{snapshot.fiscal.acked}</dd>
                  <dt>{t("shiftClose.fiscalUnsent")}</dt>
                  <dd className="text-right tabular-nums">
                    {snapshot.fiscal.unsent}
                    {snapshot.fiscal.oldestUnsentAt
                      ? ` · ${formatDateTime(snapshot.fiscal.oldestUnsentAt)}`
                      : ""}
                  </dd>
                </dl>
              </section>
            </div>
          </div>
          {snapshot.unsynced > 0 ? (
            <Banner
              tone="warning"
              icon={RefreshCw}
              action={
                <Button variant="warning" size="sm" onClick={() => void navigate(POS_SYNC)}>
                  {t("shiftClose.sync")} <Kbd keys="F12" />
                </Button>
              }
            >
              {t("shiftClose.unsynced", { n: snapshot.unsynced })}
            </Banner>
          ) : null}
          <Button
            size="pos-cta"
            variant="destructive"
            disabled={closing || blocked}
            onClick={startClose}
            data-testid="close-shift"
            className={cn("self-end")}
          >
            {closing ? t("shiftClose.closing") : t("shiftClose.close")}
            <Kbd keys="Enter" inverted />
          </Button>
        </div>
      )}
      {confirm ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => (open ? undefined : setConfirm(false))}
          title={t("shiftClose.confirmTitle")}
          description={t("shiftClose.confirmText")}
          confirmLabel={t("shiftClose.confirmYes")}
          cancelLabel={t("shiftClose.confirmNo")}
          tone="destructive"
          onConfirm={() => {
            setConfirm(false);
            shiftCloseConfirmed(shift.id);
            // counted already (POS-15 opened first) → the close runs right here; otherwise count first
            if (count?.shiftId !== shift.id) void navigate(POS_COUNT);
          }}
        />
      ) : null}
    </PosScreen>
  );
}

/** Average receipt (display only): whole so'm of total ÷ count by long division on the digit string. */
function formatAverage(total: string, count: number): string {
  const digits = total.split(".")[0] ?? "0";
  let rem = 0;
  let out = "";
  for (const ch of digits.replace("-", "")) {
    const cur = rem * 10 + "0123456789".indexOf(ch);
    const q = Math.floor(cur / count);
    rem = cur % count;
    if (out || q) out += String(q);
  }
  return out || "0";
}

function ZReportView({
  z,
  closeEventId,
  onPrint,
  printError,
  onBack,
}: {
  z: ZView;
  closeEventId: string | null;
  onPrint: () => void;
  printError: string | null;
  onBack: () => void;
}) {
  const held = useHeldClose(z.shiftId, closeEventId);
  const { t } = useTranslation("pos");
  const r = z.report;
  const qr = addMoney(
    money(r.totals_by_method.uzqr),
    money(r.totals_by_method.click),
    money(r.totals_by_method.payme),
    money(r.totals_by_method.uzum),
  );
  const rows: [string, string, string?][] = [
    [t("shiftClose.methods.cash"), r.totals_by_method.cash],
    [t("shiftClose.methods.card_integrated"), r.card_split.integrated, "z-card-integrated"],
    [t("shiftClose.methods.card_manual"), r.card_split.manual, "z-card-manual"],
    [t("shiftClose.methods.qr"), qr],
    [t("shiftClose.methods.debt"), r.totals_by_method.debt],
    [t("shiftClose.kpi.returns"), r.returns_total],
  ];
  return (
    <PosScreen
      testId="pos-z-report"
      title={t("shiftClose.zTitle", { number: z.shiftNo })}
      backLabel={t("shiftClose.toLogin")}
      onBack={onBack}
      actions={
        <Button size="pos" onClick={onPrint} data-testid="z-print">
          <Icon as={Printer} size="md" />
          {t("shiftClose.print")}
          <Kbd keys="Enter" inverted />
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <Banner
          tone={z.source === "server" ? "success" : "warning"}
          icon={z.source === "server" ? ReceiptText : CircleAlert}
        >
          <span data-testid="z-source">
            {z.source === "server" ? t("shiftClose.zServer") : t("shiftClose.zLocal")}
          </span>
        </Banner>
        {held > 0 ? (
          <Banner
            tone="warning"
            icon={RefreshCw}
            action={
              <Button asChild variant="warning" size="sm">
                <Link to={POS_SYNC}>{t("shiftClose.sync")}</Link>
              </Button>
            }
          >
            <span data-testid="close-held">{t("shiftClose.held", { n: held })}</span>
          </Banner>
        ) : null}
        {printError ? (
          <Banner tone="destructive" icon={Printer} live="assertive">
            {t(`equipment.printer.errors.${printError}`, { defaultValue: t("shiftClose.printFailed") })}
          </Banner>
        ) : null}
        <div className="grid gap-4 lg:grid-cols-2">
          <dl className="grid grid-cols-[1fr_auto] gap-y-2 rounded-2xl border border-border p-4 text-[15px]">
            <dt>{t("shiftClose.kpi.receipts")}</dt>
            <dd className="text-right tabular-nums">{r.sales_count}</dd>
            {rows.map(([label, value, testId]) => (
              <FragmentRow key={label} label={label} value={value} testId={testId} />
            ))}
          </dl>
          <dl className="grid grid-cols-[1fr_auto] gap-y-2 rounded-2xl border border-border p-4 text-[15px]">
            <dt>{t("shiftClose.expected")}</dt>
            <dd className="text-right tabular-nums">{formatMoney(r.expected_cash)}</dd>
            <dt>{t("cashCount.counted")}</dt>
            <dd className="text-right tabular-nums" data-testid="z-counted">
              {formatMoney(r.counted_cash ?? "0.00")}
            </dd>
            <dt className="font-extrabold">{t("cashCount.variance")}</dt>
            <dd className="text-right font-extrabold tabular-nums" data-testid="z-variance">
              {formatMoney(r.variance ?? "0.00")}
            </dd>
            {z.source === "server" ? (
              <>
                <dt>{t("shiftClose.vat")}</dt>
                <dd className="text-right tabular-nums">{formatMoney(r.vat_total, { precision: 2 })}</dd>
              </>
            ) : null}
            {r.card_settlements.map((s) => (
              <FragmentRow
                key={s.card_terminal_id}
                label={t("shiftClose.settlement", { status: t(`shiftClose.settlementStatus.${s.status}`) })}
                value={s.net_total}
              />
            ))}
          </dl>
        </div>
        <span className="flex items-center gap-2 text-[13px] text-foreground-secondary">
          <Icon as={CreditCard} size="sm" />
          {t("shiftClose.cardSplitNote")}
        </span>
      </div>
    </PosScreen>
  );
}

function FragmentRow({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd className="text-right tabular-nums" data-testid={testId}>
        {formatMoney(value)}
      </dd>
    </>
  );
}

export const ShiftClose = {
  route: "shift/close",
  titleKey: "pos:shiftClose.title",
  Page: ShiftClosePage,
} as const;

/** ACC-01: how many earlier documents the queued `shift.closed` still waits for (re-read on outbox changes). */
function useHeldClose(shiftId: string, closeEventId: string | null): number {
  const [held, setHeld] = useState(0);
  useEffect(() => {
    let alive = true;
    const read = () =>
      void outbox
        .heldShiftCloses()
        .then((rows) => alive && setHeld(heldCloseCount(rows, shiftId, closeEventId)))
        .catch(() => undefined);
    read();
    const unwatch = outboxChanged.watch(read);
    const timer = setInterval(read, 5_000);
    return () => {
      alive = false;
      unwatch();
      clearInterval(timer);
    };
  }, [shiftId, closeEventId]);
  return held;
}

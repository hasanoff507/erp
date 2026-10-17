import { useUnit } from "effector-react";
import { Banknote, CircleAlert, Minus, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { addMoney, compareMoney, type Money } from "@shared/lib/money";
import { $isOnline } from "@shared/state/network";
import {
  Banner,
  Button,
  EmptyState,
  FormField,
  Icon,
  Kbd,
  MoneyInput,
  NoPermissionState,
  Skeleton,
  Textarea,
  cn,
} from "@shared/ui";

import {
  $posCashier,
  $posShift,
  DENOMINATIONS,
  PosScreen,
  cashierCan,
  defaultShiftDataDeps,
  loadShiftSnapshot,
  shiftCloseCancelled,
  shiftCountSaved,
  type ShiftSnapshot,
} from "#/entities/pos-session/index.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";

import { COUNT_NOTE_MAX, MAX_PIECES, countView, noteRequired } from "../../model/index.ts";

const POS_CLOSE = "/pos/shift/close";

/** POS-15 — Smena yopishda naqdni sanash (07, route /pos/shift/cash-count; maket Pos15Sanash.dc.html). */
function CashCountPage() {
  const { t } = useTranslation("pos");
  const navigate = useNavigate();
  const [cashier, shift, online] = useUnit([$posCashier, $posShift, $isOnline]);
  const [snapshot, setSnapshot] = useState<ShiftSnapshot | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [manual, setManual] = useState("");
  const [note, setNote] = useState("");
  const [noteError, setNoteError] = useState(false);

  const back = useCallback(() => {
    shiftCloseCancelled();
    void navigate(POS_CLOSE);
  }, [navigate]);

  useEffect(() => {
    if (!shift) return;
    let alive = true;
    void loadShiftSnapshot(
      defaultShiftDataDeps(() => online),
      shift,
    ).then((s) => alive && setSnapshot(s));
    return () => {
      alive = false;
    };
  }, [shift, online]);

  const view = snapshot ? countView(counts, manual, snapshot.expectedCash) : null;

  const proceed = () => {
    if (!shift || !view || !snapshot) return;
    const trimmed = note.trim();
    if (noteRequired(view) && trimmed === "") {
      setNoteError(true);
      return;
    }
    if (view.counted === null) return;
    shiftCountSaved({
      shiftId: shift.id,
      countedCash: view.counted,
      countedCardTotal: snapshot.totals.cardSplit.manual,
      varianceNote: trimmed || null,
      expectedCash: snapshot.expectedCash,
      variance: view.variance ?? ("0.00" as Money),
    });
    void navigate(POS_CLOSE);
  };

  useHotkeys([
    // Enter from the counting inputs too, but a newline in the note stays a newline
    {
      key: "Enter",
      allowInInput: true,
      handler: (e) => ((e.target as HTMLElement | null)?.tagName === "TEXTAREA" ? false : proceed()),
    },
    { key: "Escape", handler: back },
  ]);

  if (!cashier || !cashierCan(cashier, "cash.count.shift")) {
    return (
      <PosScreen title={t("cashCount.title")} backLabel={t("cashCount.back")} onBack={back}>
        <NoPermissionState />
      </PosScreen>
    );
  }
  if (!shift) {
    return (
      <PosScreen title={t("cashCount.title")} backLabel={t("cashCount.back")} onBack={back}>
        <EmptyState icon={Banknote} title={t("cashMovement.noShift")} />
      </PosScreen>
    );
  }

  const setCount = (den: string, value: number) =>
    setCounts((c) => ({ ...c, [den]: Math.max(0, Math.min(MAX_PIECES, value)) }));
  const varianceTone =
    !view || view.variance === null
      ? ""
      : compareMoney(view.variance, "0.00" as Money) < 0
        ? "text-destructive-strong"
        : compareMoney(view.variance, "0.00" as Money) > 0
          ? "text-warning-strong"
          : "text-success-strong";

  return (
    <PosScreen
      testId="pos-cash-count"
      title={t("cashCount.title")}
      subtitle={t("cashCount.subtitle", { number: shift.shift_no })}
      backLabel={t("cashCount.back")}
      onBack={back}
    >
      {!snapshot || !view ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
          <section className="flex flex-col gap-3">
            <p className="text-[14px] text-foreground-secondary">{t("cashCount.hint")}</p>
            <ul className="grid gap-2 sm:grid-cols-2">
              {DENOMINATIONS.map((den) => {
                const n = counts[den] ?? 0;
                return (
                  <li
                    key={den}
                    className={cn(
                      "flex items-center gap-2 rounded-xl border border-border px-3 py-2",
                      n > 0 ? "bg-card" : "bg-background",
                    )}
                  >
                    <span className="w-24 text-[15px] font-extrabold tabular-nums">
                      {formatMoney(den, { withCurrency: false })}
                    </span>
                    <Button
                      variant="secondary"
                      size="icon-pos"
                      aria-label={t("cashCount.minus", { den: formatMoney(den) })}
                      onClick={() => setCount(den, n - 1)}
                    >
                      <Icon as={Minus} size="md" />
                    </Button>
                    <input
                      type="text"
                      inputMode="numeric"
                      aria-label={t("cashCount.pieces", { den: formatMoney(den, { withCurrency: false }) })}
                      data-testid={`den-${den}`}
                      value={String(n)}
                      onChange={(e) => {
                        const digits = e.target.value.replace(/\D/g, "").slice(0, 4);
                        let v = 0;
                        for (const ch of digits) v = v * 10 + "0123456789".indexOf(ch);
                        setCount(den, v);
                      }}
                      className="h-12 w-16 rounded-lg border border-input bg-card text-center text-[16px] font-bold tabular-nums"
                    />
                    <Button
                      variant="secondary"
                      size="icon-pos"
                      aria-label={t("cashCount.plus", { den: formatMoney(den) })}
                      onClick={() => setCount(den, n + 1)}
                    >
                      <Icon as={Plus} size="md" />
                    </Button>
                  </li>
                );
              })}
            </ul>
            <p className="text-[13px] text-foreground-secondary">
              {t("cashCount.piecesTotal", { n: view.pieces })}
            </p>
            <FormField
              label={t("cashCount.counted")}
              required
              hint={view.fromDenominations ? t("cashCount.fromDenominations") : undefined}
            >
              {view.fromDenominations ? (
                <output
                  data-testid="counted-cash"
                  className="flex h-14 items-center justify-end rounded-xl border border-input bg-card px-4 text-[24px] font-extrabold tabular-nums"
                >
                  {formatMoney(view.counted ?? "0.00")}
                </output>
              ) : (
                <MoneyInput
                  value={manual}
                  onChange={setManual}
                  data-testid="counted-cash-input"
                  className="h-14 text-[22px] font-extrabold"
                />
              )}
            </FormField>
          </section>
          <aside className="flex flex-col gap-3 rounded-2xl border border-border bg-background p-4">
            <h2 className="text-[16px] font-extrabold">{t("shiftClose.expected")}</h2>
            <dl className="grid grid-cols-[1fr_auto] gap-y-1 text-[14px]">
              <dt>{t("cashMovement.calc.opening")}</dt>
              <dd className="text-right tabular-nums">+{formatMoney(snapshot.totals.openingCash)}</dd>
              <dt>{t("cashMovement.calc.cashSales")}</dt>
              <dd className="text-right tabular-nums">+{formatMoney(snapshot.totals.cashSales)}</dd>
              <dt>{t("cashMovement.calc.cashReturns")}</dt>
              <dd className="text-right tabular-nums">−{formatMoney(snapshot.totals.cashReturns)}</dd>
              <dt>{t("cashMovement.calc.in")}</dt>
              <dd className="text-right tabular-nums">+{formatMoney(snapshot.totals.cashIn)}</dd>
              <dt>{t("cashMovement.calc.out")}</dt>
              <dd className="text-right tabular-nums">−{formatMoney(snapshot.totals.cashOut)}</dd>
            </dl>
            <dl className="grid grid-cols-[1fr_auto] gap-y-1 border-t border-border pt-2 text-[15px]">
              <dt>{t("cashCount.expected")}</dt>
              <dd className="text-right font-bold tabular-nums" data-testid="count-expected">
                {formatMoney(snapshot.expectedCash)}
              </dd>
              <dt>{t("cashCount.counted")}</dt>
              <dd className="text-right font-bold tabular-nums">
                {view.counted ? formatMoney(view.counted) : "—"}
              </dd>
              <dt className="font-extrabold">{t("cashCount.variance")}</dt>
              <dd
                className={cn("text-right font-extrabold tabular-nums", varianceTone)}
                data-testid="count-variance"
              >
                {view.variance ? formatMoney(view.variance) : "—"}
                {view.variance ? ` · ${t(`cashCount.varianceKinds.${view.varianceKind}`)}` : ""}
              </dd>
            </dl>
            <dl className="grid grid-cols-[1fr_auto] gap-y-1 border-t border-border pt-2 text-[14px]">
              <dt className="font-bold">{t("cashCount.cardTotal")}</dt>
              <dd className="text-right font-bold tabular-nums">
                {formatMoney(
                  addMoney(snapshot.totals.cardSplit.integrated, snapshot.totals.cardSplit.manual),
                )}
              </dd>
              <dt>{t("shiftClose.methods.card_integrated")}</dt>
              <dd className="text-right tabular-nums">{formatMoney(snapshot.totals.cardSplit.integrated)}</dd>
              <dt>{t("shiftClose.methods.card_manual")}</dt>
              <dd className="text-right tabular-nums" data-testid="count-card-manual">
                {formatMoney(snapshot.totals.cardSplit.manual)}
              </dd>
            </dl>
            <FormField
              label={t("cashCount.note")}
              required={view.varianceKind !== "match"}
              optional={view.varianceKind === "match"}
              error={noteError ? t("cashCount.noteRequired") : null}
            >
              <Textarea
                value={note}
                rows={3}
                maxLength={COUNT_NOTE_MAX}
                data-testid="variance-note"
                onChange={(e) => {
                  setNote(e.target.value);
                  setNoteError(false);
                }}
              />
            </FormField>
            {noteError ? (
              <Banner tone="destructive" icon={CircleAlert} live="assertive">
                {t("cashCount.noteRequired")}
              </Banner>
            ) : null}
            <Button
              size="pos-cta"
              onClick={proceed}
              disabled={view.counted === null}
              data-testid="count-continue"
            >
              {t("cashCount.continue")}
              <Kbd keys="Enter" inverted />
            </Button>
          </aside>
        </div>
      )}
    </PosScreen>
  );
}

export const CashCount = {
  route: "shift/cash-count",
  titleKey: "pos:cashCount.title",
  Page: CashCountPage,
} as const;

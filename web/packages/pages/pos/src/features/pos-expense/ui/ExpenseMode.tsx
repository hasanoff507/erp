/**
 * POS-14 «Xarajat» mode (07 POS-14 amallar «Xarajat»; mockup Pos14KassaPul): amount (keypad / digits),
 * category chips from the cached `GET /expense-categories` (the Dt account shown), tax type chips for a
 * 6410 category, comment; above the cashier's `cash.withdraw` limit the inline ApprovalDialog
 * (`cash_withdrawal_over_limit`); «Tasdiqlash — N so'm xarajat» (`Enter`), `Esc` back. Touch targets ≥ 48px.
 */
import { useUnit } from "effector-react";
import { CircleAlert, Receipt, WifiOff } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { $isOnline } from "@shared/state/network";
import { Banner, Button, FormField, Icon, Kbd, Textarea, cn } from "@shared/ui";

import { $posCashier, $posDevice, $posShift, NumPad, numPadAppend } from "#/entities/pos-session/index.ts";
import { tashkentDate } from "#/shared/lib/dates.ts";
import { digitKeys, useHotkeys } from "#/shared/lib/use-hotkeys.ts";

import {
  COMMENT_MAX,
  TAX_TYPES,
  defaultPosExpenseDeps,
  digitsToMoney,
  expenseNeedsApproval,
  expensePayload,
  isTaxCategory,
  loadCategories,
  newExpenseId,
  validateExpense,
  type ExpenseApprovalRef,
  type ExpenseError,
  type PosExpenseCategory,
  type TaxType,
} from "../model/index.ts";

/** What the page's ApprovalDialog needs (`cash_withdrawal_over_limit`, approver's `cash.withdraw`). */
export interface ExpenseApprovalSlot {
  amount: string;
  context: Record<string, unknown>;
  ownLimit: string;
  allowRemote: boolean;
  onApproved: (approval: ExpenseApprovalRef) => void;
  onClose: () => void;
}

export interface ExpenseModeProps {
  onBack: () => void;
  /** After a recorded expense (the page refreshes «Kassadagi naqd»). */
  onDone: () => void;
  /** The inline ManagerApprovalDialog, rendered by the page (FSD: a feature does not import a feature). */
  renderApproval: (slot: ExpenseApprovalSlot) => ReactNode;
}

export function ExpenseMode({ onBack, onDone, renderApproval }: ExpenseModeProps) {
  const { t } = useTranslation("pos");
  const [cashier, shift, device, online] = useUnit([$posCashier, $posShift, $posDevice, $isOnline]);
  const [categories, setCategories] = useState<PosExpenseCategory[] | null>(null);
  const [fromCache, setFromCache] = useState(false);
  const [digits, setDigits] = useState("");
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [taxType, setTaxType] = useState<TaxType | null>(null);
  const [comment, setComment] = useState("");
  const [errors, setErrors] = useState<ExpenseError[]>([]);
  const [needApproval, setNeedApproval] = useState(false);
  const [ownLimit, setOwnLimit] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    void loadCategories(defaultPosExpenseDeps(() => online)).then((r) => {
      setCategories(r.categories?.items ?? []);
      setFromCache(r.fromCache);
    });
    // categories are read once per visit (and again when the network comes back)
  }, [online]);

  const amount = digitsToMoney(digits);
  const category = categories?.find((c) => c.id === categoryId) ?? null;

  const commit = useCallback(
    async (approval: ExpenseApprovalRef | null) => {
      if (!cashier || !shift || !amount || !category) return;
      setBusy(true);
      setFailed(false);
      try {
        await defaultPosExpenseDeps(() => online).enqueue(
          expensePayload({
            id: newExpenseId(),
            docDate: tashkentDate(),
            branchId: typeof shift.branch_id === "string" ? shift.branch_id : (device?.branchId ?? ""),
            cashRegisterId: shift.cash_register_id,
            shiftId: shift.id,
            category,
            amount,
            comment,
            taxType,
            approval,
          }),
          cashier.userId,
        );
        setDone(amount);
        setDigits("");
        setCategoryId(null);
        setTaxType(null);
        setComment("");
        setNeedApproval(false);
        onDone();
      } catch {
        setFailed(true);
      } finally {
        setBusy(false);
      }
    },
    [cashier, shift, device, amount, category, comment, taxType, online, onDone],
  );

  const submit = async () => {
    if (busy || !cashier) return;
    const found = validateExpense({ digits, categoryId, taxType, comment }, category);
    setErrors(found);
    setDone(null);
    if (found.length > 0 || !amount) return;
    const own = await defaultPosExpenseDeps(() => online).ownLimit(cashier.userId);
    if (expenseNeedsApproval(cashier, own, amount)) {
      setOwnLimit(own ?? "0.00");
      setNeedApproval(true);
      return;
    }
    await commit(null);
  };

  useHotkeys([
    ...digitKeys((d) => setDigits((v) => numPadAppend(v, d))),
    { key: "Backspace", handler: () => setDigits((v) => v.slice(0, -1)) },
    ...(needApproval ? [] : [{ key: "Enter", handler: () => void submit() }]),
    { key: "Escape", handler: () => (needApproval ? setNeedApproval(false) : onBack()) },
  ]);

  if (!cashier || !shift) return null;
  const errorOf = (e: ExpenseError) => (errors.includes(e) ? t(`posExpense.errors.${e}`) : null);

  return (
    <div className="flex flex-col gap-4" data-testid="pos-expense">
      {fromCache && categories && categories.length > 0 ? (
        <Banner tone="info" icon={WifiOff}>
          {t("posExpense.cached")}
        </Banner>
      ) : null}
      <FormField label={t("posExpense.amount")} required error={errorOf("amount")}>
        <output
          data-testid="expense-amount"
          className="flex h-16 items-center justify-end rounded-xl border border-input bg-card px-4 text-[30px] font-extrabold tabular-nums"
        >
          {formatMoney(amount ?? "0.00", { withCurrency: false })}{" "}
          <span className="ml-2 text-[16px] text-foreground-secondary">{t("cashMovement.som")}</span>
        </output>
      </FormField>
      <NumPad value={digits} onChange={setDigits} backspaceLabel={t("cashMovement.backspace")} />
      <FormField label={t("posExpense.category")} required error={errorOf("category")}>
        {categories === null ? (
          <p className="text-small text-foreground-secondary">{t("posExpense.loading")}</p>
        ) : categories.length === 0 ? (
          <Banner tone="warning" icon={CircleAlert}>
            {t("posExpense.noCategories")}
          </Banner>
        ) : (
          <div role="radiogroup" className="flex flex-wrap gap-2">
            {categories.map((c) => (
              <button
                key={c.id}
                type="button"
                role="radio"
                aria-checked={categoryId === c.id}
                data-testid={`expense-category-${c.id}`}
                onClick={() => {
                  setCategoryId(c.id);
                  setTaxType(null);
                  setErrors((e) => e.filter((x) => x !== "category" && x !== "taxType"));
                }}
                className={cn(
                  "flex min-h-12 flex-col items-start justify-center rounded-xl border px-4 py-1.5 text-left",
                  categoryId === c.id
                    ? "border-primary bg-primary-soft text-primary-strong"
                    : "border-border bg-card",
                )}
              >
                <span className="text-[14px] font-bold">{c.name}</span>
                <span className="text-[11px] text-foreground-secondary">{c.default_account}</span>
              </button>
            ))}
          </div>
        )}
      </FormField>
      {isTaxCategory(category) ? (
        <FormField label={t("posExpense.taxType")} required error={errorOf("taxType")}>
          <div role="radiogroup" className="flex flex-wrap gap-2">
            {TAX_TYPES.map((k) => (
              <button
                key={k}
                type="button"
                role="radio"
                aria-checked={taxType === k}
                onClick={() => setTaxType(k)}
                className={cn(
                  "h-12 rounded-xl border px-4 text-[14px] font-bold",
                  taxType === k
                    ? "border-primary bg-primary-soft text-primary-strong"
                    : "border-border bg-card",
                )}
              >
                {t(`posExpense.taxTypes.${k}`)}
              </button>
            ))}
          </div>
        </FormField>
      ) : null}
      <FormField label={t("posExpense.comment")} optional error={errorOf("comment")}>
        <Textarea
          value={comment}
          maxLength={COMMENT_MAX}
          rows={2}
          data-testid="expense-comment"
          onChange={(e) => setComment(e.target.value)}
        />
      </FormField>
      {needApproval && amount
        ? renderApproval({
            amount,
            context: { amount, reason: "expense", category_name: category?.name ?? null },
            ownLimit: ownLimit ?? "0.00",
            allowRemote: online,
            onApproved: (a) => void commit(a),
            onClose: () => setNeedApproval(false),
          })
        : null}
      {done ? (
        <Banner tone="success" icon={Receipt} live="polite">
          <span data-testid="expense-done">{t("posExpense.done", { amount: formatMoney(done) })}</span>
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
          disabled={busy || !categories || categories.length === 0}
          onClick={() => void submit()}
          data-testid="expense-submit"
        >
          <Icon as={Receipt} size="lg" />
          {t("posExpense.submit", { amount: formatMoney(amount ?? "0.00") })}
          <Kbd keys="Enter" inverted />
        </Button>
      ) : null}
      <p className="text-[12px] text-foreground-secondary">{t("posExpense.note")}</p>
    </div>
  );
}

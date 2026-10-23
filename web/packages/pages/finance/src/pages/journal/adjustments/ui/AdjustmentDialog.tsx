/**
 * «Tuzatuvchi yozuv» dialog (07 BO-08 `adjustment.*` fields; 20 #10): filial, sana (open period, ≤ today),
 * Debet / Kredit hisobi (4 digits, ≠; stock accounts 2910/2920/2970 are not offered), summa (> 0), kontragent
 * (4010 / 6010 / 6310), tuzatilayotgan davr (optional closed month), izoh (required). Server field errors land
 * on the fields; `PERIOD_CLOSED` and the rest — in the banner.
 */
import { useUnit } from "effector-react";
import { CircleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { toApiError } from "@shared/api";
import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { isMoney } from "@shared/lib/money";
import { $activeBranchId, $branches, ALL_BRANCHES } from "@shared/state/session";
import {
  Banner,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  FormField,
  Input,
  MoneyInput,
  SearchInput,
  SimpleSelect,
  Textarea,
  toast,
} from "@shared/ui";

import { todayIso } from "#/shared/lib/effect.ts";

import { ACCOUNT_CODES, reloadRequested } from "../../model/index.ts";
import {
  COMMENT_MAX,
  adjustmentFieldErrors,
  createAdjustmentFx,
  emptyForm,
  isRegisterManaged,
  needsCounterparty,
  searchCounterpartiesFx,
  toAdjustmentBody,
  validateAdjustment,
  type AdjustmentErrors,
  type AdjustmentForm,
  type Counterparty,
} from "../model/index.ts";

/** Accounts a manual entry may use (the register-managed stock accounts are left out, 13 §2.23). */
const MANUAL_ACCOUNTS = ACCOUNT_CODES.filter((code) => !isRegisterManaged(code));

export function AdjustmentDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return open ? <AdjustmentForm onClose={onClose} /> : null;
}

function AdjustmentForm({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation("finance");
  const [branches, activeBranch, pending, reloadJournal] = useUnit([
    $branches,
    $activeBranchId,
    createAdjustmentFx.pending,
    reloadRequested,
  ]);
  const today = todayIso();
  const initialBranch =
    activeBranch && activeBranch !== ALL_BRANCHES ? activeBranch : branches.length === 1 ? branches[0]?.id : null;
  const [form, setForm] = useState<AdjustmentForm>(() => emptyForm(today, initialBranch ?? null));
  const [errors, setErrors] = useState<AdjustmentErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [counterparties, setCounterparties] = useState<Counterparty[]>([]);
  const [query, setQuery] = useState("");
  const set = (patch: Partial<AdjustmentForm>) => setForm((f) => ({ ...f, ...patch }));
  const withCounterparty = needsCounterparty(form);

  useEffect(() => {
    if (!withCounterparty) return;
    let alive = true;
    searchCounterpartiesFx(query)
      .then((list) => alive && setCounterparties(list))
      .catch(() => alive && setCounterparties([]));
    return () => {
      alive = false;
    };
  }, [withCounterparty, query]);

  const accountOptions = MANUAL_ACCOUNTS.map((code) => ({
    value: code,
    label: `${code} — ${t(`accounts.${code}`)}`,
  }));

  const submit = async () => {
    const found = validateAdjustment(form, today);
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length > 0) return;
    try {
      const done = await createAdjustmentFx(toAdjustmentBody(form));
      toast.success(t("adjustments.created", { number: done.number ?? "" }));
      reloadJournal();
      onClose();
    } catch (e) {
      const error = toApiError(e);
      const { fields, rest } = adjustmentFieldErrors(error);
      setErrors(fields);
      if (rest) setServerError(serverErrorText(error));
    }
  };

  return (
    <Dialog open onOpenChange={(next) => (next || pending ? undefined : onClose())}>
      <DialogContent data-testid="adjustment-dialog">
        <form
          className="flex flex-col gap-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <DialogHeader>
            <DialogTitle>{t("adjustments.dialogTitle")}</DialogTitle>
            <DialogDescription>{t("adjustments.dialogDescription")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField label={t("adjustments.branch")} required error={errors.branchId}>
              <SimpleSelect
                options={branches.map((b) => ({ value: b.id, label: b.name }))}
                value={form.branchId || undefined}
                placeholder={t("adjustments.branchPlaceholder")}
                onValueChange={(branchId) => set({ branchId })}
                aria-label={t("adjustments.branch")}
              />
            </FormField>
            <FormField
              label={t("adjustments.docDate")}
              required
              error={errors.docDate}
              hint={t("adjustments.docDateHint")}
            >
              <Input
                type="date"
                value={form.docDate}
                max={today}
                onChange={(e) => set({ docDate: e.target.value })}
                data-testid="adjustment-date"
              />
            </FormField>
            <FormField label={t("adjustments.accountDt")} required error={errors.accountDt}>
              <SimpleSelect
                options={accountOptions}
                value={form.accountDt || undefined}
                placeholder={t("adjustments.accountPlaceholder")}
                onValueChange={(accountDt) => set({ accountDt })}
                aria-label={t("adjustments.accountDt")}
              />
            </FormField>
            <FormField label={t("adjustments.accountKt")} required error={errors.accountKt}>
              <SimpleSelect
                options={accountOptions}
                value={form.accountKt || undefined}
                placeholder={t("adjustments.accountPlaceholder")}
                onValueChange={(accountKt) => set({ accountKt })}
                aria-label={t("adjustments.accountKt")}
              />
            </FormField>
            <FormField label={t("adjustments.amount")} required error={errors.amount}>
              <MoneyInput
                precision={2}
                value={form.amount}
                onChange={(amount) => set({ amount })}
                data-testid="adjustment-amount"
              />
            </FormField>
            <FormField
              label={t("adjustments.correctionOfPeriod")}
              error={errors.correctionOfPeriod}
              hint={t("adjustments.correctionHint")}
            >
              <Input
                type="month"
                value={form.correctionOfPeriod}
                max={today.slice(0, 7)}
                onChange={(e) => set({ correctionOfPeriod: e.target.value })}
                data-testid="adjustment-correction"
              />
            </FormField>
          </div>
          {withCounterparty ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <FormField label={t("adjustments.counterpartySearch")}>
                <SearchInput
                  value={query}
                  onSearch={setQuery}
                  placeholder={t("adjustments.counterpartySearchPlaceholder")}
                />
              </FormField>
              <FormField label={t("adjustments.counterparty")} required error={errors.counterpartyId}>
                <SimpleSelect
                  options={counterparties.map((c) => ({ value: c.id, label: c.name }))}
                  value={form.counterpartyId || undefined}
                  placeholder={t("adjustments.counterpartyPlaceholder")}
                  onValueChange={(counterpartyId) => set({ counterpartyId })}
                  aria-label={t("adjustments.counterparty")}
                />
              </FormField>
            </div>
          ) : null}
          <FormField label={t("adjustments.comment")} required error={errors.comment}>
            <Textarea
              rows={2}
              maxLength={COMMENT_MAX}
              value={form.comment}
              onChange={(e) => set({ comment: e.target.value })}
              data-testid="adjustment-comment"
            />
          </FormField>
          {form.accountDt && form.accountKt && isMoney(form.amount) ? (
            <p className="text-[13px] font-semibold" data-testid="adjustment-preview">
              {t("adjustments.preview", {
                dt: form.accountDt,
                kt: form.accountKt,
                amount: formatMoney(form.amount, { precision: 2 }),
              })}
            </p>
          ) : null}
          {serverError ? (
            <Banner tone="destructive" icon={CircleAlert} live="assertive">
              <span data-testid="adjustment-error">{serverError}</span>
            </Banner>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose} disabled={pending}>
              {t("shared.back")}
            </Button>
            <Button type="submit" disabled={pending} data-testid="adjustment-submit">
              {t("adjustments.submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

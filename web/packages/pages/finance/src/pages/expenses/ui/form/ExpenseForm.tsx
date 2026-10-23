/**
 * BO-17 «Yangi xarajat» (07 BO-17, mockup Bo17Xarajatlar right panel): amount, category → the Dt account
 * shown at once, tax type (6410 only), date, branch, source (Bank hisobi / Korporativ karta — cash is
 * POS-14), comment, receipt photo (`POST /attachments`, kind `expense_receipt`), recurrence + day of month,
 * limit note; «Qoralama» / «Saqlash va o'tkazish» (202 → «Egasi tasdig'iga yuborildi»).
 * The form state lives here (never in a store); checks and the request body are pure model functions.
 */
import { useUnit } from "effector-react";
import { CircleAlert, Info, Repeat, Send } from "lucide-react";
import { useState } from "react";

import { applyApiFieldErrors, toApiError } from "@shared/api";
import { serverErrorText, useTranslation } from "@shared/i18n";
import { $branches } from "@shared/state/session";
import {
  Banner,
  Button,
  Card,
  FormField,
  Icon,
  Input,
  MoneyInput,
  SegmentedControl,
  SimpleSelect,
  Textarea,
} from "@shared/ui";

import { AttachmentField } from "#/shared/ui/AttachmentField.tsx";

import {
  $activeCategories,
  $defaultBranchId,
  $saving,
  $today,
  COMMENT_MAX,
  FORM_SOURCES,
  PERIODS,
  TAX_TYPES,
  createExpenseFx,
  emptyForm,
  isPeriod,
  isTaxCategory,
  isTaxType,
  toSaveRequest,
  validateExpenseForm,
  type ExpenseForm as Form,
  type ExpenseFormErrors,
  type ExpenseFormField,
  type FormSource,
} from "../../model/index.ts";

const FIELDS: readonly ExpenseFormField[] = [
  "amount",
  "categoryId",
  "taxType",
  "docDate",
  "branchId",
  "comment",
  "dayOfMonth",
];
const SERVER_FIELDS: Readonly<Record<string, ExpenseFormField>> = {
  category_id: "categoryId",
  tax_type: "taxType",
  doc_date: "docDate",
  branch_id: "branchId",
  day_of_month: "dayOfMonth",
};

export function ExpenseForm({ disabled }: { disabled: boolean }) {
  const { t } = useTranslation("finance");
  const [today, defaultBranch, categories, branches, saving] = useUnit([
    $today,
    $defaultBranchId,
    $activeCategories,
    $branches,
    $saving,
  ]);
  const createExpense = useUnit(createExpenseFx);
  const [form, setForm] = useState<Form>(() => emptyForm(today, defaultBranch ?? branches[0]?.id ?? null));
  const [errors, setErrors] = useState<ExpenseFormErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const category = categories.find((c) => c.id === form.categoryId) ?? null;
  const tax = isTaxCategory(category);

  const set = <K extends keyof Form>(key: K, value: Form[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({ ...e, [key]: undefined }));
  };

  const save = async (post: boolean) => {
    if (saving || disabled) return;
    const found = validateExpenseForm(form, category, today);
    setErrors(found);
    setFailure(null);
    if (Object.keys(found).length > 0 || !category) return;
    try {
      await createExpense(toSaveRequest(form, category, post));
      setForm(emptyForm(today, form.branchId || defaultBranch));
    } catch (e) {
      const error = toApiError(e);
      const server: ExpenseFormErrors = {};
      const { unmatched } = applyApiFieldErrors(
        error,
        (name, { message }) => (server[name] = message),
        FIELDS,
        SERVER_FIELDS,
      );
      setErrors(server);
      if (unmatched.length > 0 || Object.keys(server).length === 0) setFailure(serverErrorText(error));
    }
  };

  const err = (field: ExpenseFormField) => errors[field] ?? null;

  return (
    <Card role="region" aria-labelledby="expense-form-title" className="flex flex-col gap-3.5">
      <h2 id="expense-form-title" className="text-[16px] font-extrabold">
        {t("expenses.form.title")}
      </h2>
      <FormField label={t("expenses.form.amount")} required error={err("amount")}>
        <MoneyInput
          value={form.amount}
          onChange={(v) => set("amount", v)}
          disabled={disabled}
          data-testid="expense-amount"
        />
      </FormField>
      <FormField
        label={t("expenses.form.category")}
        required
        error={err("categoryId")}
        hint={
          category
            ? t("expenses.form.accountHint", {
                code: category.default_account,
                name: t(`accounts.${category.default_account}`),
              })
            : undefined
        }
      >
        <SimpleSelect
          options={categories.map((c) => ({ value: c.id, label: c.name }))}
          value={form.categoryId || undefined}
          placeholder={t("expenses.form.categoryPlaceholder")}
          disabled={disabled}
          onValueChange={(v) => {
            set("categoryId", v);
            set("taxType", null);
          }}
        />
      </FormField>
      {tax ? (
        <FormField label={t("expenses.form.taxType")} required error={err("taxType")}>
          <SimpleSelect
            options={TAX_TYPES.map((k) => ({ value: k, label: t(`expenses.taxTypes.${k}`) }))}
            value={form.taxType ?? undefined}
            placeholder={t("expenses.form.taxTypePlaceholder")}
            disabled={disabled}
            onValueChange={(v) => set("taxType", isTaxType(v) ? v : null)}
          />
        </FormField>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <FormField label={t("expenses.form.date")} required error={err("docDate")}>
          <Input
            type="date"
            value={form.docDate}
            max={today}
            disabled={disabled}
            onChange={(e) => set("docDate", e.target.value)}
          />
        </FormField>
        {branches.length > 1 ? (
          <FormField label={t("expenses.form.branch")} required error={err("branchId")}>
            <SimpleSelect
              options={branches.map((b) => ({ value: b.id, label: b.name }))}
              value={form.branchId || undefined}
              placeholder={t("expenses.form.branchPlaceholder")}
              disabled={disabled}
              onValueChange={(v) => set("branchId", v)}
            />
          </FormField>
        ) : null}
      </div>
      <FormField label={t("expenses.form.source")} required>
        <div className="flex flex-col gap-1.5">
          <SegmentedControl<FormSource>
            label={t("expenses.form.source")}
            value={form.source}
            onChange={(v) => set("source", v)}
            options={FORM_SOURCES.map((s) => ({ value: s, label: t(`expenses.formSources.${s}`) }))}
          />
          <p className="text-[12px] text-foreground-secondary">{t("expenses.form.cashHint")}</p>
        </div>
      </FormField>
      <FormField label={t("expenses.form.comment")} optional error={err("comment")}>
        <Textarea
          value={form.comment}
          maxLength={COMMENT_MAX}
          rows={2}
          disabled={disabled}
          onChange={(e) => set("comment", e.target.value)}
        />
      </FormField>
      <FormField label={t("expenses.form.photo")} optional>
        {(a11y) => (
          <AttachmentField
            id={a11y.id}
            kind="expense_receipt"
            value={form.attachment}
            onChange={(v) => set("attachment", v)}
            disabled={disabled}
            title={t("expenses.form.photoHint")}
          />
        )}
      </FormField>
      {tax ? null : (
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label={t("expenses.form.period")}>
            <SimpleSelect
              options={PERIODS.map((p) => ({ value: p, label: t(`expenses.periods.${p}`) }))}
              value={form.period}
              disabled={disabled}
              onValueChange={(v) => set("period", isPeriod(v) ? v : "none")}
            />
          </FormField>
          {form.period !== "none" ? (
            <FormField label={t("expenses.form.dayOfMonth")} required error={err("dayOfMonth")}>
              <Input
                inputMode="numeric"
                maxLength={2}
                value={form.dayOfMonth}
                disabled={disabled}
                data-testid="expense-day"
                onChange={(e) => set("dayOfMonth", e.target.value.replace(/\D/g, ""))}
              />
            </FormField>
          ) : null}
        </div>
      )}
      {form.period !== "none" && !tax ? (
        <p className="flex items-start gap-1.5 text-[12px] text-foreground-secondary">
          <Icon as={Repeat} size="sm" />
          {t("expenses.form.recurringHint", { day: form.dayOfMonth || "—" })}
        </p>
      ) : null}
      <Banner tone="info" icon={Info}>
        {t("expenses.form.limitHint")}
      </Banner>
      {failure ? (
        <Banner tone="destructive" icon={CircleAlert} live="assertive">
          {failure}
        </Banner>
      ) : null}
      <div className="flex flex-wrap justify-end gap-2">
        <Button
          variant="outline"
          disabled={disabled || saving}
          onClick={() => void save(false)}
          data-testid="expense-save-draft"
        >
          {t("expenses.form.saveDraft")}
        </Button>
        <Button disabled={disabled || saving} onClick={() => void save(true)} data-testid="expense-save-post">
          <Icon as={Send} size="sm" />
          {t("expenses.form.savePost")}
        </Button>
      </div>
    </Card>
  );
}

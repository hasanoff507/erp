/**
 * «To'lov qayd etish» (07 BO-04; 19 §11 POST /supplier-payments): supplier, current debt (6010) and open
 * documents (oldest first, deferred VAT), method bank / cash from the till (an open shift), amount, date,
 * the allocation table — «Standart — eng eskisidan avtomatik» preview or a manual split — the overpay
 * warning «Ortiqcha {summa} avans sifatida yoziladi» (qaror #47; `block` policy → SUPPLIER_OVERPAY_BLOCKED),
 * the posting note (Dt 6010 / Kt 5110|5010, advance Dt 4310).
 */
import { useUnit } from "effector-react";
import { CircleAlert, Info } from "lucide-react";
import { useMemo, useState } from "react";

import { toApiError } from "@shared/api";
import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatDate, formatMoney } from "@shared/lib/format";
import { compareMoney, money, type Money } from "@shared/lib/money";
import type { CounterpartyListItem } from "@shared/models";
import {
  Banner,
  Button,
  FormField,
  Input,
  MoneyInput,
  SegmentedControl,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SimpleSelect,
  StatusChip,
  Switch,
  Textarea,
} from "@shared/ui";

import { createSupplierSearch, SupplierPicker, type PickedSupplier } from "#/entities/supplier/index.tsx";
import { todayIso } from "#/shared/lib/effect.ts";

import {
  $openDocs,
  $openDocsStatus,
  $openShifts,
  $paymentFormOpen,
  $paymentFormSupplier,
  COMMENT_MAX,
  PAYMENT_METHODS,
  advanceOf,
  autoAllocation,
  checkManual,
  createPaymentFx,
  paymentFormClosed,
  supplierChosen,
  toMoney,
  toPaymentBody,
  validatePayment,
  type PaymentForm,
  type PaymentFormField,
  type PaymentMethod,
} from "../model/index.ts";

const supplierSearch = createSupplierSearch();
const money2 = (v: string) => formatMoney(v, { precision: 2 });

export function PaymentSheet() {
  const { t } = useTranslation("warehouse");
  const [open, close] = useUnit([$paymentFormOpen, paymentFormClosed]);
  return (
    <Sheet open={open} onOpenChange={(next) => (next ? undefined : close())}>
      <SheetContent wide>
        <SheetHeader>
          <SheetTitle>{t("supplierPayments.form.title")}</SheetTitle>
          <SheetDescription>{t("supplierPayments.form.description")}</SheetDescription>
        </SheetHeader>
        {open ? <PaymentFormBody /> : null}
      </SheetContent>
    </Sheet>
  );
}

function PaymentFormBody() {
  const { t } = useTranslation("warehouse");
  const [preset, docs, docsStatus, shifts, pending] = useUnit([
    $paymentFormSupplier,
    $openDocs,
    $openDocsStatus,
    $openShifts,
    createPaymentFx.pending,
  ]);
  const [create, choose, close] = useUnit([createPaymentFx, supplierChosen, paymentFormClosed]);
  const today = todayIso();
  const [supplier, setSupplier] = useState<PickedSupplier | null>(null);
  const [form, setForm] = useState<PaymentForm>({
    supplierId: preset ?? "",
    method: "bank",
    shiftId: "",
    amount: "",
    docDate: today,
    manual: false,
    split: {},
    comment: "",
  });
  const [errors, setErrors] = useState<Partial<Record<PaymentFormField, string>>>({});
  const [failure, setFailure] = useState<string | null>(null);
  const set = <K extends keyof PaymentForm>(key: K, value: PaymentForm[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({
      ...e,
      [key]: undefined,
      ...(key === "split" || key === "amount" ? { allocations: undefined } : {}),
    }));
  };

  const amount = toMoney(form.amount);
  const auto = useMemo(() => (docs && amount ? autoAllocation(amount, docs) : {}), [docs, amount]);
  const advance: Money | null = docs && amount ? advanceOf(amount, docs) : null;
  const manualCheck = docs && amount && form.manual ? checkManual(form.split, amount, docs) : null;
  const shift = shifts.find((s) => s.shift.id === form.shiftId)?.shift ?? null;

  const pick = (s: CounterpartyListItem) => {
    setSupplier({ id: s.id, name: s.name, stir: s.stir });
    set("supplierId", s.id);
    set("split", {});
    choose(s.id);
  };

  const submit = async () => {
    const found = validatePayment(form, docs, today);
    setErrors(found);
    setFailure(null);
    if (Object.keys(found).length > 0) return;
    try {
      await create(toPaymentBody(form, docs, shift));
    } catch (e) {
      const error = toApiError(e);
      if (error.code === "SUPPLIER_OVERPAY_BLOCKED") {
        setFailure(
          t("supplierPayments.form.overpayBlocked", {
            debt: money2(typeof error.params.debt === "string" ? error.params.debt : "0"),
            amount: money2(
              typeof error.params.amount === "string" ? error.params.amount : form.amount || "0",
            ),
          }),
        );
        return;
      }
      const first = error.details[0];
      if (first?.field.startsWith("allocations")) setErrors({ allocations: first.messageKey });
      setFailure(serverErrorText(error));
    }
  };

  return (
    <>
      <SheetBody className="flex flex-col gap-4">
        <FormField label={t("supplierPayments.form.supplier")} required error={errors.supplierId ?? null}>
          <SupplierPicker model={supplierSearch} value={supplier} onPick={pick} />
        </FormField>
        {docs ? (
          <div
            className="flex flex-wrap gap-x-6 gap-y-1 rounded-xl bg-accent px-3 py-2.5 text-[13px]"
            data-testid="payable"
          >
            <span>
              {t("supplierPayments.form.payable")}{" "}
              <b className="tabular-nums">{money2(docs.payable_balance)}</b>
            </span>
            {compareMoney(money(docs.advance_balance), money("0")) > 0 ? (
              <span>
                {t("supplierPayments.form.advanceBalance")}{" "}
                <b className="tabular-nums">{money2(docs.advance_balance)}</b>
              </span>
            ) : null}
          </div>
        ) : null}
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label={t("supplierPayments.form.method")} required>
            <SegmentedControl<PaymentMethod>
              label={t("supplierPayments.form.method")}
              value={form.method}
              onChange={(v) => set("method", v)}
              options={PAYMENT_METHODS.map((m) => ({ value: m, label: t(`supplierPayments.methods.${m}`) }))}
            />
          </FormField>
          {form.method === "cash" ? (
            <FormField
              label={t("supplierPayments.form.shift")}
              required
              error={errors.shiftId ?? null}
              hint={shifts.length === 0 ? t("supplierPayments.form.noShift") : undefined}
            >
              <SimpleSelect
                options={shifts.map(({ shift: s, register }) => ({
                  value: s.id,
                  label: t("supplierPayments.form.shiftOption", {
                    register: register?.name ?? "—",
                    number: s.shift_no,
                  }),
                }))}
                value={form.shiftId || undefined}
                placeholder={t("supplierPayments.form.shiftPlaceholder")}
                onValueChange={(v) => set("shiftId", v)}
              />
            </FormField>
          ) : null}
          <FormField label={t("supplierPayments.form.amount")} required error={errors.amount ?? null}>
            <MoneyInput
              precision={2}
              value={form.amount}
              onChange={(v) => set("amount", v)}
              data-testid="payment-amount"
            />
          </FormField>
          <FormField label={t("supplierPayments.form.docDate")} required error={errors.docDate ?? null}>
            <Input
              type="date"
              value={form.docDate}
              max={today}
              onChange={(e) => set("docDate", e.target.value)}
            />
          </FormField>
        </div>

        {form.supplierId ? (
          <section aria-labelledby="alloc-title" className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <h3 id="alloc-title" className="min-w-0 flex-1 text-[14px] font-bold">
                {t("supplierPayments.form.allocation")}
              </h3>
              <label className="flex items-center gap-2 text-[13px]">
                <Switch
                  checked={form.manual}
                  onCheckedChange={(on) => set("manual", on)}
                  data-testid="manual-split"
                />
                {t("supplierPayments.form.manual")}
              </label>
            </div>
            <p className="text-[12px] text-foreground-secondary">
              {form.manual ? t("supplierPayments.form.manualHint") : t("supplierPayments.form.autoHint")}
            </p>
            {docsStatus === "loading" ? (
              <p className="text-small text-foreground-secondary">{t("supplierPayments.form.loadingDocs")}</p>
            ) : docs && docs.items.length === 0 ? (
              <p className="text-small text-foreground-secondary">{t("supplierPayments.form.noDocs")}</p>
            ) : docs ? (
              <div className="overflow-x-auto">
                <table
                  className="w-full min-w-[560px] text-[13px]"
                  aria-label={t("supplierPayments.form.allocation")}
                  data-testid="allocation-table"
                >
                  <thead>
                    <tr className="text-left text-[12px] text-foreground-secondary">
                      <th className="py-1.5 pr-2 font-semibold">{t("supplierPayments.columns.document")}</th>
                      <th className="py-1.5 pr-2 font-semibold">{t("supplierPayments.columns.due")}</th>
                      <th className="py-1.5 pr-2 text-right font-semibold">
                        {t("supplierPayments.columns.outstanding")}
                      </th>
                      <th className="py-1.5 text-right font-semibold">{t("supplierPayments.columns.pay")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {docs.items.map((d) => (
                      <tr key={d.target_doc_id} className="border-t border-border">
                        <td className="py-1.5 pr-2">
                          <span className="font-semibold">
                            {t(`supplierPayments.docTypes.${d.target_doc_type}`)} {d.number ?? ""}
                          </span>
                          <span className="block text-[11px] text-foreground-secondary">
                            {formatDate(d.doc_date)}
                            {d.einvoice_risk_flag && d.einvoice_risk_flag !== "green" ? (
                              <>
                                {" "}
                                <StatusChip tone="warning">
                                  {t("supplierPayments.form.vatPending", { amount: money2(d.vat_pending) })}
                                </StatusChip>
                              </>
                            ) : null}
                          </span>
                        </td>
                        <td className="py-1.5 pr-2 tabular-nums">
                          {d.due_date ? formatDate(d.due_date) : "—"}
                        </td>
                        <td className="py-1.5 pr-2 text-right tabular-nums">{money2(d.outstanding)}</td>
                        <td className="py-1.5 text-right">
                          {form.manual ? (
                            <MoneyInput
                              precision={2}
                              withCurrency={false}
                              className="ml-auto w-36 text-right"
                              aria-label={t("supplierPayments.form.payFor", { number: d.number ?? "" })}
                              aria-invalid={manualCheck?.lines[d.target_doc_id] ? true : undefined}
                              value={form.split[d.target_doc_id] ?? ""}
                              onChange={(v) => set("split", { ...form.split, [d.target_doc_id]: v })}
                            />
                          ) : (
                            <span className="font-bold tabular-nums">
                              {auto[d.target_doc_id] ? money2(auto[d.target_doc_id] ?? "0") : "—"}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            {errors.allocations ? (
              <p className="text-small text-destructive" role="alert">
                {t(
                  `supplierPayments.form.allocationErrors.${errors.allocations === "validation.allocation_sum_mismatch" ? "sum" : "exceeds"}`,
                )}
              </p>
            ) : null}
          </section>
        ) : null}

        {advance && compareMoney(advance, money("0")) > 0 ? (
          <Banner tone="warning" icon={Info}>
            <span data-testid="overpay-warning">
              {t("supplierPayments.form.overpay", { amount: money2(advance) })}
            </span>
          </Banner>
        ) : null}
        <p className="text-[12px] text-foreground-secondary">
          {t("supplierPayments.form.posting", { kt: form.method === "cash" ? "5010" : "5110" })}
        </p>
        <FormField label={t("supplierPayments.form.comment")} optional error={errors.comment ?? null}>
          <Textarea
            value={form.comment}
            rows={2}
            maxLength={COMMENT_MAX}
            onChange={(e) => set("comment", e.target.value)}
          />
        </FormField>
        {failure ? (
          <Banner tone="destructive" icon={CircleAlert} live="assertive">
            <span data-testid="payment-error">{failure}</span>
          </Banner>
        ) : null}
      </SheetBody>
      <SheetFooter>
        <Button variant="secondary" disabled={pending} onClick={() => close()}>
          {t("actions.back")}
        </Button>
        <Button disabled={pending} onClick={() => void submit()} data-testid="payment-submit">
          {t("supplierPayments.form.submit")}
        </Button>
      </SheetFooter>
    </>
  );
}

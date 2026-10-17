/**
 * Supplier create / edit form (19 §9): turi (yuridik / jismoniy shaxs), STIR (9 raqam — yuridik shaxsda
 * majburiy) with «Soliq bazasidan to'ldirish» (lookup-by-stir: a suggestion the user applies; an
 * existing supplier with the same STIR is offered instead), nomi, telefon, yuridik manzil, bank
 * hisobi, MFO, QQS to'lovchi, izoh.
 */
import { useUnit } from "effector-react";
import { Building2, Search, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { toApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import {
  Banner,
  Button,
  FormField,
  Icon,
  Input,
  Label,
  SegmentedControl,
  Switch,
  Textarea,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";

import {
  applySuggestion,
  formErrors,
  isStir,
  lookupStirFx,
  type StirSuggestion,
  type SupplierFormValues,
} from "../model/index.ts";

export interface SupplierFormProps {
  initial: SupplierFormValues;
  submitLabel: string;
  pending: boolean;
  online: boolean;
  /** Lookup is `purchases.create` (19 §9). */
  canLookup: boolean;
  onSubmit: (values: SupplierFormValues) => Promise<unknown>;
  onCancel: () => void;
  onOpenExisting: (id: string) => void;
}

export function SupplierForm({
  initial,
  submitLabel,
  pending,
  online,
  canLookup,
  onSubmit,
  onCancel,
  onOpenExisting,
}: SupplierFormProps) {
  const { t } = useTranslation("warehouse");
  const [lookup, looking] = useUnit([lookupStirFx, lookupStirFx.pending]);
  const [values, setValues] = useState(initial);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState<StirSuggestion | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);

  const errors = formErrors(values);
  const set = (patch: Partial<SupplierFormValues>) => setValues((v) => ({ ...v, ...patch }));
  const show = (key: keyof SupplierFormValues) => (submitted ? (errors[key] ?? null) : null);

  const runLookup = () => {
    setLookupError(null);
    setSuggestion(null);
    lookup(values.stir)
      .then(setSuggestion)
      .catch((e: unknown) => {
        const apiError = toApiError(e);
        setLookupError(apiError.status === 404 ? t("suppliers.lookup.notFound") : errorText(apiError));
      });
  };

  const submit = () => {
    setSubmitted(true);
    if (Object.keys(errors).length > 0) return;
    setError(null);
    onSubmit(values).catch((e: unknown) => setError(errorText(e)));
  };

  return (
    <div className="flex flex-col gap-4">
      <SegmentedControl
        label={t("suppliers.fields.kind")}
        options={[
          { value: "company", label: t("suppliers.kind.company") },
          { value: "person", label: t("suppliers.kind.person") },
        ]}
        value={values.kind}
        onChange={(kind) => set({ kind })}
      />
      <FormField
        label={t("suppliers.fields.stir")}
        required={values.kind === "company"}
        error={show("stir")}
        hint={t("suppliers.fields.stirHint")}
      >
        {(a11y) => (
          <div className="flex gap-2">
            <Input
              {...a11y}
              value={values.stir}
              inputMode="numeric"
              maxLength={9}
              autoComplete="off"
              className="tabular-nums"
              onChange={(e) => set({ stir: e.target.value.replace(/\D/g, "").slice(0, 9) })}
            />
            {canLookup ? (
              <Button
                type="button"
                variant="secondary"
                disabled={!isStir(values.stir) || looking || !online}
                aria-busy={looking || undefined}
                onClick={runLookup}
              >
                <Icon as={Search} size="sm" />
                {t("suppliers.lookup.action")}
              </Button>
            ) : null}
          </div>
        )}
      </FormField>
      {lookupError ? (
        <Banner tone="warning" icon={TriangleAlert}>
          {lookupError}
        </Banner>
      ) : null}
      {suggestion ? (
        <div
          role="region"
          aria-label={t("suppliers.lookup.found")}
          className="flex flex-col gap-2 rounded-lg border border-primary bg-primary-soft/40 px-4 py-3"
        >
          <p className="flex items-center gap-2 text-[14px] font-bold">
            <Icon as={Building2} size="sm" />
            {suggestion.name}
          </p>
          <p className="text-small text-foreground-secondary">
            {[
              suggestion.legal_address,
              suggestion.bank_account
                ? t("suppliers.lookup.bank", {
                    account: suggestion.bank_account,
                    mfo: suggestion.bank_mfo ?? "",
                  })
                : null,
              suggestion.director_name
                ? t("suppliers.lookup.director", { name: suggestion.director_name })
                : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          {suggestion.existing_counterparty_id ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-small font-semibold text-warning-strong">
                {t("suppliers.lookup.exists")}
              </span>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => onOpenExisting(suggestion.existing_counterparty_id ?? "")}
              >
                {t("suppliers.lookup.openExisting")}
              </Button>
            </div>
          ) : (
            <div>
              <Button
                type="button"
                size="sm"
                onClick={() => {
                  setValues((v) => applySuggestion(v, suggestion));
                  setSuggestion(null);
                }}
              >
                {t("suppliers.lookup.apply")}
              </Button>
            </div>
          )}
        </div>
      ) : null}
      <FormField label={t("suppliers.fields.name")} required error={show("name")}>
        <Input value={values.name} maxLength={255} onChange={(e) => set({ name: e.target.value })} />
      </FormField>
      <FormField label={t("suppliers.fields.phone")} optional>
        <Input
          value={values.phone}
          inputMode="tel"
          maxLength={20}
          onChange={(e) => set({ phone: e.target.value })}
        />
      </FormField>
      <FormField label={t("suppliers.fields.legalAddress")} optional>
        <Input
          value={values.legalAddress}
          maxLength={500}
          onChange={(e) => set({ legalAddress: e.target.value })}
        />
      </FormField>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t("suppliers.fields.bankAccount")} optional>
          <Input
            value={values.bankAccount}
            inputMode="numeric"
            maxLength={64}
            onChange={(e) => set({ bankAccount: e.target.value })}
          />
        </FormField>
        <FormField label={t("suppliers.fields.bankMfo")} optional>
          <Input
            value={values.bankMfo}
            inputMode="numeric"
            maxLength={64}
            onChange={(e) => set({ bankMfo: e.target.value })}
          />
        </FormField>
      </div>
      <span className="flex items-center gap-2">
        <Switch
          id="supplier-vat"
          checked={values.vatPayer}
          onCheckedChange={(vatPayer) => set({ vatPayer })}
        />
        <Label htmlFor="supplier-vat">{t("suppliers.fields.vatPayer")}</Label>
      </span>
      <FormField label={t("suppliers.fields.note")} optional>
        <Textarea
          value={values.note}
          rows={2}
          maxLength={1000}
          onChange={(e) => set({ note: e.target.value })}
        />
      </FormField>
      {error ? (
        <Banner tone="destructive" icon={TriangleAlert} live="assertive">
          {error}
        </Banner>
      ) : null}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="secondary" disabled={pending} onClick={onCancel}>
          {t("actions.back")}
        </Button>
        <Button disabled={pending || !online} aria-busy={pending || undefined} onClick={submit}>
          {submitLabel}
        </Button>
      </div>
    </div>
  );
}

/**
 * «Mijoz kartasi» Sheet (07 BO-06): requisites for B2B e-invoices, credit limit (empty = no limit), standing
 * discount, notification consent. Read-only without `debts.limit.manage`.
 */
import { CircleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { useTranslation } from "@shared/i18n";
import type { CounterpartyOut } from "@shared/models";
import {
  Banner,
  Button,
  DecimalInput,
  ErrorState,
  FormField,
  Input,
  MoneyInput,
  NativeSelect,
  PhoneInput,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  Skeleton,
  Switch,
  toast,
} from "@shared/ui";

import { errorText, fieldError } from "#/shared/lib/errors.ts";

import {
  loadCardFx,
  saveCardFx,
  toCardForm,
  toCardPatch,
  validateCard,
  type CardErrors,
  type CardForm,
} from "../model/index.ts";

export interface CustomerCardSheetProps {
  counterpartyId: string;
  canEdit: boolean;
  onClose: () => void;
}

export function CustomerCardSheet({ counterpartyId, canEdit, onClose }: CustomerCardSheetProps) {
  const { t } = useTranslation("debts");
  const [card, setCard] = useState<CounterpartyOut | null>(null);
  const [form, setForm] = useState<CardForm | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [errors, setErrors] = useState<CardErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let alive = true;
    loadCardFx(counterpartyId)
      .then((c) => {
        if (!alive) return;
        setCard(c);
        setForm(toCardForm(c));
        setLoadError(null);
      })
      .catch((e: unknown) => alive && setLoadError(errorText(e)));
    return () => {
      alive = false;
    };
  }, [counterpartyId, attempt]);

  const set = (patch: Partial<CardForm>) => setForm((f) => (f ? { ...f, ...patch } : f));

  const save = async () => {
    if (!form || !card) return;
    const found = validateCard(form);
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length > 0) return;
    setSaving(true);
    try {
      const saved = await saveCardFx({ id: card.id, patch: toCardPatch(form, card) });
      setCard(saved);
      setForm(toCardForm(saved));
      toast.success(t("card.saved"));
    } catch (e) {
      setServerError(errorText(e));
    } finally {
      setSaving(false);
    }
  };

  const disabled = !canEdit || saving;
  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent data-testid="customer-card">
        <SheetHeader>
          <SheetTitle>{t("card.title")}</SheetTitle>
          <SheetDescription>{card?.name ?? t("ledger.loading")}</SheetDescription>
        </SheetHeader>
        <SheetBody>
          {loadError ? <ErrorState message={loadError} onRetry={() => setAttempt((n) => n + 1)} /> : null}
          {!form && !loadError ? <Skeleton className="h-64" /> : null}
          {form ? (
            <form
              id="customer-card-form"
              className="flex flex-col gap-3"
              onSubmit={(e) => {
                e.preventDefault();
                void save();
              }}
            >
              <FormField label={t("card.name")} required error={fieldError(errors.name)}>
                <Input
                  value={form.name}
                  maxLength={255}
                  onChange={(e) => set({ name: e.target.value })}
                  disabled={disabled}
                />
              </FormField>
              <div className="grid grid-cols-2 gap-3">
                <FormField label={t("card.phone")} required error={fieldError(errors.phone)}>
                  <PhoneInput value={form.phone} onChange={(phone) => set({ phone })} disabled={disabled} />
                </FormField>
                <FormField label={t("card.kind")}>
                  <NativeSelect
                    value={form.kind}
                    onChange={(e) => set({ kind: e.target.value === "company" ? "company" : "person" })}
                    options={[
                      { value: "person", label: t("card.kinds.person") },
                      { value: "company", label: t("card.kinds.company") },
                    ]}
                    disabled={disabled}
                  />
                </FormField>
              </div>
              <FormField label={t("card.stir")} optional error={fieldError(errors.stir)}>
                <Input
                  value={form.stir}
                  maxLength={14}
                  inputMode="numeric"
                  onChange={(e) => set({ stir: e.target.value.replace(/\D+/g, "") })}
                  disabled={disabled}
                />
              </FormField>
              <FormField label={t("card.legalAddress")} optional>
                <Input
                  value={form.legalAddress}
                  maxLength={500}
                  onChange={(e) => set({ legalAddress: e.target.value })}
                  disabled={disabled}
                />
              </FormField>
              <div className="grid grid-cols-2 gap-3">
                <FormField label={t("card.bankAccount")} optional>
                  <Input
                    value={form.bankAccount}
                    maxLength={20}
                    inputMode="numeric"
                    onChange={(e) => set({ bankAccount: e.target.value.replace(/\D+/g, "") })}
                    disabled={disabled}
                  />
                </FormField>
                <FormField label={t("card.bankMfo")} optional>
                  <Input
                    value={form.bankMfo}
                    maxLength={5}
                    inputMode="numeric"
                    onChange={(e) => set({ bankMfo: e.target.value.replace(/\D+/g, "") })}
                    disabled={disabled}
                  />
                </FormField>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <FormField
                  label={t("card.creditLimit")}
                  hint={t("card.creditLimitHint")}
                  error={fieldError(errors.creditLimit)}
                >
                  <MoneyInput
                    value={form.creditLimit}
                    onChange={(creditLimit) => set({ creditLimit })}
                    disabled={disabled}
                    data-testid="card-limit"
                  />
                </FormField>
                <FormField label={t("card.discount")} error={fieldError(errors.discountPct)}>
                  <DecimalInput
                    value={form.discountPct}
                    onChange={(discountPct) => set({ discountPct })}
                    precision={2}
                    outputScale={2}
                    suffix="%"
                    disabled={disabled}
                  />
                </FormField>
              </div>
              <label className="flex items-center gap-3 text-[14px]">
                <Switch
                  checked={form.notifyConsent}
                  onCheckedChange={(v) => set({ notifyConsent: v })}
                  disabled={disabled}
                />
                {t("card.notifyConsent")}
              </label>
              {serverError ? (
                <Banner tone="destructive" icon={CircleAlert} live="assertive">
                  <span data-testid="card-error">{serverError}</span>
                </Banner>
              ) : null}
            </form>
          ) : null}
        </SheetBody>
        <SheetFooter>
          <Button variant="secondary" onClick={onClose}>
            {t("actions.close")}
          </Button>
          {canEdit ? (
            <Button
              type="submit"
              form="customer-card-form"
              disabled={saving || !form}
              data-testid="card-save"
            >
              {t("card.save")}
            </Button>
          ) : null}
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

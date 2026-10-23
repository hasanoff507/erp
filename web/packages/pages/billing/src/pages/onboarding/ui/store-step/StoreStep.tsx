/**
 * BO-21 ② (07 fields `storeName`, `businessType`, `legalForm`, `acceptTerms`, `aiCrossBorderConsent`).
 * «Davom» = POST /auth/signup: the tenant is created here (before ③–⑥). The terms checkbox gates the
 * button and links the current `terms` text from GET /auth/terms; the trial dates sit under it.
 */
import { useUnit } from "effector-react";
import { ShieldCheck, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate } from "@shared/lib/format";
import {
  Banner,
  Checkbox,
  ErrorState,
  Icon,
  Input,
  RadioCard,
  RadioGroup,
  SimpleSelect,
  Skeleton,
} from "@shared/ui";
import { Controller, RhfField, useWatch, useZodForm, z } from "@shared/ui/form";

import { errorText, fieldError } from "#/shared/lib/errors.ts";

import {
  $signupError,
  $signupFailure,
  $storeDraft,
  $termsError,
  $termsVersion,
  BUSINESS_TYPES,
  DEFAULT_STORE,
  LEGAL_FORMS,
  backClicked,
  loadTermsFx,
  signupFx,
  storeDraftChanged,
  storeSubmitted,
  termsReloadRequested,
  trialPeriod,
} from "../../model/index.ts";
import { StepFooter } from "../footer/StepFooter.tsx";

const schema = z.object({
  storeName: z.string().trim().min(2).max(100),
  businessType: z.enum(["retail", "other"]),
  legalForm: z.enum(["llc", "jsc", "private_enterprise", "sole_proprietor"]),
  acceptTerms: z.boolean().refine((v) => v, { message: "validation.terms_required" }),
  aiCrossBorderConsent: z.boolean(),
});

export function StoreStep() {
  const { t } = useTranslation("onboarding");
  const { t: tc } = useTranslation();
  const [
    draft,
    terms,
    termsError,
    termsLoading,
    signupError,
    failure,
    pending,
    submit,
    saveDraft,
    back,
    reloadTerms,
  ] = useUnit([
    $storeDraft,
    $termsVersion,
    $termsError,
    loadTermsFx.pending,
    $signupError,
    $signupFailure,
    signupFx.pending,
    storeSubmitted,
    storeDraftChanged,
    backClicked,
    termsReloadRequested,
  ]);
  const form = useZodForm(schema, { defaultValues: draft ?? DEFAULT_STORE });
  const accepted = useWatch({ control: form.control, name: "acceptTerms" });
  const [today] = useState(() => new Date());
  const trial = trialPeriod(today);

  const onSubmit = form.handleSubmit((values) => submit({ ...values, storeName: values.storeName.trim() }));
  const goBack = () => {
    const values = form.getValues();
    saveDraft({ ...DEFAULT_STORE, ...values });
    back();
  };

  return (
    <form className="flex flex-col gap-4" onSubmit={(e) => void onSubmit(e)} noValidate aria-busy={pending}>
      <section className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-5 shadow-card md:px-6">
        <div className="grid gap-4 md:grid-cols-2">
          <RhfField
            control={form.control}
            name="storeName"
            label={t("store.storeName")}
            required
            hint={t("store.storeNameHint")}
            render={({ field, control }) => (
              <Input
                {...control}
                {...field}
                aria-invalid={
                  control["aria-invalid"] ?? (fieldError(signupError, "store_name") ? true : undefined)
                }
                maxLength={100}
                autoComplete="organization"
                autoFocus
              />
            )}
          />
          <RhfField
            control={form.control}
            name="businessType"
            label={t("store.businessType")}
            required
            hint={t("store.businessTypeHint")}
            render={({ field, control }) => (
              <SimpleSelect
                {...control}
                ref={field.ref}
                name={field.name}
                value={field.value}
                onBlur={field.onBlur}
                onValueChange={(v) => field.onChange(v)}
                options={BUSINESS_TYPES.map((value) => ({ value, label: t(`store.businessTypes.${value}`) }))}
              />
            )}
          />
          <fieldset className="flex flex-col gap-1.5 md:col-span-2">
            <legend className="mb-1.5 text-label text-foreground-secondary">
              {t("store.legalForm")}
              <span aria-hidden="true" className="ml-0.5 text-destructive">
                *
              </span>
            </legend>
            <Controller
              control={form.control}
              name="legalForm"
              render={({ field }) => (
                <RadioGroup
                  value={field.value}
                  onValueChange={(v) => field.onChange(v)}
                  aria-label={t("store.legalForm")}
                  className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4"
                >
                  {LEGAL_FORMS.map((value) => (
                    <RadioCard
                      key={value}
                      value={value}
                      title={t(`store.legalForms.${value}.title`)}
                      description={t(`store.legalForms.${value}.note`)}
                    />
                  ))}
                </RadioGroup>
              )}
            />
          </fieldset>
        </div>
        {fieldError(signupError, "store_name", "business_type", "legal_form") ? (
          <p role="alert" className="text-small font-semibold text-destructive">
            {fieldError(signupError, "store_name", "business_type", "legal_form")}
          </p>
        ) : null}

        <div className="flex flex-col gap-3 border-t border-border pt-4">
          {termsLoading && !terms ? (
            <Skeleton className="h-6 w-2/3" aria-label={t("store.termsLoading")} />
          ) : termsError && !terms ? (
            <ErrorState message={t("store.termsFailed")} onRetry={() => reloadTerms()} />
          ) : (
            <Controller
              control={form.control}
              name="acceptTerms"
              render={({ field, fieldState }) => (
                <div className="flex flex-col gap-1">
                  <label className="flex items-start gap-3 text-[14px]">
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={(v) => field.onChange(v === true)}
                      onBlur={field.onBlur}
                      aria-required="true"
                      aria-invalid={fieldState.invalid || failure === "terms_outdated" || undefined}
                      className="mt-0.5"
                    />
                    <span>
                      <b>{t("store.acceptTerms")}</b> <span className="text-destructive">*</span> —{" "}
                      {terms ? (
                        <a href={terms.text_url} target="_blank" rel="noreferrer">
                          {t("store.termsLink", {
                            version: terms.version,
                            date: formatDate(terms.effective_from),
                          })}
                        </a>
                      ) : null}{" "}
                      {t("store.termsRead")}
                    </span>
                  </label>
                  {failure === "terms_outdated" ? (
                    <p role="alert" className="pl-8 text-small font-semibold text-destructive">
                      {t("store.termsChanged")}
                    </p>
                  ) : null}
                </div>
              )}
            />
          )}
          <Controller
            control={form.control}
            name="aiCrossBorderConsent"
            render={({ field }) => (
              <label className="flex items-start gap-3 text-[14px]">
                <Checkbox
                  checked={field.value}
                  onCheckedChange={(v) => field.onChange(v === true)}
                  className="mt-0.5"
                />
                <span className="flex flex-col gap-1">
                  <span>
                    <b>{t("store.aiConsent")}</b>{" "}
                    <span className="text-muted-foreground">· {tc("ui.field.optional")}</span>
                  </span>
                  <span className="text-[12px] leading-normal text-muted-foreground">
                    {t("store.aiConsentHint")}
                  </span>
                </span>
              </label>
            )}
          />
        </div>
      </section>

      <Banner tone="info" icon={ShieldCheck}>
        {t("store.trialNote", { from: formatDate(trial.from), to: formatDate(trial.to) })}
      </Banner>
      {signupError &&
      (failure === "general" || failure === "fields") &&
      !fieldError(signupError, "store_name", "business_type", "legal_form") ? (
        <Banner tone="destructive" icon={TriangleAlert} live="assertive">
          {errorText(signupError)}
        </Banner>
      ) : null}
      {pending ? (
        <p role="status" className="flex items-center gap-2 text-[13px] text-foreground-secondary">
          <Icon as={ShieldCheck} size="sm" />
          {t("store.creating")}
        </p>
      ) : null}

      <StepFooter onBack={goBack} pending={pending} primaryDisabled={!accepted || !terms} />
    </form>
  );
}

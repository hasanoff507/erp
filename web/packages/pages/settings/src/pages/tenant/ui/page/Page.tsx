import { useUnit } from "effector-react";
import { Store, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { toApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { formatDate, formatDateTime } from "@shared/lib/date";
import { useCan } from "@shared/state/permissions";
import {
  Banner,
  Button,
  Card,
  ErrorState,
  Icon,
  Input,
  MoneyInput,
  NoPermissionState,
  Skeleton,
  StatusChip,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  toast,
} from "@shared/ui";
import { RhfField, useZodForm, z, zDecimal } from "@shared/ui/form";

import { applyServerErrors } from "#/shared/lib/form.ts";
import { errorText } from "#/shared/lib/errors.ts";
import { NextStageCard, PageHeader } from "#/shared/ui/PageHeader.tsx";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $settings,
  $settingsError,
  LEGAL_FORMS,
  TENANT_FIELD_TAB,
  TENANT_TABS,
  buildPatch,
  firstErrorField,
  pageMounted,
  settingsReloadRequested,
  tabsWithErrors,
  toFormValues,
  updateSettingsFx,
  type TenantFormValues,
  type TenantSettings,
  type TenantTab,
} from "../../model/index.ts";
import { AiConsentCard } from "../AiConsentCard.tsx";
import { TaxRegimeCard } from "../TaxRegimeCard.tsx";
import { SegmentField, SelectField, SwitchField } from "../fields.tsx";

const digits = (max: number, exact?: number) =>
  z
    .string()
    .trim()
    .refine(
      (v) =>
        v === "" ||
        ([...v].every((c) => c >= "0" && c <= "9") && (exact ? v.length === exact : v.length <= max)),
      {
        message: "validation.invalid_format",
      },
    );

const schema = z.object({
  name: z.string().trim().min(2).max(100),
  legalForm: z.enum(["llc", "jsc", "private_enterprise", "sole_proprietor"]),
  bankAccount: digits(20, 20),
  bankMfo: digits(9),
  vatDiffToleranceAmount: zDecimal({ scale: 2 }),
  discountPosting: z.enum(["gross_9050", "net"]),
  ownerWithdrawalAccount: z.enum(["4890", "8720"]),
  paymentOrgCommissionAccount: z.enum(["9430", "9410"]),
  turnoverTaxAccount: z.enum(["9430", "9820"]),
  markingPrecheck: z.enum(["off", "warn", "block"]),
  negativeStockPolicy: z.enum(["allow", "block"]),
  debtReceiptSplit: z.enum(["single", "per_sale"]),
  creditSaleReceipt: z.enum(["none", "credit_type"]),
  supplierOverpayPolicy: z.enum(["warn", "block"]),
  aiTrainingConsent: z.boolean(),
}) satisfies z.ZodType<TenantFormValues>;

const SERVER_FIELDS: Readonly<Record<string, keyof TenantFormValues>> = {
  legal_form: "legalForm",
  "settings.bank_account": "bankAccount",
  "settings.bank_mfo": "bankMfo",
  "settings.vat_diff_tolerance_amount": "vatDiffToleranceAmount",
  "settings.discount_posting": "discountPosting",
  "settings.owner_withdrawal_account": "ownerWithdrawalAccount",
  "settings.payment_org_commission_account": "paymentOrgCommissionAccount",
  "settings.turnover_tax_account": "turnoverTaxAccount",
  "settings.marking_precheck": "markingPrecheck",
  "settings.negative_stock_policy": "negativeStockPolicy",
  "settings.supplier_overpay_policy": "supplierOverpayPolicy",
  "settings.ai_training_consent": "aiTrainingConsent",
};

function isTab(value: string | null): value is TenantTab {
  return value !== null && (TENANT_TABS as readonly string[]).includes(value);
}

/**
 * BO-14 — Tenant/do'kon sozlamalari, Bosqich 1 part (07, route /app/settings/tenant, `settings.tenant`
 * — owner only): name, legal form, bank details, the tenant policies of 20 #40b, tax regime (#40c),
 * AI cross-border consent (#40h). Integrations, costing method, scales, store agent, receipt template and
 * sync exceptions are later stages and shown as disabled sections.
 */
function TenantPage() {
  const { t } = useTranslation("settings");
  const canTenant = useCan({ permission: "settings.tenant" });
  const [settings, error, mounted, reload] = useUnit([
    $settings,
    $settingsError,
    pageMounted,
    settingsReloadRequested,
  ]);

  useEffect(() => {
    if (canTenant) mounted();
  }, [mounted, canTenant]);

  const header = (actions?: ReactNode) => (
    <PageHeader title={t("tenant.title")} description={t("tenant.description")} actions={actions} />
  );

  if (!canTenant || error?.status === 403) {
    return (
      <div className="flex flex-col gap-[18px]">
        {header()}
        <NoPermissionState />
      </div>
    );
  }
  if (error && !settings) {
    return (
      <div className="flex flex-col gap-[18px]">
        {header()}
        <ErrorState message={errorText(error)} onRetry={reload} />
      </div>
    );
  }
  if (!settings) {
    return (
      <div className="flex flex-col gap-[18px]" aria-busy="true">
        {header()}
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  return <TenantForm settings={settings} header={header} />;
}

function TenantForm({
  settings,
  header,
}: {
  settings: TenantSettings;
  header: (actions?: ReactNode) => ReactNode;
}) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const online = useOnline();
  const [update, saving, reload] = useUnit([
    updateSettingsFx,
    updateSettingsFx.pending,
    settingsReloadRequested,
  ]);
  const [params, setParams] = useSearchParams();
  const [formError, setFormError] = useState<{ text: string; conflict: boolean } | null>(null);
  const base = toFormValues(settings);
  const form = useZodForm(schema, {
    defaultValues: base,
    values: base,
    resetOptions: { keepDirtyValues: true },
  });
  const requested = params.get("tab");
  const tab: TenantTab = isTab(requested) ? requested : "shop";
  const dirty = form.formState.isDirty;
  // Reading `errors` here subscribes the form state: tabs with errors get a marker + summary banner.
  const errorTabs = tabsWithErrors(Object.keys(form.formState.errors));
  const showTab = (next: TenantTab) => setParams({ tab: next }, { replace: true });

  /**
   * One form spans six tabs and Radix unmounts the inactive ones (WEB-03): after a failed validation
   * (client or server) switch to the first tab with an error and focus its first errored field.
   */
  const [focusRequest, setFocusRequest] = useState<{ field: keyof TenantFormValues } | null>(null);
  const revealErrors = (fields: readonly string[]) => {
    const [first] = tabsWithErrors(fields);
    const field = firstErrorField(fields);
    if (!first) return;
    if (first !== tab) showTab(first);
    if (field) setFocusRequest({ field });
  };
  // Focus after the tab with the error has been rendered (its fields are mounted only then).
  // The URL (tab) update may commit after the request, so wait for the field's tab; focus each request once.
  const { setFocus } = form;
  const focused = useRef<object | null>(null);
  useEffect(() => {
    if (!focusRequest || focused.current === focusRequest) return;
    if (TENANT_FIELD_TAB[focusRequest.field] !== tab) return;
    focused.current = focusRequest;
    // The newly shown tab panel may still be settling (Radix presence / tab focus) in this commit:
    // focus on the next frame and retry for a few frames until the field really holds focus.
    const { field } = focusRequest;
    let frames = 0;
    let frame = 0;
    const attempt = () => {
      setFocus(field);
      const active = document.activeElement;
      if (active instanceof HTMLElement && active.getAttribute("name") === field) return;
      if (++frames < 10) frame = requestAnimationFrame(attempt);
    };
    frame = requestAnimationFrame(attempt);
    return () => cancelAnimationFrame(frame);
  }, [focusRequest, tab, setFocus]);

  const save = form.handleSubmit(
    async (values) => {
      setFormError(null);
      const patch = buildPatch(base, values, settings.version);
      if (!patch) return;
      try {
        await update(patch);
        form.reset(values);
        toast.success(t("tenant.saved"));
      } catch (e) {
        const apiError = toApiError(e);
        if (apiError.code === "VERSION_CONFLICT") {
          setFormError({ text: errorText(apiError), conflict: true });
          return;
        }
        const rest = applyServerErrors(form, apiError, SERVER_FIELDS);
        if (rest) setFormError({ text: rest, conflict: false });
        revealErrors(
          (Object.keys(base) as (keyof TenantFormValues)[]).filter((f) => form.getFieldState(f).error),
        );
      }
    },
    (errors) => {
      setFormError(null);
      revealErrors(Object.keys(errors));
    },
  );

  const actions = (
    <>
      <Button variant="secondary" disabled={!dirty || saving} onClick={() => form.reset(base)}>
        {tc("actions.cancel")}
      </Button>
      <Button disabled={!online || !dirty || saving} onClick={() => void save()}>
        {tc("actions.save")}
      </Button>
    </>
  );

  const control = form.control;
  const opt = <V extends string>(values: readonly V[], key: (v: V) => string) =>
    values.map((value) => ({ value, label: key(value) }));
  const integrations = settings.integrations;
  const integrationRows: { key: string; label: string; connected: boolean; detail?: string }[] = [
    { key: "ofd", label: t("tenant.integrations.ofd"), connected: integrations.ofd.status === "connected" },
    { key: "faktura", label: "Faktura.uz", connected: integrations.faktura_uz.status === "connected" },
    {
      key: "crpt",
      label: t("tenant.integrations.crpt"),
      connected: integrations.crpt.status === "connected",
      detail: integrations.crpt.key_last4 ? `•••• ${integrations.crpt.key_last4}` : undefined,
    },
    { key: "click", label: "Click", connected: integrations.click.status === "connected" },
    { key: "payme", label: "Payme", connected: integrations.payme.status === "connected" },
    { key: "uzum", label: "Uzum", connected: integrations.uzum.status === "connected" },
    { key: "uzqr", label: "UzQR", connected: integrations.uzqr.status === "connected" },
  ];

  return (
    <div className="flex flex-col gap-[18px]">
      {header(actions)}
      {formError ? (
        <Banner
          tone="destructive"
          icon={TriangleAlert}
          live="assertive"
          action={
            formError.conflict ? (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  setFormError(null);
                  form.reset(base);
                  reload();
                }}
              >
                {tc("actions.reload")}
              </Button>
            ) : undefined
          }
        >
          {formError.text}
        </Banner>
      ) : null}
      {errorTabs.length > 0 ? (
        <Banner tone="destructive" icon={TriangleAlert} live="polite">
          {t("tenant.errorsInTabs", { tabs: errorTabs.map((key) => t(`tenant.tabs.${key}`)).join(", ") })}
        </Banner>
      ) : null}
      <Tabs value={tab} onValueChange={(value) => (isTab(value) ? showTab(value) : undefined)}>
        <TabsList aria-label={t("tenant.tabs.label")}>
          {TENANT_TABS.map((key) => (
            <TabsTrigger key={key} value={key}>
              {t(`tenant.tabs.${key}`)}
              {errorTabs.includes(key) ? (
                <>
                  <span
                    aria-hidden="true"
                    className="ml-1.5 inline-block size-1.5 rounded-full bg-destructive"
                  />
                  <span className="sr-only"> ({t("tenant.tabs.hasErrors")})</span>
                </>
              ) : null}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="shop" className="mt-3.5">
          <Card className="flex flex-col gap-4">
            <div className="grid gap-4 md:grid-cols-2">
              <RhfField
                control={control}
                name="name"
                label={t("tenant.fields.storeName")}
                required
                render={({ field, control: a11y }) => (
                  <Input {...a11y} {...field} maxLength={100} disabled={!online} />
                )}
              />
              <SelectField
                control={control}
                name="legalForm"
                label={t("tenant.fields.legalForm")}
                options={opt(LEGAL_FORMS, (v) => t(`tenant.legalForm.${v}`))}
                disabled={!online}
              />
              <RhfField
                control={control}
                name="bankAccount"
                label={t("tenant.fields.bankAccount")}
                optional
                hint={t("tenant.fields.bankAccountHint")}
                render={({ field, control: a11y }) => (
                  <Input {...a11y} {...field} inputMode="numeric" maxLength={20} disabled={!online} />
                )}
              />
              <RhfField
                control={control}
                name="bankMfo"
                label={t("tenant.fields.bankMfo")}
                optional
                render={({ field, control: a11y }) => (
                  <Input {...a11y} {...field} inputMode="numeric" maxLength={9} disabled={!online} />
                )}
              />
            </div>
            <dl className="grid gap-x-6 gap-y-1 text-[13px] sm:grid-cols-[max-content_1fr]">
              <dt className="text-foreground-secondary">{t("tenant.fields.goLiveDate")}</dt>
              <dd>{settings.go_live_date ? formatDate(settings.go_live_date) : "—"}</dd>
              <dt className="text-foreground-secondary">{t("tenant.fields.acceptedTerms")}</dt>
              <dd>
                {settings.accepted_terms_version
                  ? t("tenant.fields.acceptedTermsValue", {
                      version: settings.accepted_terms_version,
                      at: settings.accepted_terms_at ? formatDateTime(settings.accepted_terms_at) : "—",
                    })
                  : "—"}
              </dd>
            </dl>
          </Card>
        </TabsContent>

        <TabsContent value="tax" className="mt-3.5 flex flex-col gap-3.5">
          <TaxRegimeCard settings={settings} />
          <Card className="flex flex-col gap-4">
            <h3 className="text-[15px] font-bold">{t("tenant.accounting.title")}</h3>
            <RhfField
              control={control}
              name="vatDiffToleranceAmount"
              label={t("tenant.fields.vatDiffTolerance")}
              required
              hint={t("tenant.fields.vatDiffToleranceHint")}
              className="max-w-xs"
              render={({ field, control: a11y }) => (
                <MoneyInput
                  {...a11y}
                  ref={field.ref}
                  name={field.name}
                  value={field.value}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                  precision={2}
                  disabled={!online}
                />
              )}
            />
            <div className="grid gap-4 md:grid-cols-2">
              <SelectField
                control={control}
                name="turnoverTaxAccount"
                label={t("tenant.fields.turnoverTaxAccount")}
                options={opt(["9430", "9820"] as const, (v) => t(`tenant.accounts.${v}`))}
                disabled={!online}
              />
              <SelectField
                control={control}
                name="discountPosting"
                label={t("tenant.fields.discountPosting")}
                options={opt(["gross_9050", "net"] as const, (v) => t(`tenant.discountPosting.${v}`))}
                disabled={!online}
              />
              <SelectField
                control={control}
                name="ownerWithdrawalAccount"
                label={t("tenant.fields.ownerWithdrawalAccount")}
                options={opt(["4890", "8720"] as const, (v) => t(`tenant.accounts.${v}`))}
                disabled={!online}
              />
              <SelectField
                control={control}
                name="paymentOrgCommissionAccount"
                label={t("tenant.fields.paymentOrgCommissionAccount")}
                options={opt(["9430", "9410"] as const, (v) => t(`tenant.accounts.${v}`))}
                disabled={!online}
              />
            </div>
          </Card>
          <NextStageCard title={t("tenant.costing.title")} description={t("tenant.costing.description")} />
        </TabsContent>

        <TabsContent value="integrations" className="mt-3.5 flex flex-col gap-3.5">
          <Card className="flex flex-col gap-2">
            <h3 className="text-[15px] font-bold">
              {t("tenant.integrations.summary", {
                connected: integrationRows.filter((r) => r.connected).length,
                total: integrationRows.length,
              })}
            </h3>
            <ul className="flex flex-col divide-y divide-divider">
              {integrationRows.map((row) => (
                <li key={row.key} className="flex flex-wrap items-center gap-2 py-2.5">
                  <span className="min-w-0 flex-1 text-[14px] font-semibold">{row.label}</span>
                  {row.detail ? (
                    <span className="text-[12px] text-muted-foreground">{row.detail}</span>
                  ) : null}
                  <StatusChip tone={row.connected ? "success" : "warning"} dot>
                    {row.connected
                      ? t("tenant.integrations.connected")
                      : t("tenant.integrations.notConnected")}
                  </StatusChip>
                </li>
              ))}
            </ul>
          </Card>
          <NextStageCard
            title={t("tenant.integrations.keysTitle")}
            description={t("tenant.integrations.keysDescription")}
          />
          <NextStageCard title={t("tenant.onec.title")} description={t("tenant.onec.description")} />
        </TabsContent>

        <TabsContent value="fiscal" className="mt-3.5 flex flex-col gap-3.5">
          <Card className="flex flex-col gap-4">
            <SegmentField
              control={control}
              name="markingPrecheck"
              label={t("tenant.fields.markingPrecheck")}
              hint={t("tenant.fields.markingPrecheckHint")}
              options={opt(["off", "warn", "block"] as const, (v) => t(`tenant.markingPrecheck.${v}`))}
              disabled={!online}
            />
            <SegmentField
              control={control}
              name="negativeStockPolicy"
              label={t("tenant.fields.negativeStockPolicy")}
              options={opt(["allow", "block"] as const, (v) => t(`tenant.negativeStock.${v}`))}
              disabled={!online}
            />
            <div className="grid gap-4 md:grid-cols-2">
              <SelectField
                control={control}
                name="debtReceiptSplit"
                label={t("tenant.fields.debtReceiptSplit")}
                options={opt(["single", "per_sale"] as const, (v) => t(`tenant.debtReceiptSplit.${v}`))}
                disabled={!online}
              />
              <SelectField
                control={control}
                name="creditSaleReceipt"
                label={t("tenant.fields.creditSaleReceipt")}
                options={opt(["none", "credit_type"] as const, (v) => t(`tenant.creditSaleReceipt.${v}`))}
                disabled={!online}
              />
            </div>
          </Card>
          <NextStageCard title={t("tenant.agent.title")} description={t("tenant.agent.description")} />
          <NextStageCard title={t("tenant.scales.title")} description={t("tenant.scales.description")} />
        </TabsContent>

        <TabsContent value="receipt" className="mt-3.5">
          <NextStageCard title={t("tenant.receipt.title")} description={t("tenant.receipt.description")} />
        </TabsContent>

        <TabsContent value="security" className="mt-3.5 flex flex-col gap-3.5">
          <AiConsentCard settings={settings} />
          <Card className="flex flex-col gap-4">
            <SwitchField
              control={control}
              name="aiTrainingConsent"
              label={t("tenant.fields.aiTrainingConsent")}
              hint={t("tenant.fields.aiTrainingConsentHint")}
              disabled={!online}
            />
            <SegmentField
              control={control}
              name="supplierOverpayPolicy"
              label={t("tenant.fields.supplierOverpayPolicy")}
              hint={t("tenant.fields.supplierOverpayPolicyHint")}
              options={opt(["warn", "block"] as const, (v) => t(`tenant.supplierOverpay.${v}`))}
              disabled={!online}
            />
          </Card>
          <NextStageCard
            title={t("tenant.syncExceptions.title")}
            description={t("tenant.syncExceptions.description")}
          />
        </TabsContent>
      </Tabs>
      {dirty ? (
        <p className="flex items-center gap-1.5 text-small text-foreground-secondary" role="status">
          <Icon as={Store} size="sm" />
          {t("tenant.unsaved")}
        </p>
      ) : null}
    </div>
  );
}

export const Tenant = {
  route: "settings/tenant",
  titleKey: "settings:tenant.title",
  Page: TenantPage,
} as const;

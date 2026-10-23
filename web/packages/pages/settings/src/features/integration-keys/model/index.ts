/**
 * BO-14 «Integratsiyalar» — tenant integration keys (20 #40a/#40d/#40e; contracts/tenant-integrations.md):
 * `PUT /tenant/integrations/{provider}` stores the provider's secret fields (envelope-encrypted on the server,
 * never returned — the form always starts empty), `DELETE …/{provider}` disconnects. Status comes from
 * `GET /tenant/settings` → `integrations` (`status`, `connected_at`, `last_ok_at`, `last_error`, `key_last4`).
 * Click / Payme / Uzum require `provider_autofiscal_disabled_confirmed: true` (07 BO-14 `providerFiscalizationOff`).
 */
import { createEffect } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";
import type {
  AppModulesIntegrationsTenantKeysApiRouterIntegrationOut,
  CashRegisterOut,
  IntegrationKeysIn,
  IntegrationsOut,
} from "@shared/models";

/** URL slug of `PUT /tenant/integrations/{provider}` (20 #40d). */
export type ProviderSlug = "faktura-uz" | "didox" | "crpt" | "click" | "payme" | "uzum" | "uzqr";
/** Key of the provider in `GET /tenant/settings` → `integrations`. */
export type ProviderKind = "faktura_uz" | "didox" | "crpt" | "click" | "payme" | "uzum" | "uzqr";

export type FieldName =
  | "login"
  | "password"
  | "client_id"
  | "client_secret"
  | "api_key"
  | "merchant_id"
  | "service_id"
  | "secret_key"
  | "merchant_user_id"
  | "key"
  | "terminal_id"
  | "dynamic_qr_service_id"
  | "dynamic_qr_user_id"
  | "dynamic_qr_secret_key";

export interface FieldSpec {
  name: FieldName;
  /** Masked input, never shown again (07 BO-14 «qayta ko'rsatilmaydi»). */
  secret: boolean;
  required: boolean;
  /** Numeric identifier (Click merchant/service id, Uzum serviceId …). */
  digits?: boolean;
}

export interface ProviderSpec {
  slug: ProviderSlug;
  kind: ProviderKind;
  fields: readonly FieldSpec[];
  /** Optional fields that come all together or not at all (Uzum Dynamic QR). */
  group?: readonly FieldName[];
  /** click / payme / uzum — provider auto-fiscalisation must be confirmed OFF. */
  autofiscal: boolean;
  /** payme — sandbox flag `test_mode`. */
  testMode?: boolean;
  /** uzqr — the key belongs to one cash register. */
  perRegister?: boolean;
}

const f = (name: FieldName, secret: boolean, required = true, digits = false): FieldSpec => ({
  name,
  secret,
  required,
  digits,
});

/** 20 #40d provider table (backend `tenant_keys/domain/providers.py`). */
export const PROVIDERS: readonly ProviderSpec[] = [
  {
    slug: "faktura-uz",
    kind: "faktura_uz",
    fields: [f("login", true), f("password", true), f("client_id", true), f("client_secret", true)],
    autofiscal: false,
  },
  { slug: "didox", kind: "didox", fields: [f("login", true), f("password", true)], autofiscal: false },
  { slug: "crpt", kind: "crpt", fields: [f("api_key", true)], autofiscal: false },
  {
    slug: "click",
    kind: "click",
    fields: [
      f("merchant_id", false, true, true),
      f("service_id", false, true, true),
      f("secret_key", true),
      f("merchant_user_id", false, false, true),
    ],
    autofiscal: true,
  },
  {
    slug: "payme",
    kind: "payme",
    fields: [f("merchant_id", false), f("key", true)],
    autofiscal: true,
    testMode: true,
  },
  {
    slug: "uzum",
    kind: "uzum",
    fields: [
      f("merchant_id", false, true, true),
      f("login", true),
      f("password", true),
      f("dynamic_qr_service_id", false, false, true),
      f("dynamic_qr_user_id", false, false, true),
      f("dynamic_qr_secret_key", true, false),
    ],
    group: ["dynamic_qr_service_id", "dynamic_qr_user_id", "dynamic_qr_secret_key"],
    autofiscal: true,
  },
  {
    slug: "uzqr",
    kind: "uzqr",
    fields: [f("merchant_id", false), f("terminal_id", false), f("api_key", true, false)],
    autofiscal: false,
    perRegister: true,
  },
];

export function providerBySlug(slug: ProviderSlug): ProviderSpec {
  const spec = PROVIDERS.find((p) => p.slug === slug);
  if (!spec) throw new Error(`unknown provider ${slug}`);
  return spec;
}

export interface KeyFormValues {
  fields: Partial<Record<FieldName, string>>;
  autofiscalConfirmed: boolean;
  testMode: boolean;
  cashRegisterId: string;
}

export function emptyValues(): KeyFormValues {
  return { fields: {}, autofiscalConfirmed: false, testMode: false, cashRegisterId: "" };
}

export type KeyFormError =
  | "validation.required"
  | "validation.digits_only"
  | "validation.group_incomplete"
  | "validation.autofiscal_confirmation_required";

/** Client-side checks of 20 #40d (the server repeats them); `{field|autofiscal|cashRegisterId: key}`. */
export function validateKeys(spec: ProviderSpec, v: KeyFormValues): Record<string, KeyFormError> {
  const errors: Record<string, KeyFormError> = {};
  const value = (n: FieldName) => (v.fields[n] ?? "").trim();
  for (const field of spec.fields) {
    const text = value(field.name);
    if (field.required && text === "") errors[field.name] = "validation.required";
    else if (text !== "" && field.digits && !/^[0-9]{1,20}$/.test(text)) {
      errors[field.name] = "validation.digits_only";
    }
  }
  if (spec.group) {
    const filled = spec.group.filter((n) => value(n) !== "");
    if (filled.length > 0 && filled.length < spec.group.length) {
      for (const n of spec.group) if (value(n) === "" && !errors[n]) errors[n] = "validation.group_incomplete";
    }
  }
  if (spec.autofiscal && !v.autofiscalConfirmed) {
    errors.autofiscal = "validation.autofiscal_confirmation_required";
  }
  if (spec.perRegister && v.cashRegisterId === "") errors.cashRegisterId = "validation.required";
  return errors;
}

/** Form → `IntegrationKeysIn`: only this provider's non-empty fields (others → server VALIDATION_ERROR). */
export function toKeysBody(spec: ProviderSpec, v: KeyFormValues): IntegrationKeysIn {
  const body: IntegrationKeysIn = {};
  for (const field of spec.fields) {
    const text = (v.fields[field.name] ?? "").trim();
    if (text !== "") body[field.name] = text;
  }
  if (spec.autofiscal) body.provider_autofiscal_disabled_confirmed = v.autofiscalConfirmed;
  if (spec.testMode && v.testMode) body.test_mode = true;
  if (spec.perRegister && v.cashRegisterId) body.cash_register_id = v.cashRegisterId;
  return body;
}

// --- status (20 #40a) ----------------------------------------------------------------------------------

export type RowState = "connected" | "attention" | "not_connected";

export interface StatusRow {
  spec: ProviderSpec;
  state: RowState;
  connectedAt: string | null;
  lastOkAt: string | null;
  lastError: string | null;
  lastErrorAt: string | null;
  keyLast4: string | null;
  registerIds: readonly string[];
}

interface StatusLike {
  status: string;
  connected_at?: string | null;
  last_ok_at?: string | null;
  last_error?: string | null;
  last_error_at?: string | null;
}

function statusOf(integrations: IntegrationsOut, kind: ProviderKind): StatusLike | null {
  return (integrations[kind] as StatusLike | null | undefined) ?? null;
}

/**
 * One row per provider. A connected key whose last call failed after its last success needs attention
 * («Tasdiq kerak» chip, the header's «M ta e'tibor talab qiladi»).
 */
export function statusRows(integrations: IntegrationsOut): StatusRow[] {
  return PROVIDERS.map((spec) => {
    const s = statusOf(integrations, spec.kind);
    const connected = s?.status === "connected";
    const lastError = s?.last_error ?? null;
    const failedLast =
      lastError !== null && (!s?.last_ok_at || !s.last_error_at || s.last_error_at >= s.last_ok_at);
    return {
      spec,
      state: !connected ? "not_connected" : failedLast ? "attention" : "connected",
      connectedAt: s?.connected_at ?? null,
      lastOkAt: s?.last_ok_at ?? null,
      lastError,
      lastErrorAt: s?.last_error_at ?? null,
      keyLast4: spec.kind === "crpt" ? integrations.crpt.key_last4 : null,
      registerIds: spec.kind === "uzqr" ? integrations.uzqr.cash_register_ids : [],
    };
  });
}

export function summaryOf(rows: readonly StatusRow[]): { connected: number; attention: number; total: number } {
  return {
    connected: rows.filter((r) => r.state !== "not_connected").length,
    attention: rows.filter((r) => r.state === "attention").length,
    total: rows.length,
  };
}

// --- effects -------------------------------------------------------------------------------------------

function wrap<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw toApiError(e);
    }
  });
}

export const putKeysFx = wrap<
  { slug: ProviderSlug; body: IntegrationKeysIn },
  AppModulesIntegrationsTenantKeysApiRouterIntegrationOut
>(({ slug, body }) => api.branches.putTenantIntegration(slug, body));

export const deleteKeysFx = wrap<{ slug: ProviderSlug; cashRegisterId: string | null }, void>(
  ({ slug, cashRegisterId }) =>
    api.branches.deleteTenantIntegration(slug, cashRegisterId ? { cash_register_id: cashRegisterId } : {}),
);

/** UzQR keys are per cash register (20 #40d) — the register list for the select. */
export const loadRegistersFx = wrap<void, CashRegisterOut[]>(async () => {
  const { items } = await api.branches.cashRegistersList();
  return items.filter((r) => r.archived_at === null);
});

import { describe, expect, it } from "vitest";

import { initI18n, translateMessageKey } from "./index.ts";
import { resources } from "./resources.ts";

type Tree = { [key: string]: string | Tree };

function keys(tree: Tree, prefix = ""): string[] {
  return Object.entries(tree).flatMap(([k, v]) =>
    typeof v === "string" ? [`${prefix}${k}`] : keys(v, `${prefix}${k}.`),
  );
}

function leaves(tree: Tree, prefix = ""): [string, string][] {
  return Object.entries(tree).flatMap(([k, v]): [string, string][] =>
    typeof v === "string" ? [[`${prefix}${k}`, v]] : leaves(v, `${prefix}${k}.`),
  );
}

/** i18next plural suffixes: `key_one`/`key_few`/... are one logical key (uz has no plural forms). */
const PLURAL = /_(zero|one|two|few|many|other)$/;

function logicalKeys(tree: Tree): string[] {
  return [...new Set(keys(tree).map((k) => k.replace(PLURAL, "")))].sort();
}

describe("i18n resources — 08 §11", () => {
  it.each(Object.keys(resources.uz))("ru/%s.json has exactly the uz keys", (ns) => {
    const uz = logicalKeys(resources.uz[ns as keyof typeof resources.uz]);
    const ru = logicalKeys(resources.ru[ns as keyof typeof resources.ru]);
    expect(ru).toEqual(uz);
  });

  it.each(["uz", "ru"] as const)("%s plural keys carry every CLDR category of the language", (lang) => {
    const categories = new Intl.PluralRules(lang).resolvedOptions().pluralCategories;
    const missing = Object.entries(resources[lang] as Record<string, Tree>).flatMap(([ns, tree]) => {
      const all = new Set(keys(tree));
      const bases = [...all].filter((k) => PLURAL.test(k)).map((k) => k.replace(PLURAL, ""));
      return [...new Set(bases)].flatMap((base) =>
        categories.filter((c) => !all.has(`${base}_${c}`)).map((c) => `${ns}:${base}_${c}`),
      );
    });
    expect(missing).toEqual([]);
  });

  it("Russian counts use plural forms (1 событие, 3 события, 37 событий)", async () => {
    const i18n = initI18n("ru");
    await i18n.changeLanguage("ru");
    const t = i18n.getFixedT("ru", "settings");
    expect(t("devices.pendingWarning", { count: 1 })).toContain("1 неотправленное событие");
    expect(t("devices.pendingWarning", { count: 3 })).toContain("3 неотправленных события");
    expect(t("devices.pendingWarning", { count: 37 })).toContain("37 неотправленных событий");
    await i18n.changeLanguage("uz");
    expect(i18n.getFixedT("uz", "settings")("devices.pendingWarning", { count: 37 })).toBe(
      "Qurilmada 37 ta yuborilmagan voqea bor — avval sinxronlang.",
    );
  });

  it.each(["uz", "ru"] as const)("%s has no empty or whitespace-only values", (lang) => {
    const empty = Object.entries(resources[lang] as Record<string, Tree>).flatMap(([ns, tree]) =>
      leaves(tree, `${ns}:`)
        .filter(([, value]) => value.trim().length === 0)
        .map(([key]) => key),
    );
    expect(empty).toEqual([]);
  });

  it("translates server message_key and falls back to internal_error", async () => {
    const i18n = initI18n("uz");
    expect(translateMessageKey("errors.invalid_credentials")).toBe("Telefon yoki parol noto'g'ri");
    expect(translateMessageKey("errors.something_unknown")).toBe("Xatolik yuz berdi. Qayta urinib ko'ring");
    await i18n.changeLanguage("ru");
    expect(translateMessageKey("errors.invalid_credentials")).toBe("Неверный телефон или пароль");
  });
});

/** 17 §15 codes and 17 §15.1 field keys that Bosqich 1 endpoints (auth/OTP/Google, staff, branches, catalog, import) can return. */
const BOSQICH1_MESSAGE_KEYS = [
  "errors.unauthorized",
  "errors.invalid_credentials",
  "errors.account_locked",
  "errors.otp_invalid",
  "errors.otp_expired",
  "errors.otp_max_attempts",
  "errors.otp_channel_unavailable",
  "errors.telegram_not_linked",
  "errors.google_email_not_verified",
  "errors.google_auth_failed",
  "errors.csrf_invalid",
  "errors.token_expired",
  "errors.token_revoked",
  "errors.device_revoked",
  "errors.pin_invalid",
  "errors.validation",
  "errors.version_conflict",
  "errors.not_found",
  "errors.resource_archived",
  "errors.system_role_readonly",
  "errors.barcode_duplicate",
  "errors.category_has_products",
  "errors.mxik_code_invalid",
  "errors.permission_denied",
  "errors.branch_scope_denied",
  "errors.owner_only",
  "errors.warehouse_account_locked",
  "errors.addon_required",
  "errors.import_file_invalid",
  "errors.import_job_not_validated",
  "errors.import_job_already_committed",
  "errors.file_too_large",
  "errors.unsupported_file_type",
  "errors.doc_not_draft",
  "errors.doc_invalid_state",
  "errors.doc_already_cancelled",
  "errors.approval_required",
  "errors.price_change_limit_exceeded",
  "errors.rate_limited",
  "errors.idempotency_in_progress",
  "errors.idempotency_key_reused",
  "errors.subscription_restricted",
  "errors.internal_error",
  "otp_sent_telegram",
  "otp_sent_sms",
  "validation.required",
  "validation.max_length",
  "validation.phone_format",
  "validation.json_invalid",
  "validation.cannot_block_self",
];

describe("message_key coverage — 17 §15 / §15.1", () => {
  it.each(["uz", "ru"] as const)("%s/common.json has every Bosqich 1 message_key", (lang) => {
    const all = new Set(keys(resources[lang].common));
    expect(BOSQICH1_MESSAGE_KEYS.filter((k) => !all.has(k))).toEqual([]);
  });

  it("interpolates params with i18next syntax", async () => {
    await initI18n("uz").changeLanguage("uz");
    expect(translateMessageKey("validation.min_length", { min: 2 })).toBe("Kamida 2 ta belgi kiriting");
  });
});

/**
 * Runtime configuration — 24-frontend-arxitekturasi.md §3: `window.__ERP_CONFIG__` lets one build run
 * in every environment. It is set by `/config.js` (external script, CSP-safe), loaded before the app.
 *
 * Every value from the window is validated; an invalid or missing value falls back to the safe
 * default (links: `null` → the UI shows the text without a link — never a guessed URL).
 */
export interface ErpRuntimeConfig {
  /** API origin. Empty string = same origin (required for the HttpOnly BFF cookie, 14 §2.1). */
  apiBaseUrl: string;
  /** dev | test | staging | production */
  environment: "dev" | "test" | "staging" | "production";
  /** Shop agent loopback port (21 §16, default 47110). */
  agentPort: number;
  /**
   * Notification / OTP Telegram bot (21 §11; BO-21 ①⑤, credential set): `"erp_uz_bot"`,
   * `"@erp_uz_bot"` or `"https://t.me/erp_uz_bot"`. Stored normalised as the bare username.
   */
  telegramBot: string | null;
  /** Support Telegram (bot or account, 25 §12 "/yordam"; BO-21 «Yordam kerakmi?») — same formats. */
  supportTelegram: string | null;
  /** Support phone (25 §12), E.164 `+998901234567` (a `tel:` prefix is accepted). */
  supportPhone: string | null;
  /** Support / help-centre page — https only. */
  supportUrl: string | null;
  /**
   * «Google bilan kirish» (14 §2.2) on BO-01 and BO-21 ①. Default `false`: the button is shown only
   * where the backend has Google OAuth configured (otherwise /auth/google/start just redirects back
   * to `/login?error=google_auth_failed`). Only the boolean `true` enables it.
   */
  googleEnabled: boolean;
}

/** What `/config.js` may set: any key, any value — it is validated by getRuntimeConfig(). */
export type ErpRuntimeConfigInput = { [K in keyof ErpRuntimeConfig]?: unknown };

declare global {
  interface Window {
    __ERP_CONFIG__?: ErpRuntimeConfigInput;
  }
}

export const RUNTIME_CONFIG_DEFAULTS: Readonly<ErpRuntimeConfig> = Object.freeze({
  apiBaseUrl: "",
  environment: "dev",
  agentPort: 47110,
  telegramBot: null,
  supportTelegram: null,
  supportPhone: null,
  supportUrl: null,
  googleEnabled: false,
});

const ENVIRONMENTS: readonly ErpRuntimeConfig["environment"][] = ["dev", "test", "staging", "production"];
/** Telegram username rules: 5–32 chars, letters/digits/underscore, starts with a letter. */
const TELEGRAM_USERNAME = /^[A-Za-z][A-Za-z0-9_]{4,31}$/;
const TELEGRAM_URL = /^https:\/\/t\.me\/([A-Za-z][A-Za-z0-9_]{4,31})\/?$/;
const E164 = /^\+[1-9][0-9]{6,14}$/;

/** `"name"`, `"@name"` or `"https://t.me/name"` → `"name"`; anything else → null. */
export function parseTelegramUsername(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const raw = value.trim();
  const fromUrl = TELEGRAM_URL.exec(raw)?.[1];
  if (fromUrl) return fromUrl;
  const name = raw.startsWith("@") ? raw.slice(1) : raw;
  return TELEGRAM_USERNAME.test(name) ? name : null;
}

/** `"+998901234567"` / `"tel:+998901234567"` (spaces, dashes, brackets ignored) → E.164 or null. */
export function parsePhone(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const compact = value
    .trim()
    .replace(/^tel:/i, "")
    .replace(/[\s\-()]/g, "");
  return E164.test(compact) ? compact : null;
}

/** Absolute https URL without credentials → normalised href, else null. */
export function parseHttpsUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    return null;
  }
  if (url.protocol !== "https:" || url.username || url.password) return null;
  return url.href;
}

/** Validates the raw window object field by field; invalid fields take the default. */
export function parseRuntimeConfig(input: ErpRuntimeConfigInput | undefined): ErpRuntimeConfig {
  const raw = input ?? {};
  const d = RUNTIME_CONFIG_DEFAULTS;
  const port = raw.agentPort;
  return {
    apiBaseUrl: typeof raw.apiBaseUrl === "string" ? raw.apiBaseUrl : d.apiBaseUrl,
    environment: ENVIRONMENTS.includes(raw.environment as ErpRuntimeConfig["environment"])
      ? (raw.environment as ErpRuntimeConfig["environment"])
      : d.environment,
    agentPort:
      typeof port === "number" && Number.isInteger(port) && port > 0 && port < 65536 ? port : d.agentPort,
    telegramBot: parseTelegramUsername(raw.telegramBot),
    supportTelegram: parseTelegramUsername(raw.supportTelegram),
    supportPhone: parsePhone(raw.supportPhone),
    supportUrl: parseHttpsUrl(raw.supportUrl),
    googleEnabled: raw.googleEnabled === true,
  };
}

export function getRuntimeConfig(): ErpRuntimeConfig {
  return parseRuntimeConfig(typeof window === "undefined" ? undefined : window.__ERP_CONFIG__);
}

export interface ExternalLink {
  /** Visible text: `@erp_uz_bot`, `+998 71 200 00 00`, the host of a URL. */
  label: string;
  href: string;
}

const telegramLink = (username: string | null): ExternalLink | null =>
  username ? { label: `@${username}`, href: `https://t.me/${username}` } : null;

/** "+998712000000" → "+998 71 200 00 00" (Uzbek numbers, 08 §8); other countries stay E.164. */
function phoneLabel(e164: string): string {
  const national = e164.startsWith("+998") ? e164.slice(4) : "";
  if (national.length !== 9) return e164;
  return `+998 ${national.slice(0, 2)} ${national.slice(2, 5)} ${national.slice(5, 7)} ${national.slice(7)}`;
}

/** Notification / OTP bot link (BO-21 account and Telegram steps, credential set); null if unset. */
export function telegramBotLink(config: ErpRuntimeConfig = getRuntimeConfig()): ExternalLink | null {
  return telegramLink(config.telegramBot);
}

export interface SupportLinks {
  telegram: ExternalLink | null;
  phone: ExternalLink | null;
  web: ExternalLink | null;
}

/** Support channels (25 §12): Telegram, phone (`tel:`), help page — each null when not configured. */
export function supportLinks(config: ErpRuntimeConfig = getRuntimeConfig()): SupportLinks {
  return {
    telegram: telegramLink(config.supportTelegram),
    phone: config.supportPhone
      ? { label: phoneLabel(config.supportPhone), href: `tel:${config.supportPhone}` }
      : null,
    web: config.supportUrl ? { label: new URL(config.supportUrl).host, href: config.supportUrl } : null,
  };
}

/**
 * Full-page navigation to `GET /auth/google/start` (14 §2.2) — the one builder for BO-01 and BO-21 ①.
 * `null` when Google sign-in is not enabled for this deployment (`googleEnabled`) → no button.
 */
export function googleStartUrl(
  { returnTo, tenantId }: { returnTo?: string | null; tenantId?: string | null } = {},
  config: ErpRuntimeConfig = getRuntimeConfig(),
): string | null {
  if (!config.googleEnabled) return null;
  const params = new URLSearchParams();
  if (returnTo) params.set("return_to", returnTo);
  if (tenantId) params.set("tenant_id", tenantId);
  const query = params.toString();
  return `${config.apiBaseUrl}/auth/google/start${query ? `?${query}` : ""}`;
}

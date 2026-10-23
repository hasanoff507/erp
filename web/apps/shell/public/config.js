/*
 * Runtime configuration (24-frontend-arxitekturasi.md §3) — replaced per environment at deploy time;
 * one build runs everywhere. Not precached by the service worker (always fetched NetworkFirst).
 * apiBaseUrl must stay "" (same origin): the HttpOnly BFF session cookie is first-party only.
 * Every key is validated by @shared/lib/runtime-config; an invalid value falls back to its default
 * (links: null → the UI shows plain text, no link).
 *   telegramBot      notification / OTP bot: "erp_uz_bot", "@erp_uz_bot" or "https://t.me/erp_uz_bot"
 *   supportTelegram  support bot / account (25 §12 "/yordam") — same formats
 *   supportPhone     support phone, E.164 "+998712000000" ("tel:" prefix accepted)
 *   supportUrl       help page, https:// only
 *   googleEnabled    true = show «Google bilan kirish» (BO-01, BO-21 ①); only when the backend has Google
 *                    OAuth configured (ERP_GOOGLE_CLIENT_ID/SECRET), else /auth/google/start bounces back to
 *                    /login?error=google_auth_failed. Anything but the boolean true = hidden (default).
 */
window.__ERP_CONFIG__ = {
  apiBaseUrl: "",
  environment: "dev",
  agentPort: 47110,
  telegramBot: null,
  supportTelegram: null,
  supportPhone: null,
  supportUrl: null,
  googleEnabled: false,
};

/**
 * BO-01 helpers. The credentials themselves are entered on the AS page (14 §2.1), so the SPA only
 * decides where to send the browser and how to explain `/login?error=<reason>` coming back from
 * `/auth/callback`.
 */

/** Backend limit: `GET /auth/login/start` `return_to` is `Query(max_length=2048)` (auth/api/bff.py). */
export const MAX_NEXT_LENGTH = 2048;

/**
 * Same-app absolute paths only (the backend applies the same open-redirect guard, `safe_return_to`).
 * Anything else is dropped before the /auth/login/start URL is built, so a crafted `?next=` can
 * neither redirect off-site nor make the BFF answer 422.
 */
export function safeNextPath(next: string | null): string | null {
  if (!next || next.length > MAX_NEXT_LENGTH) return null;
  if (!next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return null;
  if (next.startsWith("/login")) return null;
  return next;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** `?tenant_id=` is forwarded to the BFF only when it is a UUID (backend `tenant_id: UUID | None`). */
export function safeTenantId(value: string | null): string | null {
  return value && UUID.test(value) ? value : null;
}

/** BFF callback reasons with their own message; anything else → `login.errors.default`. */
const KNOWN_REASONS = [
  "login_state_missing",
  "login_state_expired",
  "state_mismatch",
  "authorization_denied",
  "invalid_grant",
  // GET /auth/google/start or /callback failed — also when Google OAuth is not configured (14 §2.2).
  "google_auth_failed",
] as const;
/**
 * Reasons of GET /auth/google/callback → `/login?error=<reason>` (backend auth/application/google.py)
 * and BFF `client_unavailable`; their texts live in the `onboarding` namespace (`login.errors.*`).
 */
const ONBOARDING_REASONS = [
  "google_email_not_verified",
  "tenant_required",
  "no_active_membership",
  "not_a_member",
  "client_unavailable",
] as const;
export type OnboardingErrorReason = (typeof ONBOARDING_REASONS)[number];
/** `no_membership` comes from GET /auth/session 403 PERMISSION_DENIED, not from the callback. */
export type LoginErrorReason =
  (typeof KNOWN_REASONS)[number] | OnboardingErrorReason | "no_membership" | "default";

export function isOnboardingReason(reason: LoginErrorReason): reason is OnboardingErrorReason {
  return (ONBOARDING_REASONS as readonly string[]).includes(reason);
}

/** `subscription_restricted` is not an error message but the restricted-subscription banner. */
export const SUBSCRIPTION_REASON = "subscription_restricted";

export function loginErrorReason(error: string | null): LoginErrorReason | null {
  if (!error || error === SUBSCRIPTION_REASON) return null;
  if ((KNOWN_REASONS as readonly string[]).includes(error)) return error as LoginErrorReason;
  if ((ONBOARDING_REASONS as readonly string[]).includes(error)) return error as LoginErrorReason;
  return "default";
}

import type { Branch, Session, SubscriptionRestriction } from "../types/index.ts";

const BRANCH_KEY = "erp.branch";

/** Topbar "Barcha filiallar" (06 §1.9): consolidated view, no X-Branch-Id header is sent. */
export const ALL_BRANCHES = "all";

/** 14 §16.1.4: light periodic GET /auth/session so a lock-out is noticed without user action. */
export const HEARTBEAT_MS = 30_000;

/** i18n key (common namespace) for a failed logout — see `$logoutError` / `logoutFailed`. */
export const LOGOUT_FAILED_KEY = "session.logoutFailed";

/** First-check retry while the server is unreachable / failing (5xx): 3 s doubling up to 30 s. */
export const SESSION_RETRY_BASE_MS = 3_000;
export const SESSION_RETRY_MAX_MS = 30_000;

export function sessionRetryDelay(attempt: number): number {
  let ms = SESSION_RETRY_BASE_MS;
  for (let i = 0; i < attempt && ms < SESSION_RETRY_MAX_MS; i += 1) ms *= 2;
  return Math.min(ms, SESSION_RETRY_MAX_MS);
}

/** The server itself refused the session (401 / 403) — as opposed to "could not ask" (network, 5xx). */
export function isSessionRefusal(error: { status: number | null }): boolean {
  return error.status === 401 || error.status === 403;
}

export function readStoredBranchId(): string | null {
  try {
    return globalThis.localStorage?.getItem(BRANCH_KEY) ?? null;
  } catch {
    return null;
  }
}

export function writeStoredBranchId(id: string): void {
  try {
    globalThis.localStorage?.setItem(BRANCH_KEY, id);
  } catch {
    // storage unavailable — selection lives in memory only
  }
}

/**
 * Keeps a remembered choice only if it is still valid for the session; a single branch is chosen
 * automatically; several branches without a valid choice → `null` (BO-01 branch step, 07 `branchId`).
 */
export function resolveActiveBranch(branches: readonly Branch[], preferred: string | null): string | null {
  if (branches.length === 1) return branches[0]?.id ?? null;
  if (preferred === ALL_BRANCHES && branches.length > 1) return ALL_BRANCHES;
  if (preferred && branches.some((b) => b.id === preferred)) return preferred;
  return null;
}

export function restrictionFromParams(params: Readonly<Record<string, unknown>>): SubscriptionRestriction {
  return {
    payUrl: typeof params.pay_url === "string" ? params.pay_url : null,
    amountDue: typeof params.amount_due === "string" ? params.amount_due : null,
  };
}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;

export function isSession(value: unknown): value is Session {
  if (!isObject(value)) return false;
  return (
    isObject(value.user) &&
    typeof value.user.id === "string" &&
    isObject(value.tenant) &&
    typeof value.tenant.id === "string" &&
    Array.isArray(value.branches) &&
    Array.isArray(value.roles) &&
    Array.isArray(value.permissions) &&
    Array.isArray(value.scope)
  );
}

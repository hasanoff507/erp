/**
 * App-level hooks injected by the shell (`configureApi`). The API layer must not import
 * @shared/state (state depends on api), so cross-cutting context arrives through these callbacks.
 */
import type { ApiError } from "./errors.ts";

export interface ApiHooks {
  /** Current UI language → `Accept-Language` (17 §5: `uz` | `ru`). */
  getLanguage: () => string;
  /** Selected branch → `X-Branch-Id` (17 §5). */
  getBranchId: () => string | null;
  /** 401 after the BFF failed its silent refresh (24 §3). */
  onUnauthorized: (error: ApiError) => void;
  /** 403 SUBSCRIPTION_RESTRICTED → /login?reason=subscription_expired (14 §16.1.4). Not a logout. */
  onSubscriptionRestricted: (error: ApiError) => void;
  /** No response at all → `$isOnline = false` (24 §3). */
  onNetworkError: (error: ApiError) => void;
  /** The server answered (any 2xx, or an error that has a response) → `$isOnline = true` (24 §3). */
  onOnline: () => void;
}

const noop = () => undefined;

export const apiHooks: ApiHooks = {
  getLanguage: () => "uz",
  getBranchId: () => null,
  onUnauthorized: noop,
  onSubscriptionRestricted: noop,
  onNetworkError: noop,
  onOnline: noop,
};

export function configureApi(hooks: Partial<ApiHooks>): void {
  Object.assign(apiHooks, hooks);
}

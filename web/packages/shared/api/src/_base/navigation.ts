/**
 * Full-page navigations of the BFF login (14 §2.1). These are NOT XHR calls: the browser itself goes
 * to `GET /auth/login/start`, the BFF keeps state + PKCE verifier server-side and redirects to the
 * server-rendered AS page (`/oauth/authorize`), where the password is entered. The callback sets the
 * HttpOnly `__Host-sid` cookie and redirects back to `return_to` (or to `/login?error=<reason>`).
 * The path matches the generated `api.auth.loginStart` (operation `auth_login_start`).
 */
import { getRuntimeConfig } from "@shared/lib/runtime-config";

export const LOGIN_START_PATH = "/auth/login/start";

export interface LoginStartOptions {
  /** Same-app path to return to after login (the backend re-checks it: open-redirect guard). */
  returnTo?: string | null;
  /** Pick a tenant when the user belongs to several (14 §9). */
  tenantId?: string | null;
}

export function loginStartUrl({ returnTo, tenantId }: LoginStartOptions = {}): string {
  const params = new URLSearchParams();
  if (returnTo) params.set("return_to", returnTo);
  if (tenantId) params.set("tenant_id", tenantId);
  const query = params.toString();
  return `${getRuntimeConfig().apiBaseUrl}${LOGIN_START_PATH}${query ? `?${query}` : ""}`;
}

import type { SessionBranch, SessionInfo, SessionTenant, SessionUser } from "@shared/models";

/** GET /auth/session (14 §20, backend SessionInfo, Cache-Control: no-store). */
export type Session = SessionInfo;
export type User = SessionUser;
export type Tenant = SessionTenant;
export type Branch = SessionBranch;

/** `unknown` until GET /auth/session answers once (the shell shows a splash meanwhile). */
export type AuthStatus = "unknown" | "authenticated" | "anonymous";

/** Data for the "Obuna muddati tugagan" banner (14 §16.1.2: pay_url / amount_due from the 403 body). */
export interface SubscriptionRestriction {
  payUrl: string | null;
  amountDue: string | null;
}

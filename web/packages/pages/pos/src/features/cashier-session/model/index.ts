/**
 * Lock / switch cashier and device logout (07 POS-01; 16 §12, 14 §4.3):
 *  - «Bloklash» drops only the PIN-verified cashier (the device session stays, outbox untouched);
 *  - «Chiqish» = device logout: refused while an unresolved card attempt exists (CARD_OUTCOME_UNKNOWN),
 *    warns and offers the outbox export when unsynced events exist (OUTBOX_NOT_EMPTY), then wipes
 *    `erp-pos` (erp-device + counters stay) and ends the BFF session.
 */
import { isOfflineError, logout, logoutCheck, outbox, type LogoutCheck } from "@shared/offline";

export interface LogoutDeps {
  check(): Promise<LogoutCheck>;
  wipe(confirmUnsynced: boolean): Promise<void>;
  exportOutbox(): Promise<unknown>;
  /** SYNC-03: an unresolved card attempt blocks the logout — open the card recovery dialog. */
  cardBlocked?(): void;
}

export const defaultLogoutDeps: LogoutDeps = {
  check: () => logoutCheck(),
  wipe: (confirmUnsynced) => logout({ confirmUnsynced }),
  exportOutbox: () => outbox.export(),
};

export type LogoutDecision =
  { kind: "blocked_card" } | { kind: "confirm_unsynced"; pending: number; rejected: number } | { kind: "ok" };

/** 16 §12 decision before anything is deleted. */
export function logoutDecision(check: LogoutCheck): LogoutDecision {
  if (check.blocker === "card_attempts") return { kind: "blocked_card" };
  if (check.pending + check.rejected > 0) {
    return { kind: "confirm_unsynced", pending: check.pending, rejected: check.rejected };
  }
  return { kind: "ok" };
}

/** Runs the wipe; maps the library refusals back to a decision (another tab may have added events). */
export async function performLogout(deps: LogoutDeps, confirmUnsynced: boolean): Promise<LogoutDecision> {
  try {
    await deps.wipe(confirmUnsynced);
    return { kind: "ok" };
  } catch (e) {
    if (isOfflineError(e, "CARD_OUTCOME_UNKNOWN")) return { kind: "blocked_card" };
    if (isOfflineError(e, "OUTBOX_NOT_EMPTY")) return logoutDecision(await deps.check());
    throw e;
  }
}

/** File name of the outbox export (JSON, 16 §9/§12). */
export const exportFileName = (deviceId: string, at: string): string =>
  `erp-outbox-${deviceId.slice(0, 8)}-${at.replace(/[:.]/g, "-")}.json`;

/** «Chiqish» pressed: decide, open the card recovery when a card attempt blocks (SYNC-03), wipe when clean. */
export async function beginLogout(deps: LogoutDeps): Promise<LogoutDecision> {
  const decision = logoutDecision(await deps.check());
  if (decision.kind === "ok") {
    const after = await performLogout(deps, false);
    if (after.kind === "blocked_card") deps.cardBlocked?.();
    return after;
  }
  if (decision.kind === "blocked_card") deps.cardBlocked?.();
  return decision;
}

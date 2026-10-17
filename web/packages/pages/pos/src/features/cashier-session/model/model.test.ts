/* eslint-disable @typescript-eslint/require-await -- in-memory fakes of async collaborators */
/** Logout rules (16 §12): blocked by an unresolved card attempt; unsynced events → confirm + export. */
import { describe, expect, it } from "vitest";

import { OfflineError } from "@shared/offline";

import { beginLogout, exportFileName, logoutDecision, performLogout, type LogoutDeps } from "./index.ts";

describe("logout (16 §12)", () => {
  it("decision order: card attempts block, unsynced events need confirmation", () => {
    expect(logoutDecision({ blocker: "card_attempts", cardAttempts: 1, pending: 3, rejected: 0 })).toEqual({
      kind: "blocked_card",
    });
    expect(logoutDecision({ blocker: null, cardAttempts: 0, pending: 2, rejected: 1 })).toEqual({
      kind: "confirm_unsynced",
      pending: 2,
      rejected: 1,
    });
    expect(logoutDecision({ blocker: null, cardAttempts: 0, pending: 0, rejected: 0 })).toEqual({
      kind: "ok",
    });
  });

  it("library refusals map back to a decision (another tab added events meanwhile)", async () => {
    const deps = (err: Error | null): LogoutDeps => ({
      check: async () => ({ blocker: null, cardAttempts: 0, pending: 1, rejected: 0 }),
      wipe: () => (err ? Promise.reject(err) : Promise.resolve()),
      exportOutbox: async () => ({}),
    });
    expect(await performLogout(deps(null), false)).toEqual({ kind: "ok" });
    expect(await performLogout(deps(new OfflineError("CARD_OUTCOME_UNKNOWN")), true)).toEqual({
      kind: "blocked_card",
    });
    expect(await performLogout(deps(new OfflineError("OUTBOX_NOT_EMPTY")), false)).toEqual({
      kind: "confirm_unsynced",
      pending: 1,
      rejected: 0,
    });
  });

  it("export file name", () => {
    expect(exportFileName("0190a000-0000", "2026-10-17T10:00:00.000Z")).toBe(
      "erp-outbox-0190a000-2026-10-17T10-00-00-000Z.json",
    );
  });

  it("SYNC-03: a card attempt blocking the logout opens the card recovery dialog", async () => {
    let recovery = 0;
    let wiped = 0;
    const d = await beginLogout({
      check: async () => ({ blocker: "card_attempts", cardAttempts: 1, pending: 0, rejected: 0 }),
      wipe: async () => {
        wiped += 1;
      },
      exportOutbox: async () => ({}),
      cardBlocked: () => {
        recovery += 1;
      },
    });
    expect(d).toEqual({ kind: "blocked_card" });
    expect(recovery).toBe(1);
    expect(wiped).toBe(0);
  });
});

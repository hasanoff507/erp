import { allSettled, fork } from "effector";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PosLogoutWipe } from "@shared/offline";

const wipe = vi.fn<(confirm: boolean) => Promise<PosLogoutWipe>>();
vi.mock("@shared/offline", () => ({
  wipePosForLogout: (confirm: boolean) => wipe(confirm),
  outbox: { export: vi.fn() },
}));

const { $session, logoutRequested, revokeAllSessionsRequested } = await import("@shared/state/session");
const model = await import("./index.ts");

describe("SEC-07 device logout (16 §12)", () => {
  beforeEach(() => {
    wipe.mockReset();
    sessionStorage.clear();
  });

  function watchLogout() {
    const calls: string[] = [];
    const a = logoutRequested.watch(() => calls.push("logout"));
    const b = revokeAllSessionsRequested.watch(() => calls.push("revokeAll"));
    return { calls, stop: () => (a.unsubscribe(), b.unsubscribe()) };
  }

  it("not a POS device → plain BFF logout, no dialog", async () => {
    wipe.mockResolvedValue({ kind: "not_device" });
    const w = watchLogout();
    const scope = fork();
    await allSettled(model.deviceLogoutRequested, { scope, params: "logout" });
    expect(wipe).toHaveBeenCalledWith(false);
    expect(w.calls).toEqual(["logout"]);
    expect(scope.getState(model.$deviceLogoutDialog)).toBeNull();
    w.stop();
  });

  it("unresolved card attempt → refused, no logout", async () => {
    wipe.mockResolvedValue({ kind: "blocked_card", cardAttempts: 1 });
    const w = watchLogout();
    const scope = fork();
    await allSettled(model.deviceLogoutRequested, { scope, params: "logout" });
    expect(scope.getState(model.$deviceLogoutDialog)).toEqual({ kind: "blocked_card", cardAttempts: 1 });
    expect(w.calls).toEqual([]);
    w.stop();
  });

  it("unsynced events → confirm dialog; confirming wipes erp-pos, forgets the cashier, then revoke-all", async () => {
    sessionStorage.setItem(model.POS_CASHIER_KEY, '{"userId":"u"}');
    wipe.mockResolvedValueOnce({ kind: "needs_confirm", pending: 2, rejected: 1 });
    const w = watchLogout();
    const scope = fork();
    await allSettled(model.deviceLogoutRequested, { scope, params: "revokeAll" });
    expect(scope.getState(model.$deviceLogoutDialog)).toEqual({
      kind: "needs_confirm",
      pending: 2,
      rejected: 1,
    });
    expect(w.calls).toEqual([]);

    wipe.mockResolvedValueOnce({ kind: "wiped" });
    await allSettled(model.deviceLogoutConfirmed, { scope });
    expect(wipe).toHaveBeenLastCalledWith(true);
    expect(sessionStorage.getItem(model.POS_CASHIER_KEY)).toBeNull();
    expect(scope.getState(model.$deviceLogoutDialog)).toBeNull();
    expect(w.calls).toEqual(["revokeAll"]);
    w.stop();
  });

  it("a failed wipe keeps the user signed in and shows the error", async () => {
    wipe.mockRejectedValue(new Error("db"));
    const w = watchLogout();
    const scope = fork();
    await allSettled(model.deviceLogoutRequested, { scope, params: "logout" });
    expect(scope.getState(model.$deviceLogoutError)).toBe(true);
    expect(scope.getState(model.$deviceLogoutDialog)).toEqual({ kind: "error" });
    expect(w.calls).toEqual([]);
    w.stop();
  });

  it("SEC-01: a device-bound session cannot revoke every session (action hidden and ignored)", async () => {
    wipe.mockResolvedValue({ kind: "not_device" });
    const w = watchLogout();
    const bound = { device: { id: "d-1", cash_register_id: "c-1", branch_id: "b-1" } };
    const scope = fork({ values: [[$session, bound as never]] });
    expect(scope.getState(model.$deviceBoundSession)).toBe(true);
    await allSettled(model.deviceLogoutRequested, { scope, params: "revokeAll" });
    expect(wipe).not.toHaveBeenCalled();
    expect(w.calls).toEqual([]);
    await allSettled(model.deviceLogoutRequested, { scope, params: "logout" });
    expect(w.calls).toEqual(["logout"]);
    const plain = fork({ values: [[$session, { device: null } as never]] });
    expect(plain.getState(model.$deviceBoundSession)).toBe(false);
    w.stop();
  });
});

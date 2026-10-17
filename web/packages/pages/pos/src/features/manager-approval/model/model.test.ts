/* eslint-disable @typescript-eslint/require-await -- in-memory fakes of async collaborators */
/**
 * ApprovalDialog logic (18 §2.4, §9; 15 §2.3; QT-PERM-05/-06 client side): eligible approvers (permission +
 * covering limit, never the requester), local PIN outcome → `ApprovalRef{local_pin}`, remote polling.
 */
import { describe, expect, it } from "vitest";

import type { StaffRow } from "@shared/offline";

import {
  eligibleApprovers,
  localPinOutcome,
  permissionLimit,
  waitRemoteApproval,
  type ApprovalDeps,
} from "./index.ts";

const row = (id: string, perms: StaffRow["permissions"], over: Partial<StaffRow> = {}): StaffRow => ({
  user_id: id,
  full_name: id,
  role_codes: ["manager"],
  branch_ids: [],
  active: true,
  must_change_pin: false,
  pin_local_hash: "x",
  permissions: perms,
  ...over,
});

describe("eligibleApprovers", () => {
  const rows = [
    row("cashier", [{ code: "cash.withdraw", limit_value: "50000.0000" }]),
    row("manager", [
      { code: "cash.withdraw", limit_value: "100000.0000" },
      { code: "cash.withdraw", limit_value: "500000.0000" },
    ]),
    row("owner", [{ code: "cash.withdraw", limit_value: null }]),
    row("blocked", [{ code: "cash.withdraw", limit_value: null }], { active: false }),
  ];

  it("the most generous limit counts; inactive and the requester are excluded", () => {
    expect(permissionLimit(rows[1] as StaffRow, "cash.withdraw")).toBe("500000.0000");
    expect(eligibleApprovers(rows, "cash.withdraw", "50001.00", "cashier").map((a) => a.userId)).toEqual([
      "manager",
      "owner",
    ]);
    expect(eligibleApprovers(rows, "cash.withdraw", "600000.00", null).map((a) => a.userId)).toEqual([
      "owner",
    ]);
    expect(eligibleApprovers(rows, "cash.withdraw", null, null).map((a) => a.userId)).toEqual(["owner"]);
    expect(eligibleApprovers(rows, "cash.withdraw", "1.00", "owner").map((a) => a.userId)).toEqual([
      "cashier",
      "manager",
    ]);
  });
});

describe("localPinOutcome", () => {
  it("ok → local_pin ApprovalRef; errors mapped", () => {
    expect(localPinOutcome("m", { ok: true, user: row("m", []), mustChangePin: false })).toEqual({
      ok: true,
      approval: {
        mode: "local_pin",
        approved_by: "m",
        pin_verified_locally: true,
        approval_request_id: null,
      },
    });
    expect(localPinOutcome("m", { ok: false, reason: "invalid", attemptsLeft: 2 })).toEqual({
      ok: false,
      error: "PIN_INVALID",
      attemptsLeft: 2,
    });
    expect(localPinOutcome("m", { ok: false, reason: "locked", lockedUntil: "t" })).toEqual({
      ok: false,
      error: "ACCOUNT_LOCKED",
      lockedUntil: "t",
    });
    expect(localPinOutcome("m", { ok: false, reason: "no_verifier" })).toEqual({
      ok: false,
      error: "PIN_NOT_SET",
    });
    expect(localPinOutcome("m", { ok: true, user: row("m", []), mustChangePin: true })).toEqual({
      ok: false,
      error: "PIN_MUST_CHANGE",
    });
  });
});

describe("waitRemoteApproval (18 §9.3 poll)", () => {
  const deps = (statuses: string[]): ApprovalDeps => ({
    staff: async () => [],
    verifyPin: async () => ({ ok: false, reason: "unknown_user" }),
    createRemote: async () => ({ id: "ar-1" }),
    remoteStatus: async () => (statuses.shift() ?? "pending") as never,
    sleep: async () => undefined,
  });
  it("pending → approved gives the remote_request ref", async () => {
    expect(await waitRemoteApproval(deps(["pending", "pending", "approved"]), "ar-1")).toEqual({
      ok: true,
      approval: {
        mode: "remote_request",
        approved_by: null,
        pin_verified_locally: null,
        approval_request_id: "ar-1",
      },
    });
  });
  it("rejected / expired end the wait", async () => {
    expect(await waitRemoteApproval(deps(["rejected"]), "ar-1")).toEqual({ ok: false, status: "rejected" });
    expect(await waitRemoteApproval(deps(["pending", "expired"]), "ar-1")).toEqual({
      ok: false,
      status: "expired",
    });
  });
});

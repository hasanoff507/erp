import { allSettled, fork } from "effector";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@shared/api";
import type { SessionOut, StaffOut } from "@shared/models";

import {
  $deviceFilters,
  $inviteChannels,
  $limitCodes,
  $sessions,
  $staff,
  $staffCursor,
  $staffError,
  $userDevices,
  canRevokeDevice,
  createStaffFx,
  deviceFiltersChanged,
  fetchBranchesFx,
  fetchCatalogFx,
  fetchDevicesFx,
  fetchRolePermissionsFx,
  fetchRolesFx,
  fetchSessionsFx,
  fetchStaffFx,
  fetchUserDevicesFx,
  needsPendingConfirmation,
  pageMounted,
  revokeAllSessionsFx,
  revokeSessionFx,
  sameDraft,
  sessionsUserChanged,
  staffActionsFor,
  staffDisplayStatus,
  staffName,
  staffLoadMore,
  toPermissionsBody,
  updateStaffFx,
  userSelected,
  type TenantDevice,
} from "./index.ts";

const staff = (id: string, patch: Partial<StaffOut> = {}): StaffOut => ({
  user_id: id,
  name: `User ${id}`,
  phone: "+998901234567",
  role_ids: ["r-cashier"],
  branch_ids: ["b-1"],
  status: "active",
  last_login_at: "2026-10-16T08:00:00Z",
  ...patch,
});

const session = (id: string): SessionOut => ({
  session_id: id,
  client_id: "web-bff",
  device_id: null,
  device_kind: "web",
  created_at: "2026-10-16T08:00:00Z",
  last_seen_at: "2026-10-16T09:00:00Z",
  ip: "10.0.0.1",
  user_agent: "Chrome",
  current: false,
});

const device = (patch: Partial<TenantDevice> = {}): TenantDevice => ({
  id: "d-1",
  kind: "android",
  app_version: "1.4.2",
  cash_register_id: "cr-1",
  cash_register_name: "Kassa 1",
  branch_id: "b-1",
  last_seen_at: null,
  last_sync_at: null,
  outbox_pending_count: 0,
  outbox_oldest_pending_at: null,
  has_pending: false,
  revoked_at: null,
  ...patch,
});

function baseHandlers() {
  return [
    [fetchStaffFx, vi.fn(() => Promise.resolve({ items: [staff("u-1")], next_cursor: "c-2" }))],
    [fetchRolesFx, vi.fn(() => Promise.resolve({ items: [], total: 0, page: 1, size: 200 }))],
    [fetchBranchesFx, vi.fn(() => Promise.resolve({ items: [], total: 0, page: 1, size: 200 }))],
  ] as const;
}

describe("BO-11 users model", () => {
  it("loads staff/roles only with settings.users; branches always", async () => {
    const handlers = baseHandlers();
    const scope = fork({ handlers: handlers.map(([fx, fn]) => [fx, fn] as [typeof fx, typeof fn]) });
    await allSettled(pageMounted, { scope, params: { manageUsers: false } });
    expect(handlers[0][1]).not.toHaveBeenCalled();
    expect(handlers[1][1]).not.toHaveBeenCalled();
    expect(handlers[2][1]).toHaveBeenCalledTimes(1);

    await allSettled(pageMounted, { scope, params: { manageUsers: true } });
    expect(handlers[0][1]).toHaveBeenCalledWith({ cursor: null });
    expect(scope.getState($staff).map((s) => s.user_id)).toEqual(["u-1"]);
    expect(scope.getState($staffCursor)).toBe("c-2");
  });

  it("cursor pagination appends without duplicates and stops at the end", async () => {
    const fetchStaff = vi.fn(({ cursor }: { cursor: string | null }) =>
      Promise.resolve(
        cursor === null
          ? { items: [staff("u-1"), staff("u-2")], next_cursor: "c-2" }
          : { items: [staff("u-2"), staff("u-3")], next_cursor: null },
      ),
    );
    const scope = fork({
      handlers: [
        [fetchStaffFx, fetchStaff],
        [fetchRolesFx, baseHandlers()[1][1]],
        [fetchBranchesFx, baseHandlers()[2][1]],
      ],
    });
    await allSettled(pageMounted, { scope, params: { manageUsers: true } });
    await allSettled(staffLoadMore, { scope });
    expect(scope.getState($staff).map((s) => s.user_id)).toEqual(["u-1", "u-2", "u-3"]);
    await allSettled(staffLoadMore, { scope });
    expect(fetchStaff).toHaveBeenCalledTimes(2);
  });

  it("US-M13-04 / QT-M13-04: a created member appears first with the invite channel", async () => {
    const scope = fork({
      values: [[$staff, [staff("u-1")]]],
      handlers: [
        [
          createStaffFx,
          vi.fn(() =>
            Promise.resolve({
              ...staff("u-9", { last_login_at: null, name: "Dilnoza R." }),
              channel_used: "telegram" as const,
            }),
          ),
        ],
      ],
    });
    await allSettled(createStaffFx, {
      scope,
      params: { phone: "+998901112233", name: "Dilnoza R.", roleIds: ["r-cashier"], branchIds: ["b-1"] },
    });
    const list = scope.getState($staff);
    expect(list.map((s) => s.user_id)).toEqual(["u-9", "u-1"]);
    expect(list[0] && staffDisplayStatus(list[0])).toBe("invited");
    expect(scope.getState($inviteChannels)).toEqual({ "u-9": "telegram" });
  });

  it("US-M13-05 / QT-M13-05: blocking updates the row and reloads the user's sessions", async () => {
    const sessions = vi.fn(() => Promise.resolve({ items: [] }));
    const scope = fork({
      values: [
        [$staff, [staff("u-2")]],
        [$sessions, [session("s-1")]],
      ],
      handlers: [
        [
          updateStaffFx,
          vi.fn(() => Promise.resolve({ user_id: "u-2", status: "blocked" as const, sessions_revoked: 1 })),
        ],
        [fetchSessionsFx, sessions],
        [fetchUserDevicesFx, vi.fn(() => Promise.resolve({ items: [] }))],
      ],
    });
    await allSettled(userSelected, { scope, params: "u-2" });
    sessions.mockClear();
    await allSettled(updateStaffFx, { scope, params: { userId: "u-2", status: "blocked" } });
    expect(scope.getState($staff)[0]?.status).toBe("blocked");
    expect(sessions).toHaveBeenCalledWith("u-2");
    expect(scope.getState($sessions)).toEqual([]);
  });

  it("role/branch change keeps the row and patches only the sent fields", async () => {
    const scope = fork({
      values: [[$staff, [staff("u-2")]]],
      handlers: [
        [
          updateStaffFx,
          vi.fn(() => Promise.resolve({ user_id: "u-2", status: "active" as const, sessions_revoked: 0 })),
        ],
      ],
    });
    await allSettled(updateStaffFx, {
      scope,
      params: { userId: "u-2", roleIds: ["r-cashier", "r-store"], branchIds: ["b-1", "b-2"] },
    });
    expect(scope.getState($staff)[0]).toMatchObject({
      role_ids: ["r-cashier", "r-store"],
      branch_ids: ["b-1", "b-2"],
    });
  });

  it("QT-M13-07: revoking one session leaves the other one", async () => {
    const scope = fork({
      handlers: [
        [fetchSessionsFx, vi.fn(() => Promise.resolve({ items: [session("s-1"), session("s-2")] }))],
        [revokeSessionFx, vi.fn(() => Promise.resolve({ user_id: "u-2", sessions_revoked: 1 }))],
        [revokeAllSessionsFx, vi.fn(() => Promise.resolve({ user_id: "u-2", sessions_revoked: 1 }))],
      ],
    });
    await allSettled(sessionsUserChanged, { scope, params: "u-2" });
    expect(scope.getState($sessions)).toHaveLength(2);
    await allSettled(revokeSessionFx, { scope, params: { userId: "u-2", sessionId: "s-1" } });
    expect(scope.getState($sessions).map((s) => s.session_id)).toEqual(["s-2"]);
    await allSettled(revokeAllSessionsFx, { scope, params: "u-2" });
    expect(scope.getState($sessions)).toEqual([]);
  });

  it("drops a late sessions answer for a user no longer shown", async () => {
    let resolveFirst: (v: { items: SessionOut[] }) => void = () => undefined;
    const fetch = vi.fn((userId: string) =>
      userId === "u-1"
        ? new Promise<{ items: SessionOut[] }>((r) => (resolveFirst = r))
        : Promise.resolve({ items: [session("s-b")] }),
    );
    const scope = fork({ handlers: [[fetchSessionsFx, fetch]] });
    const first = allSettled(sessionsUserChanged, { scope, params: "u-1" });
    const second = allSettled(sessionsUserChanged, { scope, params: "u-2" });
    await Promise.resolve();
    resolveFirst({ items: [session("s-a")] });
    await Promise.all([first, second]);
    expect(scope.getState($sessions).map((s) => s.session_id)).toEqual(["s-b"]);
  });

  it("user devices are loaded for the selected user", async () => {
    const scope = fork({
      handlers: [
        [fetchSessionsFx, vi.fn(() => Promise.resolve({ items: [] }))],
        [
          fetchUserDevicesFx,
          vi.fn(() =>
            Promise.resolve({
              items: [
                {
                  id: "d-1",
                  kind: "android" as const,
                  app_version: "1.4.2",
                  cash_register_id: null,
                  cash_register_name: null,
                  branch_id: null,
                  last_seen_at: null,
                  last_sync_at: null,
                  revoked_at: null,
                },
              ],
            }),
          ),
        ],
      ],
    });
    await allSettled(userSelected, { scope, params: "u-3" });
    expect(scope.getState($userDevices)).toHaveLength(1);
  });

  it("staff load error is kept for the ErrorState", async () => {
    const error = new ApiError({ status: 500, code: "INTERNAL_ERROR", messageKey: "errors.internal_error" });
    const scope = fork({
      handlers: [
        [fetchStaffFx, vi.fn(() => Promise.reject(error))],
        [fetchRolesFx, baseHandlers()[1][1]],
        [fetchBranchesFx, baseHandlers()[2][1]],
      ],
    });
    await allSettled(pageMounted, { scope, params: { manageUsers: true } });
    expect(scope.getState($staffError)).toBe(error);
  });

  it("device filters reset the page and refetch with the new filter", async () => {
    const fetch = vi.fn(() => Promise.resolve({ items: [device()], total: 1, page: 1, size: 50 }));
    const scope = fork({ handlers: [[fetchDevicesFx, fetch]] });
    await allSettled(deviceFiltersChanged, { scope, params: { kind: "android", includeRevoked: true } });
    expect(scope.getState($deviceFilters)).toEqual({
      branchId: null,
      kind: "android",
      includeRevoked: true,
      page: 1,
    });
    expect(fetch).toHaveBeenCalledWith({ branchId: null, kind: "android", includeRevoked: true, page: 1 });
  });

  it("US-M13-03: limit body only for limit codes; empty limit = unlimited (null)", async () => {
    const scope = fork({
      handlers: [
        [
          fetchCatalogFx,
          vi.fn(() =>
            Promise.resolve({
              items: [
                { code: "discount.give", module: "M03", description: "", requires_limit: true },
                { code: "sales.create", module: "M01", description: "", requires_limit: false },
              ],
            }),
          ),
        ],
        [fetchRolePermissionsFx, vi.fn(() => Promise.resolve({ role_id: "r", permissions: [] }))],
      ],
    });
    await allSettled(fetchCatalogFx, { scope });
    const limitCodes = scope.getState($limitCodes);
    expect(
      toPermissionsBody(
        [
          { code: "discount.give", limit: "8.00" },
          { code: "sales.create", limit: "5" },
          { code: "returns.approve", limit: "" },
        ],
        limitCodes,
      ),
    ).toEqual({
      permissions: [
        { code: "discount.give", limit_value: "8.00" },
        { code: "sales.create", limit_value: null },
        { code: "returns.approve", limit_value: null },
      ],
    });
    expect(sameDraft([{ code: "a", limit: "" }], [{ code: "a", limit: "" }])).toBe(true);
    expect(sameDraft([{ code: "a", limit: "" }], [{ code: "a", limit: "5.00" }])).toBe(false);
  });

  it("device revoke rules: onec_agent is view-only; pending events need confirmation", () => {
    expect(canRevokeDevice(device({ kind: "onec_agent" }))).toBe(false);
    expect(canRevokeDevice(device({ revoked_at: "2026-10-16T00:00:00Z" }))).toBe(false);
    expect(canRevokeDevice(device())).toBe(true);
    expect(needsPendingConfirmation(device({ has_pending: true, outbox_pending_count: 37 }))).toBe(true);
    expect(needsPendingConfirmation(device())).toBe(false);
  });
});

describe("membership status `invited` (existing user invited by phone, code not redeemed yet)", () => {
  // The generated StaffOut does not know `invited` yet — the UI compares the status as a string.
  const pending = staff("u-5", {
    status: "invited" as StaffOut["status"],
    name: "",
    last_login_at: "2026-10-01T08:00:00Z",
    ...({ invited_name: "Dilshod" } as Partial<StaffOut>),
  });

  it("shows as a pending invite, with the invited name, and offers no credential resets", () => {
    expect(staffDisplayStatus(pending)).toBe("pending");
    expect(staffName(pending)).toBe("Dilshod");
    expect(staffActionsFor(pending)).toEqual({ resetCredentials: false, block: true, unblock: false });
  });

  it("keeps the old rules for active/blocked members", () => {
    expect(staffDisplayStatus(staff("u-1"))).toBe("active");
    expect(staffDisplayStatus(staff("u-1", { last_login_at: null }))).toBe("invited");
    expect(staffActionsFor(staff("u-1", { status: "blocked" }))).toEqual({
      resetCredentials: true,
      block: false,
      unblock: true,
    });
    expect(staffName(staff("u-1"))).toBe("User u-1");
  });
});

import { combine, createStore } from "effector";

import type { ApiError } from "@shared/api";

import type {
  Branch,
  CatalogItem,
  DeviceFilters,
  InviteChannel,
  Role,
  RolePermission,
  Session,
  Staff,
  TenantDevice,
  UserDevice,
} from "../types/index.ts";

// --- Xodimlar ------------------------------------------------------------------------------------
export const $staff = createStore<Staff[]>([]);
export const $staffCursor = createStore<string | null>(null);
export const $staffLoaded = createStore(false);
export const $staffError = createStore<ApiError | null>(null);
/** Channel the invite code went through, for rows created in this visit ("Taklif yuborildi · Telegram"). */
export const $inviteChannels = createStore<Record<string, InviteChannel>>({});

export const $roles = createStore<Role[]>([]);
export const $rolesError = createStore<ApiError | null>(null);
export const $branches = createStore<Branch[]>([]);

export const $selectedUserId = createStore<string | null>(null);
export const $selectedUser = combine(
  $staff,
  $selectedUserId,
  (staff, id) => staff.find((s) => s.user_id === id) ?? null,
);

// --- Sessions / devices of one user ----------------------------------------------------------------
export const $sessionsUserId = createStore<string | null>(null);
export const $sessions = createStore<Session[]>([]);
export const $sessionsError = createStore<ApiError | null>(null);
export const $userDevices = createStore<UserDevice[]>([]);
export const $userDevicesError = createStore<ApiError | null>(null);

// --- Rollar ----------------------------------------------------------------------------------------
export const $catalog = createStore<CatalogItem[]>([]);
export const $catalogError = createStore<ApiError | null>(null);
export const $selectedRoleId = createStore<string | null>(null);
export const $selectedRole = combine(
  $roles,
  $selectedRoleId,
  (roles, id) => roles.find((r) => r.id === id) ?? null,
);
export const $rolePermissions = createStore<RolePermission[]>([]);
export const $rolePermissionsError = createStore<ApiError | null>(null);
/** Codes that take a `limit_value` (catalog `requires_limit`). */
export const $limitCodes = $catalog.map(
  (items) => new Set(items.filter((i) => i.requires_limit).map((i) => i.code)) as ReadonlySet<string>,
);

// --- Qurilmalar --------------------------------------------------------------------------------------
export const INITIAL_DEVICE_FILTERS: DeviceFilters = {
  branchId: null,
  kind: null,
  includeRevoked: false,
  page: 1,
};
export const $deviceFilters = createStore<DeviceFilters>(INITIAL_DEVICE_FILTERS);
export const $devices = createStore<TenantDevice[]>([]);
export const $devicesTotal = createStore(0);
export const $devicesLoaded = createStore(false);
export const $devicesError = createStore<ApiError | null>(null);

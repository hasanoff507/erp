/**
 * BO-11 data effects — generated client only (24 §3). Writes carry Idempotency-Key + CSRF through
 * the shared axios instance. Endpoints: 14 §18.2 (admin users), 20 #24–#29b (roles, devices).
 */
import { createEffect } from "effector";

import { api, type ApiError } from "@shared/api";
import type {
  BranchPageOut,
  CatalogOut,
  CredentialResetOut,
  DeviceListOut,
  DevicePageOut,
  DeviceRevokedOut,
  MembershipStatusOut,
  RoleNameOut,
  RoleOut,
  RolePageOut,
  RolePermissionsOut,
  SessionListOut,
  SessionsRevokedOut,
  StaffCreatedOut,
  StaffPageOut,
} from "@shared/models";

import { toPermissionsBody } from "../lib/index.ts";
import {
  DEVICE_PAGE_SIZE,
  STAFF_PAGE_SIZE,
  type CreateStaffInput,
  type DeviceFilters,
  type PermissionsDraftRow,
  type RevokeDeviceInput,
  type UpdateStaffInput,
} from "../types/index.ts";

export const fetchStaffFx = createEffect<{ cursor: string | null }, StaffPageOut, ApiError>(({ cursor }) =>
  api.auth.adminUsersList({ ...(cursor ? { cursor } : {}), limit: STAFF_PAGE_SIZE }),
);

export const fetchRolesFx = createEffect<void, RolePageOut, ApiError>(() =>
  api.access.rolesList({ page: 1, size: 200 }),
);

export const fetchBranchesFx = createEffect<void, BranchPageOut, ApiError>(() =>
  api.branches.listBranches({ page: 1, size: 200 }),
);

export const createStaffFx = createEffect<CreateStaffInput, StaffCreatedOut, ApiError>((input) =>
  api.auth.adminUsersCreate({
    phone: input.phone,
    name: input.name.trim(),
    role_ids: input.roleIds,
    branch_ids: input.branchIds,
  }),
);

export const updateStaffFx = createEffect<UpdateStaffInput, MembershipStatusOut, ApiError>((input) =>
  api.auth.adminUsersUpdate(input.userId, {
    ...(input.status ? { status: input.status } : {}),
    ...(input.roleIds ? { role_ids: input.roleIds } : {}),
    ...(input.branchIds ? { branch_ids: input.branchIds } : {}),
  }),
);

export const resetPasswordFx = createEffect<string, CredentialResetOut, ApiError>((userId) =>
  api.auth.adminUsersResetPassword(userId),
);

export const resetPinFx = createEffect<string, CredentialResetOut, ApiError>((userId) =>
  api.auth.adminUsersResetPin(userId),
);

export const fetchSessionsFx = createEffect<string, SessionListOut, ApiError>((userId) =>
  api.auth.adminUsersSessionsList(userId),
);

export const revokeSessionFx = createEffect<
  { userId: string; sessionId: string },
  SessionsRevokedOut,
  ApiError
>(({ userId, sessionId }) => api.auth.adminUsersRevokeSession(userId, sessionId));

export const revokeAllSessionsFx = createEffect<string, SessionsRevokedOut, ApiError>((userId) =>
  api.auth.adminUsersRevokeSessions(userId),
);

export const fetchUserDevicesFx = createEffect<string, DeviceListOut, ApiError>((userId) =>
  api.auth.adminUsersDevicesList(userId),
);

export const fetchCatalogFx = createEffect<void, CatalogOut, ApiError>(() =>
  api.access.permissionsCatalogList(),
);

export const fetchRolePermissionsFx = createEffect<string, RolePermissionsOut, ApiError>((roleId) =>
  api.access.rolesPermissionsGet(roleId),
);

export const replaceRolePermissionsFx = createEffect<
  { roleId: string; rows: readonly PermissionsDraftRow[]; limitCodes: ReadonlySet<string> },
  RolePermissionsOut,
  ApiError
>(({ roleId, rows, limitCodes }) =>
  api.access.rolesPermissionsReplace(roleId, toPermissionsBody(rows, limitCodes)),
);

export const createRoleFx = createEffect<string, RoleOut, ApiError>((name) =>
  api.access.rolesCreate({ name: name.trim() }),
);

export const renameRoleFx = createEffect<
  { roleId: string; name: string; version: number },
  RoleNameOut,
  ApiError
>(({ roleId, name, version }) => api.access.rolesUpdate(roleId, { name: name.trim(), version }));

export const fetchDevicesFx = createEffect<DeviceFilters, DevicePageOut, ApiError>((f) =>
  api.access.devicesList({
    ...(f.branchId ? { branch_id: f.branchId } : {}),
    ...(f.kind ? { kind: f.kind } : {}),
    include_revoked: f.includeRevoked,
    page: f.page,
    size: DEVICE_PAGE_SIZE,
  }),
);

export const revokeDeviceFx = createEffect<RevokeDeviceInput, DeviceRevokedOut, ApiError>((input) =>
  api.access.devicesRevoke(input.deviceId, {
    reason: input.reason.trim(),
    confirm_pending_loss: input.confirmPendingLoss,
  }),
);

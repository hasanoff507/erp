import type {
  AppModulesAuthApiAdminUsersDeviceOut,
  AppModulesBranchesApiDevicesDeviceOut,
  BranchListItemOut,
  CatalogItemOut,
  PermissionOut,
  RoleOut,
  SessionOut,
  StaffOut,
} from "@shared/models";

/** BO-11 tabs (07): Xodimlar · Rollar · Qurilmalar · Sessiyalar. */
export type UsersTab = "staff" | "roles" | "devices" | "sessions";
export const USERS_TABS: readonly UsersTab[] = ["staff", "roles", "devices", "sessions"];

export type LoadStatus = "idle" | "loading" | "error";
export type InviteChannel = "telegram" | "sms";

export type Staff = StaffOut;
export type Role = RoleOut;
export type Branch = BranchListItemOut;
export type Session = SessionOut;
export type UserDevice = AppModulesAuthApiAdminUsersDeviceOut;
export type TenantDevice = AppModulesBranchesApiDevicesDeviceOut;
export type CatalogItem = CatalogItemOut;
export type RolePermission = PermissionOut;

export type DeviceKind = "web" | "android" | "onec_agent";

/** GET /devices filters (20 #29a) + page. */
export interface DeviceFilters {
  branchId: string | null;
  kind: DeviceKind | null;
  includeRevoked: boolean;
  page: number;
}

export const DEVICE_PAGE_SIZE = 50;
export const STAFF_PAGE_SIZE = 50;

/**
 * Row status chip: an active member who never logged in is still an open invite (mockup Bo11);
 * `pending` = the membership itself is `invited` — an existing user (another store's employee) was
 * invited by phone and has not redeemed the invite code yet.
 */
export type StaffDisplayStatus = "active" | "blocked" | "invited" | "pending";

export interface CreateStaffInput {
  phone: string;
  name: string;
  roleIds: string[];
  branchIds: string[];
}

export interface UpdateStaffInput {
  userId: string;
  status?: "active" | "blocked";
  roleIds?: string[];
  branchIds?: string[];
}

export interface RevokeDeviceInput {
  deviceId: string;
  reason: string;
  confirmPendingLoss: boolean;
}

export interface PermissionsDraftRow {
  code: string;
  /** "" = no limit (NULL — unlimited) */
  limit: string;
}

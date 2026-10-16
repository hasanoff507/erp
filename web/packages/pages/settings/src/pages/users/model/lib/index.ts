import type {
  PermissionsDraftRow,
  RolePermission,
  Staff,
  StaffDisplayStatus,
  TenantDevice,
} from "../types/index.ts";

export function staffDisplayStatus(staff: Staff): StaffDisplayStatus {
  // Compared as a string: the membership status `invited` is newer than the generated StaffOut model.
  const status: string = staff.status;
  if (status === "blocked") return "blocked";
  if (status === "invited") return "pending";
  return staff.last_login_at === null ? "invited" : "active";
}

/** Name to show: a pending membership may carry the inviter's `invited_name` instead of the user's own. */
export function staffName(staff: Staff): string {
  const invited = (staff as Staff & { invited_name?: string | null }).invited_name;
  return staff.name.trim() !== "" ? staff.name : (invited ?? "");
}

/**
 * Which row actions make sense for a status: a pending invite has no credentials or sessions in this
 * store yet (only roles/branches can be changed, or the invite withdrawn by blocking); a blocked
 * member can only be unblocked or edited.
 */
export function staffActionsFor(staff: Staff): {
  resetCredentials: boolean;
  block: boolean;
  unblock: boolean;
} {
  const status = staffDisplayStatus(staff);
  return {
    resetCredentials: status !== "pending",
    block: status !== "blocked",
    unblock: status === "blocked",
  };
}

/** Upserts by `user_id`, keeping list order (new rows first). */
export function upsertStaff(list: readonly Staff[], row: Staff): Staff[] {
  const index = list.findIndex((s) => s.user_id === row.user_id);
  if (index === -1) return [row, ...list];
  const next = [...list];
  next[index] = row;
  return next;
}

export function patchStaff(list: readonly Staff[], userId: string, patch: Partial<Staff>): Staff[] {
  return list.map((s) => (s.user_id === userId ? { ...s, ...patch } : s));
}

/** Appends a cursor page without duplicates (a row created meanwhile may come again). */
export function appendStaff(list: readonly Staff[], page: readonly Staff[]): Staff[] {
  const seen = new Set(list.map((s) => s.user_id));
  return [...list, ...page.filter((s) => !seen.has(s.user_id))];
}

/** Server permissions → editor rows (limit "" = unlimited). */
export function toDraft(permissions: readonly RolePermission[]): PermissionsDraftRow[] {
  return permissions.map((p) => ({ code: p.code, limit: p.limit_value ?? "" }));
}

/** Editor rows → PUT /roles/{id}/permissions body; limits only on limit codes (20 #28). */
export function toPermissionsBody(
  rows: readonly PermissionsDraftRow[],
  limitCodes: ReadonlySet<string>,
): { permissions: { code: string; limit_value: string | null }[] } {
  return {
    permissions: rows.map((r) => ({
      code: r.code,
      limit_value: limitCodes.has(r.code) && r.limit.trim() !== "" ? r.limit.trim() : null,
    })),
  };
}

/** Same set of codes and limits (order-insensitive) — "Saqlash" is enabled only when dirty. */
export function sameDraft(a: readonly PermissionsDraftRow[], b: readonly PermissionsDraftRow[]): boolean {
  if (a.length !== b.length) return false;
  const map = new Map(a.map((r) => [r.code, r.limit]));
  return b.every((r) => map.has(r.code) && map.get(r.code) === r.limit);
}

/** Devices tab: an Android/web device with unsent events needs the pending-loss confirmation. */
export function needsPendingConfirmation(device: TenantDevice): boolean {
  return device.has_pending || (device.outbox_pending_count ?? 0) > 0;
}

/** 20 #29a: `onec_agent` devices are shown only; they are revoked in the 1C screens (33 §10). */
export function canRevokeDevice(device: TenantDevice): boolean {
  return device.kind !== "onec_agent" && device.revoked_at === null;
}

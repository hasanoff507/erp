import { sample } from "effector";

import {
  createRoleFx,
  createStaffFx,
  fetchBranchesFx,
  fetchCatalogFx,
  fetchDevicesFx,
  fetchRolePermissionsFx,
  fetchRolesFx,
  fetchSessionsFx,
  fetchStaffFx,
  fetchUserDevicesFx,
  renameRoleFx,
  replaceRolePermissionsFx,
  resetPasswordFx,
  revokeAllSessionsFx,
  revokeDeviceFx,
  revokeSessionFx,
  updateStaffFx,
} from "../effects/index.ts";
import {
  deviceFiltersChanged,
  devicesPageChanged,
  devicesReloadRequested,
  devicesTabOpened,
  pageMounted,
  roleSelected,
  rolesTabOpened,
  sessionsReloadRequested,
  sessionsUserChanged,
  staffLoadMore,
  staffReloadRequested,
  userSelected,
} from "../events/index.ts";
import { appendStaff, patchStaff, upsertStaff } from "../lib/index.ts";
import {
  $branches,
  $catalog,
  $catalogError,
  $deviceFilters,
  $devices,
  $devicesError,
  $devicesLoaded,
  $devicesTotal,
  $inviteChannels,
  $rolePermissions,
  $rolePermissionsError,
  $roles,
  $rolesError,
  $selectedRoleId,
  $selectedUserId,
  $sessions,
  $sessionsError,
  $sessionsUserId,
  $staff,
  $staffCursor,
  $staffError,
  $staffLoaded,
  $userDevices,
  $userDevicesError,
} from "../stores/index.ts";

// --- Page entry: first staff page, roles and branches (pickers + names in the table) ----------------
$selectedUserId.reset(pageMounted);
$inviteChannels.reset(pageMounted);
$deviceFilters.reset(pageMounted);

sample({
  clock: pageMounted,
  filter: ({ manageUsers }) => manageUsers,
  fn: () => ({ cursor: null }),
  target: fetchStaffFx,
});
sample({ clock: pageMounted, filter: ({ manageUsers }) => manageUsers, target: fetchRolesFx });
sample({ clock: staffReloadRequested, fn: () => ({ cursor: null }), target: fetchStaffFx });
sample({ clock: pageMounted, target: fetchBranchesFx });

sample({
  clock: staffLoadMore,
  source: { cursor: $staffCursor, pending: fetchStaffFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ cursor }) => ({ cursor }),
  target: fetchStaffFx,
});

$staff.on(fetchStaffFx.done, (list, { params, result }) =>
  params.cursor === null ? result.items : appendStaff(list, result.items),
);
$staffCursor.on(fetchStaffFx.doneData, (_, page) => page.next_cursor);
$staffLoaded.on(fetchStaffFx.done, () => true);
$staffError.on(fetchStaffFx.failData, (_, error) => error).reset(fetchStaffFx.done);

$roles.on(fetchRolesFx.doneData, (_, page) => page.items);
$rolesError.on(fetchRolesFx.failData, (_, error) => error).reset(fetchRolesFx.done);
$branches.on(fetchBranchesFx.doneData, (_, page) => page.items);

// --- Writes on staff rows ----------------------------------------------------------------------------
$staff.on(createStaffFx.doneData, (list, created) =>
  upsertStaff(list, {
    user_id: created.user_id,
    name: created.name,
    phone: created.phone,
    role_ids: created.role_ids,
    branch_ids: created.branch_ids,
    status: created.status,
    last_login_at: created.last_login_at,
  }),
);
$inviteChannels.on(createStaffFx.doneData, (map, created) => ({
  ...map,
  [created.user_id]: created.channel_used,
}));

$staff.on(updateStaffFx.done, (list, { params, result }) =>
  patchStaff(list, result.user_id, {
    status: result.status,
    ...(params.roleIds ? { role_ids: params.roleIds } : {}),
    ...(params.branchIds ? { branch_ids: params.branchIds } : {}),
  }),
);

// --- Selected user: sessions + devices ---------------------------------------------------------------
$selectedUserId.on(userSelected, (_, id) => id);
$sessionsUserId.on(userSelected, (current, id) => id ?? current).on(sessionsUserChanged, (_, id) => id);

sample({ clock: userSelected, filter: (id): id is string => id !== null, target: fetchUserDevicesFx });
sample({
  clock: [sessionsUserChanged, userSelected],
  filter: (id): id is string => id !== null,
  target: fetchSessionsFx,
});
sample({
  clock: sessionsReloadRequested,
  source: $sessionsUserId,
  filter: (id): id is string => id !== null,
  target: fetchSessionsFx,
});
// Blocking / password reset / revoke-all end every session of that user (14 §18.2) → refresh the list.
sample({
  clock: updateStaffFx.done,
  source: $sessionsUserId,
  filter: (current, { params }): current is string => current !== null && current === params.userId,
  target: fetchSessionsFx,
});
sample({
  clock: resetPasswordFx.done,
  source: $sessionsUserId,
  filter: (current, { params }): current is string => current !== null && current === params,
  target: fetchSessionsFx,
});

// Late answers for a user who is no longer shown are dropped.
sample({
  clock: fetchSessionsFx.done,
  source: $sessionsUserId,
  filter: (current, { params }) => current === params,
  fn: (_, { result }) => result.items,
  target: $sessions,
});
sample({
  clock: revokeAllSessionsFx.done,
  source: $sessionsUserId,
  filter: (current, { params }) => current === params,
  fn: () => [],
  target: $sessions,
});
$sessions
  .on(sessionsUserChanged, () => [])
  .on(revokeSessionFx.done, (list, { params }) => list.filter((s) => s.session_id !== params.sessionId));
$sessionsError
  .on(fetchSessionsFx.failData, (_, error) => error)
  .reset([fetchSessionsFx.done, sessionsUserChanged]);

sample({
  clock: fetchUserDevicesFx.done,
  source: $selectedUserId,
  filter: (current, { params }) => current === params,
  fn: (_, { result }) => result.items,
  target: $userDevices,
});
$userDevices.reset(userSelected);
$userDevicesError
  .on(fetchUserDevicesFx.failData, (_, error) => error)
  .reset([fetchUserDevicesFx.done, userSelected]);

// --- Rollar ------------------------------------------------------------------------------------------
sample({ clock: rolesTabOpened, source: $catalog, filter: (c) => c.length === 0, target: fetchCatalogFx });
$catalog.on(fetchCatalogFx.doneData, (_, catalog) => catalog.items);
$catalogError.on(fetchCatalogFx.failData, (_, error) => error).reset(fetchCatalogFx.done);

// The first role is preselected when the tab opens.
sample({
  clock: [rolesTabOpened, fetchRolesFx.done],
  source: { roles: $roles, selected: $selectedRoleId },
  filter: ({ roles, selected }) => selected === null && roles.length > 0,
  fn: ({ roles }) => roles[0]?.id ?? null,
  target: roleSelected,
});
$selectedRoleId.on(roleSelected, (_, id) => id);
sample({ clock: roleSelected, filter: (id): id is string => id !== null, target: fetchRolePermissionsFx });

sample({
  clock: fetchRolePermissionsFx.done,
  source: $selectedRoleId,
  filter: (current, { params }) => current === params,
  fn: (_, { result }) => result.permissions,
  target: $rolePermissions,
});
sample({
  clock: replaceRolePermissionsFx.done,
  source: $selectedRoleId,
  filter: (current, { params }) => current === params.roleId,
  fn: (_, { result }) => result.permissions,
  target: $rolePermissions,
});
$rolePermissions.reset(roleSelected);
$rolePermissionsError
  .on(fetchRolePermissionsFx.failData, (_, error) => error)
  .reset([fetchRolePermissionsFx.done, roleSelected]);

$roles
  .on(createRoleFx.doneData, (roles, role) => [...roles, role])
  .on(renameRoleFx.doneData, (roles, renamed) =>
    roles.map((r) => (r.id === renamed.id ? { ...r, name: renamed.name, version: renamed.version } : r)),
  );
sample({ clock: createRoleFx.doneData, fn: (role) => role.id, target: roleSelected });

// --- Qurilmalar ----------------------------------------------------------------------------------------
$deviceFilters
  .on(deviceFiltersChanged, (filters, patch) => ({ ...filters, ...patch, page: 1 }))
  .on(devicesPageChanged, (filters, page) => ({ ...filters, page }));

sample({
  clock: [devicesTabOpened, deviceFiltersChanged, devicesPageChanged, devicesReloadRequested],
  source: $deviceFilters,
  target: fetchDevicesFx,
});
sample({
  clock: devicesTabOpened,
  source: $branches,
  filter: (branches) => branches.length === 0,
  target: fetchBranchesFx,
});

sample({
  clock: fetchDevicesFx.done,
  source: $deviceFilters,
  filter: (current, { params }) => current === params,
  fn: (_, { result }) => result.items,
  target: $devices,
});
sample({
  clock: fetchDevicesFx.done,
  source: $deviceFilters,
  filter: (current, { params }) => current === params,
  fn: (_, { result }) => result.total,
  target: $devicesTotal,
});
$devicesLoaded.on(fetchDevicesFx.done, () => true);
$devicesError.on(fetchDevicesFx.failData, (_, error) => error).reset(fetchDevicesFx.done);

$devices.on(revokeDeviceFx.doneData, (list, revoked) =>
  list.map((d) =>
    d.id === revoked.id
      ? { ...d, revoked_at: revoked.revoked_at, outbox_pending_count: revoked.outbox_pending_count }
      : d,
  ),
);
// A revoked device leaves the default list on the next refresh; refresh the user's device list too.
sample({
  clock: revokeDeviceFx.done,
  source: $selectedUserId,
  filter: (id): id is string => id !== null,
  target: fetchUserDevicesFx,
});

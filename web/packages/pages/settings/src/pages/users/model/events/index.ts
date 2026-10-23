import { createEvent } from "effector";

import type { DeviceFilters } from "../types/index.ts";

/** `manageUsers` = the viewer has `settings.users` (staff/roles are loaded only then). */
export const pageMounted = createEvent<{ manageUsers: boolean }>();
export const staffReloadRequested = createEvent();
export const staffLoadMore = createEvent();

/** Opens / closes the staff detail sheet (sessions + devices + actions of one user). */
export const userSelected = createEvent<string | null>();
/** Sessions tab: whose sessions are listed. */
export const sessionsUserChanged = createEvent<string | null>();
export const sessionsReloadRequested = createEvent();

export const rolesTabOpened = createEvent();
export const roleSelected = createEvent<string | null>();

export const devicesTabOpened = createEvent();
export const deviceFiltersChanged = createEvent<Partial<Omit<DeviceFilters, "page">>>();
export const devicesPageChanged = createEvent<number>();
export const devicesReloadRequested = createEvent();

/**
 * Route-level permission guards (24 §2 `ProtectedRoute`, 06 §1.9). The requirement of a path comes
 * from the sidebar definition (nav-items.ts — single source), so menu visibility and URL access agree.
 */
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useGrantedAccess } from "@shared/state/permissions";

import { ProtectedRoute } from "#/features/protected-route/index.ts";
import { firstAllowedNavItem, requiresForPath } from "../ui/sidebar/nav-items.ts";
import { NoPermissionPage, Splash } from "../ui/status/index.tsx";

/** Wraps the child routes of a layout: the current path's sidebar permission is required. */
export function RoutePermissionGuard({ inline = true }: { inline?: boolean }) {
  const { pathname } = useLocation();
  return (
    <ProtectedRoute
      pending={<Splash />}
      noPermission={<NoPermissionPage inline={inline} />}
      requires={requiresForPath(pathname)}
    >
      <Outlet />
    </ProtectedRoute>
  );
}

/** `/` and `/app`: the first screen the user may open; NoPermissionState when there is none. */
export function DefaultRedirect({ inline = false }: { inline?: boolean }) {
  const target = firstAllowedNavItem(useGrantedAccess());
  return target ? <Navigate to={target.to} replace /> : <NoPermissionPage inline={inline} />;
}

/** `/` is outside every layout: check the session first (anonymous → /login?next=%2F). */
export function RootRedirect() {
  return (
    <ProtectedRoute pending={<Splash />} noPermission={<NoPermissionPage />}>
      <DefaultRedirect />
    </ProtectedRoute>
  );
}

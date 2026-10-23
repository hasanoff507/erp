/**
 * protected-route — route-level guard (24 §2: replaces the sample's CheckRole with a permission list).
 * unknown session → `pending`; anonymous → /login?next=… (BO-01 then starts the BFF login, 14 §2.1);
 * several branches but none chosen → BO-01 branch step; missing permission → `noPermission` (NoPermissionState, 403 PERMISSION_DENIED).
 */
import { useUnit } from "effector-react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useCan, type PermissionRequirement } from "@shared/state/permissions";
import { $authStatus, $branchChoiceRequired } from "@shared/state/session";

export interface ProtectedRouteProps {
  children: ReactNode;
  pending: ReactNode;
  noPermission: ReactNode;
  requires?: PermissionRequirement;
}

export function ProtectedRoute({ children, pending, noPermission, requires = {} }: ProtectedRouteProps) {
  const [status, branchChoiceRequired] = useUnit([$authStatus, $branchChoiceRequired]);
  const location = useLocation();
  const allowed = useCan(requires);

  if (status === "unknown") return <>{pending}</>;
  if (status === "anonymous") {
    const next = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (branchChoiceRequired) {
    // Several branches, none chosen yet → BO-01 branch step (07 `branchId`).
    const next = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (!allowed) return <>{noPermission}</>;
  return <>{children}</>;
}

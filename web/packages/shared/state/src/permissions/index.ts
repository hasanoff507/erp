/**
 * Permission checks — 24 §2: route level `ProtectedRoute`, button level `<Can permission="debts.forgive">`;
 * sidebar items per exact code (06 §1.9: no permission → no item).
 *
 * GET /auth/session returns the effective `permissions` (codes, 15 §2.1) and the token `scope`
 * (their prefixes, 14 §10). The scope is applied first as a coarse module filter, then the exact code.
 * The server's `require_permission` remains the final decision (403 PERMISSION_DENIED → NoPermissionState).
 */
import { useUnit } from "effector-react";
import { createElement, Fragment, type ReactNode } from "react";

import { $permissions, $scopes } from "../session/index.ts";

export interface PermissionRequirement {
  /** All listed codes are required (`<module>.<action>`). */
  permission?: string | readonly string[];
  /** At least one of the listed codes is required. */
  anyOf?: readonly string[];
}

export interface GrantedAccess {
  permissions: readonly string[];
  scopes: readonly string[];
}

/** `debts.payment.accept` → `debts` (same rule as the backend `permission_prefix`). */
export function permissionPrefix(code: string): string {
  const dot = code.indexOf(".");
  return dot === -1 ? code : code.slice(0, dot);
}

export function hasPermissions(granted: GrantedAccess, req: PermissionRequirement): boolean {
  const scopes = new Set(granted.scopes);
  const codes = new Set(granted.permissions);
  const allowed = (code: string) => scopes.has(permissionPrefix(code)) && codes.has(code);
  const all =
    req.permission === undefined
      ? []
      : typeof req.permission === "string"
        ? [req.permission]
        : req.permission;
  if (!all.every(allowed)) return false;
  if (req.anyOf && req.anyOf.length > 0 && !req.anyOf.some(allowed)) return false;
  return true;
}

export function useGrantedAccess(): GrantedAccess {
  const [permissions, scopes] = useUnit([$permissions, $scopes]);
  return { permissions, scopes };
}

export function useCan(req: PermissionRequirement): boolean {
  return hasPermissions(useGrantedAccess(), req);
}

export interface CanProps extends PermissionRequirement {
  children: ReactNode;
  fallback?: ReactNode;
}

/** Hides (not disables) UI the user has no right to — 06 §1.9 "ruxsat yo'q — punkt yo'q". */
export function Can({ children, fallback = null, ...req }: CanProps) {
  return createElement(Fragment, null, useCan(req) ? children : fallback);
}

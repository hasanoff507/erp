/**
 * POS-only route gate (16 §1, B3-DoD-01: the shop sells regardless of internet). Normally the same as
 * `ProtectedRoute`. When the FIRST `GET /auth/session` could not be asked at all (network failure — not a
 * 401/403 answer, not a 5xx), a reload of the web POS renders from local state instead of the splash, but only
 * if this browser holds a registered device identity (erp-device); other screens also need a PIN-verified cashier (sessionStorage,
 * contracts/pos-session.md) — without a cashier only POS-01 / POS-16 open (local PIN sign-in). The server still checks every call; once the session check answers, the normal
 * rules apply again (401/403/DEVICE_REVOKED → today's behaviour). Back-office routes never use this gate.
 */
import { useUnit } from "effector-react";
import { useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { NETWORK_ERROR } from "@shared/api";
import { deviceIdentity } from "@shared/offline";
import type { PermissionRequirement } from "@shared/state/permissions";
import { $authStatus, $sessionCheckError } from "@shared/state/session";

import { ProtectedRoute } from "./ProtectedRoute.tsx";

const POS_LOGIN_PATH = "/pos/login";
/** Reachable offline without a cashier: POS-01 and POS-16. */
const OFFLINE_OPEN_PATHS = [POS_LOGIN_PATH, "/pos/settings/devices"];

/** sessionStorage key of the PIN-verified cashier (b3-pos-ops `CASHIER_STORAGE_KEY`). */
export const POS_CASHIER_KEY = "erp.pos.cashier";

function hasStoredCashier(): boolean {
  try {
    return Boolean(globalThis.sessionStorage?.getItem(POS_CASHIER_KEY));
  } catch {
    return false;
  }
}

/** `null` while unknown; true when this browser is a registered POS device (erp-device identity). */
function useLocalPosState(enabled: boolean): boolean | null {
  const [state, setState] = useState<boolean | null>(null);
  useEffect(() => {
    if (!enabled) return undefined;
    let alive = true;
    void deviceIdentity
      .get()
      .then((identity) => alive && setState(identity !== null))
      .catch(() => alive && setState(false));
    return () => {
      alive = false;
    };
  }, [enabled]);
  return enabled ? state : null;
}

export interface PosRouteGateProps {
  children: ReactNode;
  pending: ReactNode;
  noPermission: ReactNode;
  requires?: PermissionRequirement;
}

/** `true` when the first session check failed for lack of a network (offline reload). */
export function isOfflineSessionCheck(status: string, error: { code: string } | null): boolean {
  return status === "unknown" && error !== null && error.code === NETWORK_ERROR;
}

/** Offline target: null = render here; POS-01 when no cashier signed in on this tab (UX-05). */
export function offlinePosTarget(pathname: string, cashierStored: boolean): string | null {
  if (cashierStored || OFFLINE_OPEN_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`)))
    return null;
  return POS_LOGIN_PATH;
}

export function PosRouteGate({ children, pending, noPermission, requires }: PosRouteGateProps) {
  const [status, checkError] = useUnit([$authStatus, $sessionCheckError]);
  const { pathname } = useLocation();
  const offline = isOfflineSessionCheck(status, checkError);
  const local = useLocalPosState(offline);
  if (offline) {
    if (local !== true) return <>{pending}</>;
    // a registered device opens POS-01 offline (local PIN, 07 POS-01 offline state); other screens need a cashier
    const target = offlinePosTarget(pathname, hasStoredCashier());
    return target ? <Navigate to={target} replace /> : <>{children}</>;
  }
  return (
    <ProtectedRoute pending={pending} noPermission={noPermission} requires={requires}>
      {children}
    </ProtectedRoute>
  );
}

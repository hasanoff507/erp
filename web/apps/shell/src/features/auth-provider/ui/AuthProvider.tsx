/**
 * auth-provider — BFF session bootstrap (24 §1 / Asosiy xulosa #9, 14 §2.1).
 * The browser never sees an OAuth token: it holds only the HttpOnly `__Host-sid` cookie. On start we
 * ask GET /auth/session; login is a full-page navigation to /auth/login/start (14 §2.1, session model
 * in @shared/state/session). Also wires the API layer's cross-cutting hooks (language, branch,
 * 401/403/network/online).
 */
import { useUnit } from "effector-react";
import { useEffect, type ReactNode } from "react";

import { configureApi } from "@shared/api";
import { currentLanguage } from "@shared/i18n";
import { networkWatchStarted, offlineDetected, onlineDetected } from "@shared/state/network";
import {
  $activeBranchId,
  ALL_BRANCHES,
  sessionCheckRequested,
  sessionHeartbeatEnabled,
  subscriptionRestrictedReceived,
  unauthorizedReceived,
} from "@shared/state/session";

export interface AuthProviderProps {
  children: ReactNode;
  /** Navigation to /login?reason=subscription_expired (router lives in the app layer). */
  onSubscriptionRestricted: () => void;
}

export function AuthProvider({ children, onSubscriptionRestricted }: AuthProviderProps) {
  const [checkSession, enableHeartbeat, watchNetwork] = useUnit([
    sessionCheckRequested,
    sessionHeartbeatEnabled,
    networkWatchStarted,
  ]);

  useEffect(() => {
    configureApi({
      getLanguage: currentLanguage,
      // Read at request time: no stale window between a branch change and a React re-render.
      getBranchId: () => {
        const id = $activeBranchId.getState();
        return id === ALL_BRANCHES ? null : id;
      },
      onUnauthorized: (error) => unauthorizedReceived(error),
      onSubscriptionRestricted: (error) => {
        subscriptionRestrictedReceived(error);
        onSubscriptionRestricted();
      },
      onNetworkError: () => offlineDetected(),
      onOnline: () => onlineDetected(),
    });
    watchNetwork();
    enableHeartbeat(); // ~30 s GET /auth/session while signed in (14 §16.1.4)
    checkSession();
  }, [checkSession, enableHeartbeat, watchNetwork, onSubscriptionRestricted]);

  return <>{children}</>;
}

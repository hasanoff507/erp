/**
 * Dashboard / topbar alerts (20 §17 `alerts[]`, 06 §1.9 bell — one source): the alert types the
 * backend emits (most urgent first), their tone and the in-app link. `message_key` is
 * `reports.alerts.<type>` → the `reports` namespace key `alerts.<type>` with `{{count}}` and
 * `{{amount}}` (formatted money). An unknown type (a newer backend) gets the generic text.
 */
import type { AlertOut, AlertOutSeverity } from "@shared/models";

export type Alert = AlertOut;

export const ALERT_TYPES = [
  "fiscal_unacked",
  "state_report_diff",
  "unsynced_devices",
  "cash_variance",
  "overdue_debts",
  "low_stock",
  "expiring_lots",
  "sync_exceptions",
  "pending_approvals",
  "einvoices_awaiting_signature",
] as const;
export type AlertType = (typeof ALERT_TYPES)[number];

export function isKnownAlert(type: string): type is AlertType {
  return (ALERT_TYPES as readonly string[]).includes(type);
}

export type AlertTone = "destructive" | "warning" | "info";

export function alertTone(severity: AlertOutSeverity): AlertTone {
  return severity === "critical" ? "destructive" : severity === "warning" ? "warning" : "info";
}

/** Only in-app back-office links are followed (the route comes from the API). */
export function alertHref(alert: Pick<Alert, "route">): string {
  return alert.route.startsWith("/app/") || alert.route === "/app" ? alert.route : "/app/dashboard";
}

/** Critical first, then warning, then info; the API order is kept inside a severity. */
export function sortAlerts(alerts: readonly Alert[]): Alert[] {
  const rank: Record<AlertOutSeverity, number> = { critical: 0, warning: 1, info: 2 };
  return alerts
    .map((a, i) => ({ a, i }))
    .sort((x, y) => rank[x.a.severity] - rank[y.a.severity] || x.i - y.i)
    .map(({ a }) => a);
}

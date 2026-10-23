/**
 * «Diqqat talab qiladi» list (07 BO-02, mockup Bo02Dashboard) — also the topbar bell panel (06 §1.9:
 * the same `GET /reports/dashboard` → `alerts[]`). Each alert links to its screen.
 */
import {
  Bell,
  CalendarClock,
  Check,
  FileText,
  Package,
  Receipt,
  RefreshCw,
  Shield,
  Users,
  Wallet,
  WifiOff,
  type LucideIcon,
} from "lucide-react";
import { Link } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { Icon, cn } from "@shared/ui";

import { alertHref, alertTone, isKnownAlert, sortAlerts, type Alert, type AlertType } from "../lib.ts";

const ICONS: Record<AlertType, LucideIcon> = {
  fiscal_unacked: Receipt,
  state_report_diff: Shield,
  unsynced_devices: WifiOff,
  cash_variance: Wallet,
  overdue_debts: Users,
  low_stock: Package,
  expiring_lots: CalendarClock,
  sync_exceptions: RefreshCw,
  pending_approvals: Check,
  einvoices_awaiting_signature: FileText,
};

const TILE = {
  destructive: "bg-destructive-soft",
  warning: "bg-warning-soft",
  info: "bg-info-soft",
} as const;
const ICON_TONE = {
  destructive: "text-destructive-strong",
  warning: "text-warning-strong",
  info: "text-info-strong",
} as const;

export function useAlertText() {
  const { t } = useTranslation("reports");
  return (alert: Alert) => {
    const params = {
      count: alert.count,
      amount: alert.amount === null ? "" : formatMoney(alert.amount),
    };
    if (!isKnownAlert(alert.type)) {
      return { title: t("alertTitles.other"), text: t("alertTexts.other", params) };
    }
    return { title: t(`alertTitles.${alert.type}`), text: t(`alerts.${alert.type}`, params) };
  };
}

export interface AlertListProps {
  alerts: readonly Alert[];
  /** Called after a link is followed (e.g. close the bell popover). */
  onNavigate?: () => void;
  /** Compact rows (bell panel). */
  dense?: boolean;
  label: string;
}

export function AlertList({ alerts, onNavigate, dense, label }: AlertListProps) {
  const text = useAlertText();
  return (
    <ul aria-label={label} className={cn("flex flex-col", dense ? "gap-1.5" : "gap-2.5")}>
      {sortAlerts(alerts).map((alert) => {
        const tone = alertTone(alert.severity);
        const { title, text: body } = text(alert);
        return (
          <li key={alert.type}>
            <Link
              to={alertHref(alert)}
              onClick={onNavigate}
              className={cn(
                "flex items-start gap-3 rounded-xl text-foreground transition-colors hover:bg-accent",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                dense ? "p-2" : "p-3",
                TILE[tone],
              )}
            >
              <span
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-card",
                  ICON_TONE[tone],
                )}
              >
                <Icon as={isKnownAlert(alert.type) ? ICONS[alert.type] : Bell} size="md" />
              </span>
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="text-[14px] font-bold">{title}</span>
                <span className="text-[12px] text-foreground-secondary">{body}</span>
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

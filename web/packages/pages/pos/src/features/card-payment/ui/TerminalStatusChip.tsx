/**
 * TerminalStatusChip (08 §7.2/§7.4): online — success + Wifi «Wi-Fi · ulangan»; busy — warning «Band»;
 * offline/error — destructive + WifiOff «Ulanmagan»; unknown (outcome being checked) — info + RefreshCw.
 */
import { RefreshCw, Wifi, WifiOff } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { StatusChip, type Tone } from "@shared/ui";

import type { TerminalChipStatus } from "../model/types/index.ts";
import { dyn } from "./i18n.ts";

const LOOK: Record<TerminalChipStatus, { tone: Tone; icon: typeof Wifi }> = {
  online: { tone: "success", icon: Wifi },
  busy: { tone: "warning", icon: Wifi },
  offline: { tone: "destructive", icon: WifiOff },
  error: { tone: "destructive", icon: WifiOff },
  unknown: { tone: "info", icon: RefreshCw },
};

export function TerminalStatusChip({
  status,
  className,
}: {
  status: TerminalChipStatus;
  className?: string;
}) {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const look = LOOK[status];
  return (
    <StatusChip tone={look.tone} icon={look.icon} className={className}>
      <span data-testid="terminal-status-chip" data-status={status}>
        {t(`cardPayment.chip.${status}`)}
      </span>
    </StatusChip>
  );
}

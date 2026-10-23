/** Small parts of the BO-12 card terminal block: health chip and the register-row cell. */
import { useUnit } from "effector-react";
import { CreditCard, RefreshCw, Wifi, WifiOff } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatDateTime } from "@shared/lib/date";
import { Icon, StatusChip, type Tone } from "@shared/ui";

import { $cardTerminals, terminalsOf, type CardTerminal } from "../model/index.ts";

export type DynamicT = (key: string, options?: Record<string, unknown>) => string;
/** `t` for keys built from enum values (all exist in uz + ru). */
export const dyn = (t: unknown): DynamicT => t as DynamicT;

const LOOK: Record<string, { tone: Tone; icon: typeof Wifi }> = {
  online: { tone: "success", icon: Wifi },
  busy: { tone: "warning", icon: Wifi },
  offline: { tone: "destructive", icon: WifiOff },
  error: { tone: "destructive", icon: WifiOff },
  unknown: { tone: "info", icon: RefreshCw },
};

/** TerminalStatusChip look (08 §7.2) from `health_status` + `health_checked_at`. */
export function HealthChip({ terminal }: { terminal: CardTerminal }) {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const look = LOOK[terminal.health_status] ?? { tone: "info" as Tone, icon: RefreshCw };
  return (
    <span className="flex flex-col items-start gap-0.5">
      <StatusChip tone={look.tone} icon={look.icon}>
        {t(`cardPayment.chip.${terminal.health_status}`)}
      </StatusChip>
      {terminal.health_checked_at ? (
        <span className="text-[11px] text-muted-foreground">
          {formatDateTime(terminal.health_checked_at)}
        </span>
      ) : null}
    </span>
  );
}

/** «Karta terminali» column of the cash register list (07 BO-12). */
export function RegisterTerminalCell({ registerId }: { registerId: string }) {
  const { t: tt } = useTranslation("settings");
  const t = dyn(tt);
  const terminals = terminalsOf(useUnit($cardTerminals), registerId);
  const first = terminals[0];
  if (!first) {
    return (
      <span className="flex items-center gap-1.5 text-[13px]">
        <Icon as={CreditCard} size="sm" className="text-muted-foreground" />
        {t("cardTerminals.none")}
      </span>
    );
  }
  return (
    <div className="flex flex-col items-start gap-1">
      <span className="text-[13px] font-semibold">
        {first.name}
        {first.tid ? ` · TID ${first.tid}` : ""}
      </span>
      <span className="text-[11px] text-muted-foreground">
        {t(`cardTerminals.adapter.${first.adapter}`)}
        {terminals.length > 1 ? ` · ${t("cardTerminals.count", { count: terminals.length })}` : ""}
      </span>
      <HealthChip terminal={first} />
    </div>
  );
}

/** Status / risk chips shared by the BO-15 tables and the detail panel. */
import { StatusChip, type Tone } from "@shared/ui";

import { useTx } from "#/shared/lib/i18n.ts";

const RISK_TONE: Record<string, Tone> = { green: "success", red: "destructive", unknown: "neutral" };
const STATUS_TONE: Record<string, Tone> = {
  draft: "neutral",
  received: "warning",
  signed: "info",
  sent: "info",
  accepted: "success",
  rejected: "destructive",
  cancelled: "neutral",
  pending_signature: "warning",
  sending: "info",
  registered: "info",
  failed: "destructive",
};

export function RiskChip({ flag }: { flag: string }) {
  const { t } = useTx();
  return (
    <StatusChip tone={RISK_TONE[flag] ?? "neutral"} dot>
      {t(`risk.${flag === "green" || flag === "red" ? flag : "unknown"}`)}
    </StatusChip>
  );
}

/** `scope` picks the wording: e-invoice (`in`/`out`), e-TTN or power of attorney. */
export function DocStatusChip({ status, scope }: { status: string; scope: "in" | "out" | "ettn" | "poa" }) {
  const { t, exists } = useTx();
  const key = `status.${scope}.${status}`;
  return <StatusChip tone={STATUS_TONE[status] ?? "neutral"}>{exists(key) ? t(key) : status}</StatusChip>;
}

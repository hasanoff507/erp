import { useTranslation } from "@shared/i18n";
import { StatusChip, type Tone } from "@shared/ui";

import { ettnViewOf, type EttnView, type Transfer } from "../model/index.ts";

const STATUS_TONE: Readonly<Record<string, Tone>> = {
  draft: "neutral",
  posted: "awaiting-approval",
  sent: "info",
  received: "success",
  discrepancy: "warning",
  cancelled: "neutral",
};

const ETTN_TONE: Readonly<Record<EttnView, Tone>> = {
  pending_signature: "awaiting-approval",
  sending: "info",
  registered: "info",
  received: "info",
  accepted: "success",
  rejected: "destructive",
  cancelled: "neutral",
  failed: "destructive",
  not_required: "neutral",
  none: "neutral",
};

/** 07 BO-03: yo'lda / qabul qilindi / farq bilan; a late transfer is red «Kechikmoqda». */
export function TransferStatusChip({ transfer }: { transfer: Pick<Transfer, "status" | "is_overdue"> }) {
  const { t } = useTranslation("warehouse");
  if (transfer.status === "sent" && transfer.is_overdue) {
    return <StatusChip tone="destructive">{t("transfers.status.overdue")}</StatusChip>;
  }
  return (
    <StatusChip tone={STATUS_TONE[transfer.status] ?? "neutral"}>
      {t(`transfers.status.${transfer.status}`)}
    </StatusChip>
  );
}

/** 07 BO-03 e-TTN column (qaror #63). */
export function EttnChip({ transfer }: { transfer: Pick<Transfer, "transport_mode" | "ettn"> }) {
  const { t } = useTranslation("warehouse");
  const view = ettnViewOf(transfer);
  if (view === "none") return <span className="text-muted-foreground">—</span>;
  return <StatusChip tone={ETTN_TONE[view]}>{t(`ettn.${view}`)}</StatusChip>;
}

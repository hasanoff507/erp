import { useTranslation } from "@shared/i18n";
import { StatusChip, type Tone } from "@shared/ui";

import type { CountStatus } from "../model/index.ts";

const COUNT_TONE: Readonly<Record<string, Tone>> = {
  counting: "info",
  review: "awaiting-approval",
  posted: "success",
  cancelled: "neutral",
};

export function CountStatusChip({ status }: { status: string }) {
  const { t } = useTranslation("warehouse");
  return (
    <StatusChip tone={COUNT_TONE[status] ?? "neutral"}>
      {t(`counts.status.${status as CountStatus}`)}
    </StatusChip>
  );
}

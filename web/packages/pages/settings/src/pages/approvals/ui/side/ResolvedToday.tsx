/**
 * BO-16 right panel: «Bugun hal qilinganlar», the role-limits link (→ BO-11 «Rollar», `users.manage`)
 * and the offline / expiry note.
 */
import { useUnit } from "effector-react";
import { Info } from "lucide-react";
import { Link } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatDateTime } from "@shared/lib/format";
import { Can } from "@shared/state/permissions";
import { Card, Icon, StatusChip } from "@shared/ui";

import { $resolvedToday } from "../../model/index.ts";

export function ResolvedToday() {
  const { t } = useTranslation("settings");
  const resolved = useUnit($resolvedToday);
  return (
    <div className="flex flex-col gap-3.5">
      <Card role="region" aria-labelledby="approvals-resolved-title" className="flex flex-col gap-2">
        <h2 id="approvals-resolved-title" className="text-[15px] font-bold">
          {t("approvals.resolvedToday")}
        </h2>
        {resolved.length === 0 ? (
          <p className="text-small text-muted-foreground">{t("approvals.resolvedTodayEmpty")}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-divider">
            {resolved.map((r) => (
              <li key={r.id} className="flex items-center gap-2 py-2">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[13px] font-semibold">{t(`approvals.kinds.${r.kind}`)}</div>
                  <div className="truncate text-[12px] text-muted-foreground">
                    {r.requested_by_name ?? t("approvals.unknownUser")} ·{" "}
                    {r.resolved_at ? formatDateTime(r.resolved_at) : "—"}
                  </div>
                </div>
                <StatusChip tone={r.status === "rejected" ? "destructive" : "success"} dot>
                  {t(`approvals.status.${r.status}`)}
                </StatusChip>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Can permission="users.manage">
        <Card className="flex flex-col gap-1.5">
          <h2 className="text-[15px] font-bold">{t("approvals.limitsTitle")}</h2>
          <p className="text-small text-foreground-secondary">{t("approvals.limitsHint")}</p>
          <Link to="/app/settings/users?tab=roles" className="text-small font-semibold">
            {t("approvals.limitsLink")}
          </Link>
        </Card>
      </Can>
      <p className="flex gap-2 text-[12px] text-foreground-secondary">
        <Icon as={Info} size="sm" className="mt-0.5 shrink-0" />
        {t("approvals.note")}
      </p>
    </div>
  );
}

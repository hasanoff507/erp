/**
 * BO-08 — Buxgalteriya jurnali, provodkalar (07, route /app/accounting/journal, `accounting.post`).
 * Bosqich 2 part: the journal (20 #9 `GET /ledger-entries`: filters date from/to, account, document
 * type; «Dt oboroti = Kt oboroti»; cursor «Yana yuklash») and «Qayta hisoblash navbati» (19 §18,
 * `stock.view` to see, `accounting.post` to retry). Export (XLSX), «Tuzatuvchi yozuv», «Hisob
 * qoldiqlari» and «Davrni yopish» — Bosqich 5: «Tuzatuvchi yozuvlar» (20 #10/#10a/#10b — create with the
 * dialog, cancel = storno), right panel «Hisob qoldiqlari» (20 #11, `reports.finance.view`) and «Davrni
 * yopish» (20 #14–#16). Export (XLSX) is Bosqich 6 (20 #22/#23) — not rendered.
 * Offline: view only — the retry/create/cancel/close buttons are disabled. useEffect only fires the mounts (24 §2).
 */
import { useUnit } from "effector-react";
import { WifiOff } from "lucide-react";
import { useEffect } from "react";

import { useTranslation } from "@shared/i18n";
import { dayjs } from "@shared/lib/date";
import { $isOnline } from "@shared/state/network";
import { useCan } from "@shared/state/permissions";
import { Banner, Card, NoPermissionState } from "@shared/ui";

import { AdjustmentsList } from "../../adjustments/ui/AdjustmentsList.tsx";
import { balancesEnabled } from "../../balances/model/index.ts";
import { BalancesPanel } from "../../balances/ui/BalancesPanel.tsx";
import { $error, pageMounted } from "../../model/index.ts";
import { PeriodClosingCard } from "../../period-closing/ui/PeriodClosingCard.tsx";
import { Filters } from "../filters/Filters.tsx";
import { RecostQueue } from "../recost/RecostQueue.tsx";
import { JournalTable } from "../table/JournalTable.tsx";

function JournalPage() {
  const { t } = useTranslation("finance");
  const canPost = useCan({ permission: "accounting.post" });
  const canViewRecost = useCan({ permission: "stock.view" });
  const canViewBalances = useCan({ permission: "reports.finance.view" });
  const [mounted, enableBalances, error, online] = useUnit([pageMounted, balancesEnabled, $error, $isOnline]);

  useEffect(() => {
    if (!canPost) return;
    enableBalances(canViewBalances);
    mounted({ today: dayjs().format("YYYY-MM-DD"), canViewRecost });
  }, [mounted, enableBalances, canPost, canViewRecost, canViewBalances]);

  if (!canPost || error?.status === 403) return <NoPermissionState />;

  return (
    <div className="flex flex-col gap-[18px]">
      <p className="text-small text-foreground-secondary">{t("journal.subtitle")}</p>
      {online ? null : (
        <Banner tone="warning" icon={WifiOff}>
          {t("journal.offline")}
        </Banner>
      )}
      <div className="grid items-start gap-[18px] xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex min-w-0 flex-col gap-[18px]">
          <Card className="flex flex-col gap-4">
            <Filters />
            <JournalTable />
          </Card>
          <AdjustmentsList online={online} />
        </div>
        <div className="flex flex-col gap-[18px]">
          <PeriodClosingCard online={online} />
          {canViewBalances ? <BalancesPanel /> : null}
        </div>
      </div>
      {canViewRecost ? <RecostQueue canRetry={canPost} online={online} /> : null}
    </div>
  );
}

export const Journal = {
  route: "accounting/journal",
  titleKey: "finance:journal.title",
  Page: JournalPage,
} as const;

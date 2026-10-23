/**
 * BO-08 — Buxgalteriya jurnali, provodkalar (07, route /app/accounting/journal, `accounting.post`).
 * Bosqich 2 part: the journal (20 #9 `GET /ledger-entries`: filters date from/to, account, document
 * type; «Dt oboroti = Kt oboroti»; cursor «Yana yuklash») and «Qayta hisoblash navbati» (19 §18,
 * `stock.view` to see, `accounting.post` to retry). Export (XLSX), «Tuzatuvchi yozuv», «Hisob
 * qoldiqlari» and «Davrni yopish» are later stages (their APIs are not built yet) — not rendered.
 * Offline: view only — the retry button is disabled. useEffect only fires pageMounted (24 §2).
 */
import { useUnit } from "effector-react";
import { WifiOff } from "lucide-react";
import { useEffect } from "react";

import { useTranslation } from "@shared/i18n";
import { dayjs } from "@shared/lib/date";
import { $isOnline } from "@shared/state/network";
import { useCan } from "@shared/state/permissions";
import { Banner, Card, NoPermissionState } from "@shared/ui";

import { $error, pageMounted } from "../../model/index.ts";
import { Filters } from "../filters/Filters.tsx";
import { RecostQueue } from "../recost/RecostQueue.tsx";
import { JournalTable } from "../table/JournalTable.tsx";

function JournalPage() {
  const { t } = useTranslation("finance");
  const canPost = useCan({ permission: "accounting.post" });
  const canViewRecost = useCan({ permission: "stock.view" });
  const [mounted, error, online] = useUnit([pageMounted, $error, $isOnline]);

  useEffect(() => {
    if (canPost) mounted({ today: dayjs().format("YYYY-MM-DD"), canViewRecost });
  }, [mounted, canPost, canViewRecost]);

  if (!canPost || error?.status === 403) return <NoPermissionState />;

  return (
    <div className="flex flex-col gap-[18px]">
      <p className="text-small text-foreground-secondary">{t("journal.subtitle")}</p>
      {online ? null : (
        <Banner tone="warning" icon={WifiOff}>
          {t("journal.offline")}
        </Banner>
      )}
      <Card className="flex flex-col gap-4">
        <Filters />
        <JournalTable />
      </Card>
      {canViewRecost ? <RecostQueue canRetry={canPost} online={online} /> : null}
    </div>
  );
}

export const Journal = {
  route: "accounting/journal",
  titleKey: "finance:journal.title",
  Page: JournalPage,
} as const;

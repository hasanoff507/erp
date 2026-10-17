/**
 * BO-09 — Hisobotlar markazi (07, route /app/reports; `reports.sales.view` / `reports.finance.view`, the
 * catalogue shows only the reports the user may open). Bosqich 3 part: «Kassa / smena tarixi»
 * (US-M16-03, QT-M16-04) and «QQS registri (qaytarishlar bilan)»; the other reports, PDF/Excel export
 * and the export queue are later stages («Tez orada»). The open report lives in `?report=`.
 * Offline: the last loaded report stays visible (no new requests succeed). useEffect only fires the
 * mount and the URL → model sync (24 §2).
 */
import { useUnit } from "effector-react";
import { ArrowLeft, WifiOff } from "lucide-react";
import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { dayjs } from "@shared/lib/date";
import { $isOnline } from "@shared/state/network";
import { useCan } from "@shared/state/permissions";
import { Banner, Button, Card, Icon, NoPermissionState } from "@shared/ui";

import { isReportKey, pageMounted, reportOpened, type ReportKey } from "../../model/index.ts";
import { CashHistory } from "../cash-history/CashHistory.tsx";
import { Catalog } from "../catalog/Catalog.tsx";
import { VatReturns } from "../vat-returns/VatReturns.tsx";

const REPORT_ACCESS = {
  "cash-history": { anyOf: ["reports.sales.view", "cash.count.shift"] },
  "vat-returns": { permission: "tax.vat.view" },
} as const;

function ReportsPage() {
  const { t } = useTranslation("reports");
  const canView = useCan({
    anyOf: ["reports.sales.view", "reports.finance.view", "tax.vat.view", "cash.count.shift"],
  });
  const canCash = useCan(REPORT_ACCESS["cash-history"]);
  const canVat = useCan(REPORT_ACCESS["vat-returns"]);
  const [mounted, opened, online] = useUnit([pageMounted, reportOpened, $isOnline]);
  const [params, setParams] = useSearchParams();
  const requested = params.get("report");
  const allowed = (key: ReportKey) => (key === "cash-history" ? canCash : canVat);
  const report: ReportKey | null = isReportKey(requested) && allowed(requested) ? requested : null;

  useEffect(() => {
    if (canView) mounted({ today: dayjs().format("YYYY-MM-DD") });
  }, [mounted, canView]);
  useEffect(() => {
    if (canView) opened(report);
  }, [opened, report, canView]);

  if (!canView) return <NoPermissionState />;

  const open = (key: ReportKey | null) => setParams(key ? { report: key } : {}, { replace: false });

  return (
    <div className="flex flex-col gap-[18px]">
      {online ? null : (
        <Banner tone="warning" icon={WifiOff}>
          {t("center.offline")}
        </Banner>
      )}
      {report === null ? (
        <>
          <p className="text-small text-foreground-secondary">{t("center.subtitle")}</p>
          <Catalog onOpen={open} />
        </>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="secondary" size="sm" onClick={() => open(null)}>
              <Icon as={ArrowLeft} size="sm" />
              {t("center.back")}
            </Button>
            <h2 className="text-h2">{t(`center.items.${report}.title`)}</h2>
          </div>
          <Card>{report === "cash-history" ? <CashHistory /> : <VatReturns />}</Card>
        </>
      )}
    </div>
  );
}

export const Reports = {
  route: "reports",
  titleKey: "reports:center.title",
  Page: ReportsPage,
} as const;

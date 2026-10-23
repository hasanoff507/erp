/**
 * BO-09 — Hisobotlar markazi (07, route /app/reports; `reports.sales.view` / `reports.finance.view`, the
 * catalogue shows only the reports the user may open). Bosqich 3: «Kassa / smena tarixi» (US-M16-03,
 * QT-M16-04), «QQS registri (qaytarishlar bilan)». Bosqich 4: «Kunlik savdo», «Kassirlar bo'yicha
 * savdo» (US-M12-01), «Top tovarlar» (US-M12-02), «Ombor qoldig'i» / «Kam qolgan tovarlar»
 * (US-M04-03), «Foyda va zarar» (US-M15-03), «Chegirmalar va marja» (US-M03-03), «Qarzdorlik muddati»;
 * filters — period and branch («Barcha filiallar» = consolidated, US-M14-01). Bosqich 5 (M11, US-M11-02):
 * «Sinov balansi», «Buxgalteriya balansi», «Ombor qoldig'i (sana holatiga)». PDF/Excel export and the
 * export queue are Bosqich 6 (20 #22/#23 `POST /reports/{kod}/export`, `GET /reports/export-jobs/{id}`;
 * B6-EP-20#22/#23), for BO-09 and BO-03 alike. The open report lives in `?report=`. Offline: the last loaded report
 * stays visible. useEffect only fires the mount and the URL → model sync (24 §2).
 */
import { useUnit } from "effector-react";
import { ArrowLeft, WifiOff } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { dayjs } from "@shared/lib/date";
import { $isOnline } from "@shared/state/network";
import { hasPermissions, useCan, useGrantedAccess } from "@shared/state/permissions";
import { $activeBranchId, ALL_BRANCHES } from "@shared/state/session";
import { Banner, Button, Card, Icon, NoPermissionState } from "@shared/ui";

import { REPORT_ACCESS, isReportKey, pageMounted, reportOpened, type ReportKey } from "../../model/index.ts";
import { CashHistory } from "../cash-history/CashHistory.tsx";
import { Catalog } from "../catalog/Catalog.tsx";
import { BalanceSheetReport, StockAsOfReport, TrialBalanceReport } from "../reports/AccountingReports.tsx";
import { AgingReport } from "../reports/AgingReport.tsx";
import { DiscountsReport } from "../reports/DiscountsReport.tsx";
import { PnlReport } from "../reports/PnlReport.tsx";
import { SalesReport } from "../reports/SalesReport.tsx";
import { StockReport } from "../reports/StockReport.tsx";
import { TopProductsReport } from "../reports/TopProductsReport.tsx";
import { VatReturns } from "../vat-returns/VatReturns.tsx";

function ReportView({ report }: { report: ReportKey }): ReactNode {
  switch (report) {
    case "cash-history":
      return <CashHistory />;
    case "vat-returns":
      return <VatReturns />;
    case "daily-sales":
      return <SalesReport byCashier={false} />;
    case "cashier-sales":
      return <SalesReport byCashier />;
    case "top-products":
      return <TopProductsReport />;
    case "stock":
    case "low-stock":
      return <StockReport />;
    case "profit-and-loss":
      return <PnlReport />;
    case "discounts":
      return <DiscountsReport />;
    case "debts-aging":
      return <AgingReport />;
    case "trial-balance":
      return <TrialBalanceReport />;
    case "balance-sheet":
      return <BalanceSheetReport />;
    case "stock-as-of":
      return <StockAsOfReport />;
  }
}

function ReportsPage() {
  const { t } = useTranslation("reports");
  const canView = useCan({
    anyOf: ["reports.sales.view", "reports.finance.view", "tax.vat.view", "cash.count.shift"],
  });
  const granted = useGrantedAccess();
  const [mounted, opened, online, activeBranch] = useUnit([
    pageMounted,
    reportOpened,
    $isOnline,
    $activeBranchId,
  ]);
  const [params, setParams] = useSearchParams();
  const requested = params.get("report");
  const report: ReportKey | null =
    isReportKey(requested) && hasPermissions(granted, REPORT_ACCESS[requested]) ? requested : null;

  useEffect(() => {
    if (!canView) return;
    mounted({
      today: dayjs().format("YYYY-MM-DD"),
      branchId: activeBranch && activeBranch !== ALL_BRANCHES ? activeBranch : null,
    });
    // The topbar branch is only the starting filter (07 «tanlov ekran filtrlari uchun standart qiymat»).
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
          <Card>
            <ReportView report={report} />
          </Card>
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

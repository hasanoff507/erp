/** Shared pieces of the BO-09 report views: load states, totals row text, KPI grid. */
import { useUnit } from "effector-react";
import type { ReactNode } from "react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { ErrorState, Skeleton, cn } from "@shared/ui";

import {
  $reportData,
  $reportError,
  $reportStatus,
  reportReloadRequested,
  type ReportData,
} from "../../model/index.ts";

type DataOf<K extends ReportData["kind"]> = Extract<ReportData, { kind: K }>["data"];

/** Renders `children(data)` once the open report's answer of the given kind is there. */
export function ReportBody<K extends ReportData["kind"]>({
  kind,
  children,
}: {
  kind: K;
  children: (data: DataOf<K>) => ReactNode;
}) {
  const { t } = useTranslation("reports");
  const [data, status, error, reload] = useUnit([
    $reportData,
    $reportStatus,
    $reportError,
    reportReloadRequested,
  ]);
  if (data && data.kind === kind) return <>{children(data.data as DataOf<K>)}</>;
  if (status === "error" && error) {
    return <ErrorState title={t("report.error")} message={serverErrorText(error)} onRetry={reload} />;
  }
  return (
    <div className="flex flex-col gap-3" aria-busy="true">
      <Skeleton className="h-[96px] w-full rounded-2xl" />
      <Skeleton className="h-[240px] w-full rounded-2xl" />
    </div>
  );
}

export function KpiGrid({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div role="group" aria-label={label} className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {children}
    </div>
  );
}

/** A cell of the «Jami» row is bold. */
export function Strong({ on, children }: { on: boolean; children: ReactNode }) {
  return <span className={cn(on && "font-extrabold")}>{children}</span>;
}

export function Toolbar({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-end gap-3">{children}</div>;
}

/**
 * BO-10 — internal tax reconciliation (`07` BO-10; `20` #3–#8). Stage 5 handles manual report upload,
 * comparison, review and recording a portal correction/confirmation. AI-05 explanation is intentionally
 * absent here because it belongs to stage 6; this screen never submits anything to the tax portal.
 */
import { useEffect, useState } from "react";
import { ArrowUpRight, FileText, RefreshCw, Upload, WifiOff } from "lucide-react";
import { NavLink } from "react-router-dom";

import { api, toApiError, type ApiError } from "@shared/api";
import { serverErrorText, useTranslation } from "@shared/i18n";
import { dayjs } from "@shared/lib/date";
import { formatMoney } from "@shared/lib/format";
import { $isOnline } from "@shared/state/network";
import { useCan } from "@shared/state/permissions";
import {
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorState,
  FormField,
  Icon,
  Input,
  NoPermissionState,
  StatusChip,
  Textarea,
} from "@shared/ui";
import { useUnit } from "effector-react";

import {
  compareStateReport,
  confirmStateReport,
  getStateReport,
  listStateReportDiffs,
  listStateReports,
  recordCorrection,
  uploadStateReport,
} from "../../model/api/index.ts";
import type { ReportStatus, StateReport, StateReportDiff, StateReportRow, TaxType } from "../../model/types/index.ts";

const tones: Record<ReportStatus, "neutral" | "info" | "warning" | "success" | "destructive"> = {
  uploaded: "neutral",
  compared: "info",
  match: "success",
  diff_found: "warning",
  correction_sent: "info",
  confirmed: "success",
  auto_accepted: "success",
};

function amount(value: string | null | undefined) {
  return value === null || value === undefined ? "—" : formatMoney(value, { precision: 2 });
}

function ReportStatusSteps({ status }: { status: ReportStatus }) {
  const { t } = useTranslation("finance");
  const steps: ReportStatus[] = ["uploaded", "compared", "diff_found", "correction_sent", "confirmed"];
  const index = steps.indexOf(status);
  const done = status === "match" ? 2 : status === "auto_accepted" ? 4 : index;
  return (
    <ol className="grid grid-cols-2 gap-2 text-[12px] sm:grid-cols-5">
      {steps.map((step, i) => (
        <li key={step} className={i <= done ? "font-bold text-foreground" : "text-foreground-secondary"}>
          <span aria-hidden="true" className="mr-1">{i <= done ? "●" : "○"}</span>{t(`reconciliation.status.${step}`)}
        </li>
      ))}
    </ol>
  );
}

function remainingBusinessDays(deadline: string) {
  let day = dayjs().startOf("day");
  const end = dayjs(deadline).startOf("day");
  let count = 0;
  while (day.isBefore(end) && count < 6) {
    day = day.add(1, "day");
    if (day.day() !== 0 && day.day() !== 6) count += 1;
  }
  return count;
}

function ReconciliationPage() {
  const { t } = useTranslation("finance");
  const canView = useCan({ anyOf: ["tax.vat.view", "tax.compare.review"] });
  const canReview = useCan({ permission: "tax.compare.review" });
  const canSubmit = useCan({ permission: "tax.correction.submit" });
  const online = useUnit($isOnline);
  const today = dayjs().format("YYYY-MM-DD");
  const [taxType, setTaxType] = useState<TaxType>("vat");
  const [taxRegime, setTaxRegime] = useState<TaxType | null>(null);
  const [period, setPeriod] = useState(today.slice(0, 7));
  const [rows, setRows] = useState<StateReportRow[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [report, setReport] = useState<StateReport | null>(null);
  const [diffs, setDiffs] = useState<StateReportDiff[]>([]);
  const [diffFilter, setDiffFilter] = useState<"all" | "open">("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileIssue, setFileIssue] = useState(false);
  const [publishedAt, setPublishedAt] = useState(today);
  const [comment, setComment] = useState("");
  const [portalRef, setPortalRef] = useState("");

  const load = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await listStateReports({ tax_type: taxType, period });
      setRows(result.items);
      setNextCursor(result.next_cursor);
      if (report && result.items.some((item) => item.id === report.id)) await openReport(report.id);
      else if (result.items[0]) await openReport(result.items[0].id);
      else {
        setReport(null);
        setDiffs([]);
      }
    } catch (e) {
      setError(toApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const loadMore = async () => {
    if (!nextCursor || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await listStateReports({ tax_type: taxType, period, cursor: nextCursor });
      setRows((current) => [...current, ...result.items]);
      setNextCursor(result.next_cursor);
    } catch (e) {
      setError(toApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const openReport = async (id: string) => {
    setError(null);
    try {
      const [detail, diffPage] = await Promise.all([getStateReport(id), listStateReportDiffs(id)]);
      setReport(detail);
      setDiffs(diffPage.items);
      setComment(detail.correction_comment ?? "");
      setPortalRef(detail.correction_portal_ref ?? "");
    } catch (e) {
      setError(toApiError(e));
    }
  };

  useEffect(() => {
    if (canView) {
      void load();
      void api.tax.getVatSummary({ period }).then((summary) => setTaxRegime(summary.regime)).catch(() => setTaxRegime(null));
    }
    // The selected report is reloaded only when the filters change or a mutation completes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canView, taxType, period]);

  const mutate = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      await load();
    } catch (e) {
      setError(toApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const upload = async () => {
    if (!file) return;
    const published = `${publishedAt}T00:00:00+05:00`;
    await mutate(() => uploadStateReport({ file, taxType, period, publishedAt: published }));
    setFile(null);
  };

  if (!canView) return <NoPermissionState />;

  const statusLabel = (status: ReportStatus) => t(`reconciliation.status.${status}`);
  const deadlineDays = report ? remainingBusinessDays(report.deadline_at) : 0;
  // The comparison API labels only within-tolerance reports `match`; the report detail DTO does not
  // include the tenant's configured tolerance, so never infer it client-side for `diff_found`.
  const mayConfirm = canSubmit && online && report?.status === "match";
  const visibleDiffs = diffFilter === "open" ? diffs.filter((diff) => !diff.resolved) : diffs;

  return (
    <div className="flex flex-col gap-[18px]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-h2">{t("reconciliation.title")}</h1>
          <p className="mt-1 text-small text-foreground-secondary">{t("reconciliation.subtitle")}</p>
        </div>
        <NavLink className="text-small font-semibold text-primary underline" to="/app/tax/vat">
          {t("reconciliation.internalVat")}
        </NavLink>
      </div>

      {!online ? <Banner tone="warning" icon={WifiOff}>{t("reconciliation.offline")}</Banner> : null}
      {error ? <ErrorState message={serverErrorText(error)} onRetry={() => void load()} /> : null}

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.8fr)]">
        <Card className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-2" role="tablist" aria-label={t("reconciliation.taxType")}>
            {(["vat", "turnover"] as const).map((kind) => (
              <Button key={kind} size="sm" variant={taxType === kind ? "default" : "secondary"}
                role="tab" aria-selected={taxType === kind} onClick={() => setTaxType(kind)}>
                {t(`reconciliation.types.${kind}`)}
              </Button>
            ))}
          </div>
          {taxRegime ? (
            <StatusChip tone={taxRegime === taxType ? "success" : "warning"}>
              {taxRegime === taxType ? t("reconciliation.regime.active") : t("reconciliation.regime.inactive")}
            </StatusChip>
          ) : null}
          <div className="flex items-center justify-between">
            <h2 className="font-bold">{t("reconciliation.previous")}</h2>
            <Button size="sm" variant="ghost" aria-label={t("reconciliation.refresh")} onClick={() => void load()} disabled={busy}>
              <Icon as={RefreshCw} size="sm" />
            </Button>
          </div>
          {rows.length === 0 && !busy ? (
            <EmptyState icon={FileText} title={t("reconciliation.empty.title")} description={t("reconciliation.empty.description")} />
          ) : (
            <ul className="flex flex-col gap-2" aria-busy={busy}>
              {rows.map((row) => (
                <li key={row.id}>
                  <button type="button" onClick={() => void openReport(row.id)}
                    className={`flex w-full items-center justify-between gap-3 rounded-lg border p-3 text-left ${report?.id === row.id ? "border-primary bg-accent" : "border-border"}`}>
                    <span><span className="block font-semibold">{row.period} · {t(`reconciliation.types.${row.tax_type}`)}</span>
                      <span className="text-small text-foreground-secondary">{t("reconciliation.deadline", { date: dayjs(row.deadline_at).format("DD.MM.YYYY") })}</span></span>
                    <StatusChip tone={tones[row.status]}>{statusLabel(row.status)}</StatusChip>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {nextCursor ? <Button variant="secondary" onClick={() => void loadMore()} disabled={busy}>{t("reconciliation.loadMore")}</Button> : null}
          {canReview ? (
            <div className="flex flex-col gap-3 border-t border-border pt-4">
              <h2 className="font-bold">{t("reconciliation.upload.title")}</h2>
              <FormField label={t("reconciliation.period")}>
                <Input type="month" value={period} onChange={(e) => setPeriod(e.target.value)} />
              </FormField>
              <FormField label={t("reconciliation.upload.publishedAt")}>
                <Input type="date" value={publishedAt} onChange={(e) => setPublishedAt(e.target.value)} />
              </FormField>
              <FormField label={t("reconciliation.upload.file")}>
                <Input type="file" accept=".pdf,.xls,.xlsx" onChange={(e) => {
                  const next = e.currentTarget.files?.[0] ?? null;
                  const validType = next === null || /\.(pdf|xls|xlsx)$/i.test(next.name);
                  const validSize = next === null || next.size <= 5 * 1024 * 1024;
                  setFile(next && validType && validSize ? next : null);
                  setFileIssue(!validType || !validSize);
                }} />
              </FormField>
              <p className="text-xs text-foreground-secondary">{t("reconciliation.upload.limit")}</p>
              {fileIssue ? <p role="alert" className="text-small text-destructive-strong">{t("reconciliation.upload.invalidFile")}</p> : null}
              <Button onClick={() => void upload()} disabled={!online || busy || !file || !publishedAt}>
                <Icon as={Upload} size="sm" />{t("reconciliation.upload.action")}
              </Button>
            </div>
          ) : null}
        </Card>

        <Card className="flex min-h-64 flex-col gap-4">
          {!report ? <EmptyState icon={FileText} title={t("reconciliation.selectTitle")} /> : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><h2 className="text-[16px] font-bold">{t(`reconciliation.types.${report.tax_type}`)} · {report.period}</h2>
                  <p className="text-small text-foreground-secondary">{t("reconciliation.published", { date: dayjs(report.published_at).format("DD.MM.YYYY") })}</p></div>
                <StatusChip tone={tones[report.status]} dot>{statusLabel(report.status)}</StatusChip>
              </div>
              <ReportStatusSteps status={report.status} />
              {report.status !== "confirmed" && report.status !== "auto_accepted" ? (
                <Banner tone={deadlineDays <= 1 ? "warning" : "info"} icon={FileText}>
                  {t("reconciliation.countdown", { count: deadlineDays, date: dayjs(report.deadline_at).format("DD.MM.YYYY") })}
                </Banner>
              ) : null}
              <div className="grid gap-3 sm:grid-cols-3">
                {["state", "ours", "diff"].map((key) => (
                  <div key={key} className="rounded-lg border border-border p-3">
                    <p className="text-small text-foreground-secondary">{t(`reconciliation.amounts.${key}`)}</p>
                    <p className="mt-1 text-lg font-extrabold tabular-nums">{amount(key === "state" ? report.state_amount : key === "ours" ? report.our_amount : report.diff_amount)}</p>
                  </div>
                ))}
              </div>
              {report.file_url ? <a className="inline-flex items-center gap-1 text-small font-semibold text-primary underline" href={report.file_url} target="_blank" rel="noreferrer">
                <Icon as={ArrowUpRight} size="sm" />{t("reconciliation.fileLink")}</a> : null}
              <div className="flex flex-wrap gap-2">
                {canReview && online && ["uploaded", "compared", "match", "diff_found"].includes(report.status) ? (
                  <Button variant="secondary" onClick={() => void mutate(() => compareStateReport(report.id))} disabled={busy}>
                    {t("reconciliation.compare")}
                  </Button>
                ) : null}
                {mayConfirm ? (
                  <Button onClick={() => void mutate(() => confirmStateReport(report.id, { comment: comment || undefined }))} disabled={busy}>
                    {t("reconciliation.confirm")}
                  </Button>
                ) : null}
              </div>
              {diffs.length ? (
                <div className="overflow-x-auto">
                  <h3 className="mb-2 font-bold">{t("reconciliation.diffs.title")}</h3>
                  <p className="mb-2 text-small text-foreground-secondary">
                    {t("reconciliation.diffs.redInvoices")}{" "}
                    <NavLink className="font-semibold text-primary underline" to="/app/einvoices">{t("reconciliation.diffs.openEdocs")}</NavLink>
                  </p>
                  <div className="mb-2 flex gap-2" role="group" aria-label={t("reconciliation.diffs.filterLabel")}>
                    <Button size="sm" variant={diffFilter === "open" ? "default" : "secondary"} onClick={() => setDiffFilter("open")}>
                      {t("reconciliation.diffs.filterOpen")}
                    </Button>
                    <Button size="sm" variant={diffFilter === "all" ? "default" : "secondary"} onClick={() => setDiffFilter("all")}>
                      {t("reconciliation.diffs.filterAll")}
                    </Button>
                  </div>
                  <table className="w-full min-w-[560px] text-left text-small">
                    <thead><tr className="border-b border-border text-foreground-secondary">
                      {(["indicator", "state", "ours", "diff", "status"] as const).map((key) => <th key={key} className="px-2 py-2">{t(`reconciliation.diffs.${key}`)}</th>)}
                    </tr></thead>
                    <tbody>{visibleDiffs.map((diff) => <tr key={diff.id} className="border-b border-border">
                      <td className="px-2 py-2 font-semibold">{diff.indicator}</td><td className="px-2 py-2 tabular-nums">{amount(diff.state_value)}</td>
                      <td className="px-2 py-2 tabular-nums">{amount(diff.our_value)}</td><td className="px-2 py-2 tabular-nums">{amount(diff.diff)}</td>
                      <td className="px-2 py-2">{diff.resolved ? t("reconciliation.diffs.resolved") : t("reconciliation.diffs.open")}</td>
                    </tr>)}</tbody>
                  </table>
                </div>
              ) : null}
              {canSubmit && online && report.status === "diff_found" ? (
                <div className="grid gap-3 border-t border-border pt-4">
                  <h3 className="font-bold">{t("reconciliation.response.title")}</h3>
                  <FormField label={t("reconciliation.response.comment")}>
                    <Textarea value={comment} maxLength={1000} onChange={(e) => setComment(e.target.value)} />
                  </FormField>
                  <FormField label={t("reconciliation.response.portalRef")}>
                    <Input value={portalRef} maxLength={200} onChange={(e) => setPortalRef(e.target.value)} />
                  </FormField>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" disabled={busy || comment.trim().length === 0}
                      onClick={() => void mutate(() => recordCorrection(report.id, { comment: comment.trim(), ...(portalRef.trim() ? { portal_ref: portalRef.trim() } : {}) }))}>
                      {t("reconciliation.response.recordCorrection")}
                    </Button>
                    <a className="inline-flex items-center gap-1 rounded-md px-3 py-2 text-small font-semibold text-primary underline" href="https://my.soliq.uz" target="_blank" rel="noreferrer">
                      <Icon as={ArrowUpRight} size="sm" />{t("reconciliation.response.portal")}
                    </a>
                  </div>
                  <p className="text-xs text-foreground-secondary">{t("reconciliation.response.note")}</p>
                </div>
              ) : null}
            </>
          )}
        </Card>
      </div>
    </div>
  );
}

export const Reconciliation = {
  route: "tax/reconciliation",
  titleKey: "finance:reconciliation.title",
  Page: ReconciliationPage,
} as const;

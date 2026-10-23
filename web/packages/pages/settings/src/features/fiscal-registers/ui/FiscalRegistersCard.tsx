/**
 * BO-14 «Fiskal» → «Kassalar fiskal holati» (contracts/fiscal.md §4): fiscal module state per register, the
 * FM's own unsent count, receipts without the OFD ack (oldest age; 24 h warn, 48 h lock) and failed receipts;
 * «Qayta yuborish» queues the agent's `fiscal.resend_unsent` for a register bound to a Do'kon agenti.
 */
import { useUnit } from "effector-react";
import { RotateCcw, ServerCog, TriangleAlert } from "lucide-react";
import { useEffect } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDateTime } from "@shared/lib/date";
import {
  Banner,
  Button,
  Card,
  DataTable,
  EmptyState,
  Icon,
  StatusChip,
  type DataTableColumn,
  type Tone,
} from "@shared/ui";

import { $agents, agentName } from "#/entities/store-agent/index.ts";
import { errorText } from "#/shared/lib/errors.ts";

import {
  $fiscalRegisters,
  $fiscalRegistersError,
  $fiscalRegistersStatus,
  $resendError,
  $resendQueued,
  $resending,
  ageHours,
  canResend,
  fiscalRegistersOpened,
  fiscalRegistersReloadRequested,
  resendDismissed,
  resendRequested,
  severityOf,
  type FiscalRegister,
} from "../model/index.ts";

const FM_TONE: Record<string, Tone> = {
  ok: "success",
  locked: "destructive",
  ack_overdue: "destructive",
  memory_full: "destructive",
  unknown: "neutral",
};
const SEVERITY_TONE = { ok: "success", warn: "warning", blocked: "destructive" } as const;

export function FiscalRegistersCard({ canRetry, online }: { canRetry: boolean; online: boolean }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const [list, status, error, resending, queued, resendError, agents] = useUnit([
    $fiscalRegisters,
    $fiscalRegistersStatus,
    $fiscalRegistersError,
    $resending,
    $resendQueued,
    $resendError,
    $agents,
  ]);
  const [opened, reload, resend, dismiss] = useUnit([
    fiscalRegistersOpened,
    fiscalRegistersReloadRequested,
    resendRequested,
    resendDismissed,
  ]);

  useEffect(() => {
    opened();
  }, [opened]);

  const columns: DataTableColumn<FiscalRegister>[] = [
    {
      id: "name",
      header: t("fiscalRegisters.columns.register"),
      cell: (r) => (
        <div className="min-w-0">
          <p className="text-[14px] font-bold">{r.name}</p>
          <p className="text-[12px] text-muted-foreground">
            {r.fiscal_agent_id
              ? t("fiscalRegisters.viaAgent", {
                  agent: agentName(agents, r.fiscal_agent_id) ?? t("agents.unknownAgent"),
                  device: r.fiscal_local_device_id ?? "—",
                })
              : t("fiscalRegisters.cloud")}
          </p>
        </div>
      ),
    },
    {
      id: "fm",
      header: t("fiscalRegisters.columns.fm"),
      width: "150px",
      cell: (r) => (
        <StatusChip tone={FM_TONE[r.fm_state] ?? "neutral"} dot>
          {t(`fiscal.fmState.${r.fm_state}`)}
        </StatusChip>
      ),
    },
    {
      id: "fmPending",
      header: t("fiscalRegisters.columns.fmPending"),
      numeric: true,
      width: "110px",
      cell: (r) => (r.fm_receipts_pending === null ? "—" : r.fm_receipts_pending),
    },
    {
      id: "unacked",
      header: t("fiscalRegisters.columns.unacked"),
      width: "200px",
      cell: (r) => {
        const severity = severityOf(r);
        const hours = ageHours(r.oldest_unacked_age_s);
        return r.unacked_count === 0 ? (
          <StatusChip tone="success">{t("fiscalRegisters.allAcked")}</StatusChip>
        ) : (
          <span className="flex flex-col items-start gap-0.5">
            <StatusChip tone={SEVERITY_TONE[severity]}>
              {t("fiscalRegisters.unackedCount", { count: r.unacked_count })}
            </StatusChip>
            <span className="text-[11px] text-muted-foreground">
              {hours !== null ? t("fiscalRegisters.oldestHours", { hours }) : ""}
              {r.oldest_unacked_at ? ` · ${formatDateTime(r.oldest_unacked_at)}` : ""}
            </span>
          </span>
        );
      },
    },
    {
      id: "failed",
      header: t("fiscalRegisters.columns.failed"),
      numeric: true,
      width: "90px",
      cell: (r) =>
        r.failed_count > 0 ? (
          <span className="font-bold text-destructive-strong">{r.failed_count}</span>
        ) : (
          "0"
        ),
    },
    ...(canRetry
      ? [
          {
            id: "action",
            header: t("fiscalRegisters.columns.action"),
            hideHeader: true,
            width: "170px",
            cell: (r: FiscalRegister) =>
              !canResend(r) ? null : queued.includes(r.cash_register_id) ? (
                <StatusChip tone="info">{t("fiscalRegisters.queued")}</StatusChip>
              ) : (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!online || resending.includes(r.cash_register_id)}
                  aria-busy={resending.includes(r.cash_register_id) || undefined}
                  aria-label={t("fiscalRegisters.resendFor", { name: r.name })}
                  onClick={() => resend(r.cash_register_id)}
                >
                  <Icon as={RotateCcw} size="sm" />
                  {t("fiscalRegisters.resend")}
                </Button>
              ),
          } satisfies DataTableColumn<FiscalRegister>,
        ]
      : []),
  ];

  return (
    <Card role="region" aria-labelledby="fiscal-registers-title" className="flex flex-col gap-3">
      <div>
        <h3 id="fiscal-registers-title" className="text-[15px] font-bold">
          {t("fiscalRegisters.title")}
        </h3>
        <p className="text-small text-foreground-secondary">{t("fiscalRegisters.subtitle")}</p>
      </div>
      {resendError ? (
        <Banner
          tone="destructive"
          icon={TriangleAlert}
          live="assertive"
          action={
            <Button size="sm" variant="secondary" onClick={() => dismiss()}>
              {tc("actions.close")}
            </Button>
          }
        >
          {errorText(resendError)}
        </Banner>
      ) : null}
      <DataTable
        label={t("fiscalRegisters.title")}
        columns={columns}
        data={list}
        getRowId={(r) => r.cash_register_id}
        status={status}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={reload}
        minWidth={860}
        skeletonRows={2}
        empty={<EmptyState icon={ServerCog} title={t("fiscalRegisters.empty")} />}
      />
    </Card>
  );
}

/**
 * POS-12 — Offline / sinxronlash holati (07, route /pos/sync, F12; 06 §6 POS-12, mockup Pos12Offline.dc.html):
 * the 48 h counter (time since the oldest receipt without an OFD ack, time left, ladder 24 🟡 / 40 🔴 / 46 modal /
 * 48 ⛔ — qaror #43, 16 §6), the register's `fm_state`, the unsynced documents (outbox, seq order) with the
 * rejected ones and their translated error, «Qayta yuborish» per row, «QAYTA ULANISHGA URINISH» (push + pull now)
 * and the outbox export (JSON file). Open to every POS user — no permission check.
 */
import { useUnit } from "effector-react";
import { ArrowLeft, Download, Lock, RefreshCw, TriangleAlert, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import {
  $fiscalLadder,
  fiscal,
  OFFLINE_BLOCK_HOURS,
  outbox,
  outboxChanged,
  pullApplied,
  syncNow,
  type FiscalRegisterRow,
  type OutboxRow,
} from "@shared/offline";
import { $syncState } from "@shared/state/sync";
import { Banner, Button, cn, EmptyState, Icon, Kbd, StatusChip, type Tone } from "@shared/ui";

import { $posCashier, $posDevice, cashierCan } from "#/entities/pos-session/index.ts";
import { sumMoney } from "#/entities/receipt-draft/index.ts";
import { hoursMinutes, tashkentDateTime, tashkentTime } from "#/shared/lib/dates.ts";
import { dyn, messageText } from "#/shared/lib/i18n-errors.ts";
import { hasPosHistory, posBackTarget } from "#/shared/lib/pos-history.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";

const HOUR = 3_600_000;

const LEVEL_TONE: Record<string, Tone> = {
  ok: "success",
  warn24: "warning",
  red40: "destructive",
  modal46: "destructive",
  blocked48: "destructive",
};

function docLabel(row: OutboxRow, t: (k: string, o?: Record<string, unknown>) => string): string {
  const server = row.server ?? {};
  const number = typeof server.number === "string" ? server.number : null;
  const seq = row.receipt_seq;
  const base = t(`syncStatus.types.${row.type.replace(".", "_")}`);
  return number ? `${base} ${number}` : seq ? `${base} #${seq}` : base;
}

function amountOf(row: OutboxRow): string | null {
  const payments = row.payload.payments;
  if (!Array.isArray(payments) || payments.length === 0) return null;
  try {
    const amounts = payments.map((p) => {
      const value = (p as { amount?: unknown }).amount;
      return typeof value === "string" ? value : "0";
    });
    return formatMoney(sumMoney(amounts));
  } catch {
    return null;
  }
}

/**
 * SYNC-02: a non-retryable rejection is a document that needs a human — POS-12 shows it under «Eskalatsiya»
 * (export + manual retry); everything else waits in the normal queue.
 */
export function groupOutbox(rows: readonly OutboxRow[]): { escalated: OutboxRow[]; queue: OutboxRow[] } {
  // `escalated` is set by @shared/offline (SYNC-02); older rows: a non-retryable rejection
  const escalated = rows.filter(
    (r) => r.escalated === 1 || (r.status === "rejected" && r.retryable === false),
  );
  return { escalated, queue: rows.filter((r) => !escalated.includes(r)) };
}

export function exportFileName(deviceId: string, at: Date = new Date()): string {
  return `erp-outbox-${deviceId}-${at.toISOString().replace(/[:.]/g, "-")}.json`;
}

/** Downloads the outbox export (revoke / logout / support, 16 §9). */
export async function downloadOutboxExport(): Promise<void> {
  const data = await outbox.export();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = exportFileName(String(data.device_id ?? "device"));
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

function SyncStatusPage() {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const cashier = useUnit($posCashier);
  // UX-09: back to where the cashier came from (POS-02 / warehouse hub)
  const goBack = () => {
    if (hasPosHistory(pathname)) void navigate(-1);
    else void navigate(posBackTarget(pathname, cashierCan(cashier, "sales.create")));
  };
  const [sync, ladder, device] = useUnit([$syncState, $fiscalLadder, $posDevice]);
  const [rows, setRows] = useState<OutboxRow[]>([]);
  const [register, setRegister] = useState<FiscalRegisterRow | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(0);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const a = outboxChanged.watch(() => setTick((n) => n + 1));
    const b = pullApplied.watch(() => setTick((n) => n + 1));
    const timer = setInterval(() => {
      setTick((n) => n + 1);
      setNow(Date.now());
    }, 30_000);
    return () => {
      a();
      b();
      clearInterval(timer);
    };
  }, []);
  useEffect(() => {
    void outbox.list({ status: ["pending", "rejected"], limit: 500 }).then(setRows);
    if (device?.cashRegisterId) void fiscal.register(device.cashRegisterId).then(setRegister);
  }, [tick, sync.pending, sync.rejected, device?.cashRegisterId]);

  const retryNow = async () => {
    setBusy(true);
    try {
      await outbox.retryAllRetryable();
      await syncNow({ push: true, pull: true });
    } catch {
      /* the engine keeps retrying with backoff */
    } finally {
      setBusy(false);
      setTick((n) => n + 1);
    }
  };

  useHotkeys([
    { key: "Escape", allowInInput: true, handler: () => goBack() },
    { key: "Enter", handler: () => void retryNow() },
  ]);

  const elapsedMs = ladder.oldestUnackedAt ? Math.max(0, now - Date.parse(ladder.oldestUnackedAt)) : 0;
  const leftMs = Math.max(0, OFFLINE_BLOCK_HOURS * HOUR - elapsedMs);
  const elapsed = hoursMinutes(elapsedMs);
  const left = hoursMinutes(leftMs);
  const pct = Math.min(100, Math.round((elapsedMs / (OFFLINE_BLOCK_HOURS * HOUR)) * 100));
  const blocked = ladder.level === "blocked48";
  const rejected = rows.filter((r) => r.status === "rejected");
  const groups = groupOutbox(rows);
  const renderRow = (r: OutboxRow) => (
    <li
      key={r.client_event_id}
      data-testid="outbox-row"
      className={cn(
        "flex items-center gap-3 rounded-xl border px-3 py-2",
        r.status === "rejected" ? "border-destructive-border bg-destructive-soft/40" : "border-border",
      )}
    >
      <span className="w-16 text-[13px] text-muted-foreground">{tashkentTime(r.created_at)}</span>
      <span className="min-w-0 flex-1">
        <span className="block font-bold">{docLabel(r, t)}</span>
        {r.status === "rejected" ? (
          <span className="block text-[13px] text-destructive" data-testid="outbox-error">
            {messageText(r.message, r.error_code)}
          </span>
        ) : null}
      </span>
      {amountOf(r) ? <span className="font-bold">{amountOf(r)}</span> : null}
      <StatusChip tone={r.status === "rejected" ? "destructive" : "warning"}>
        {t(`syncStatus.status.${r.status}`)}
      </StatusChip>
      {r.status === "rejected" ? (
        <Button
          size="sm"
          variant="secondary"
          onClick={() => void outbox.retry(r.client_event_id).then(() => syncNow({ push: true }))}
        >
          {t("syncStatus.retryOne")}
        </Button>
      ) : null}
    </li>
  );

  return (
    <div className="flex h-full min-h-0 flex-col gap-3" data-testid="sync-status">
      <div className="flex items-center gap-3">
        <Button size="pos" variant="secondary" onClick={() => goBack()}>
          <Icon as={ArrowLeft} size="lg" />
          {t("syncStatus.back")}
          <Kbd keys="Esc" />
        </Button>
        <h1 className="text-[22px] font-extrabold">
          {blocked ? t("syncStatus.blockedTitle") : t("syncStatus.title")}
        </h1>
        <div className="grow" />
        <StatusChip
          tone={sync.online ? "success" : "warning"}
          icon={sync.online ? undefined : WifiOff}
          dot={sync.online}
        >
          {sync.online ? t("syncStatus.online") : t("syncStatus.offline")}
        </StatusChip>
      </div>

      {blocked ? (
        <Banner tone="destructive" icon={Lock} live="assertive">
          {t("fiscalLadder.blockedBanner")}
        </Banner>
      ) : null}
      {sync.lastErrorCode && sync.online ? (
        <Banner tone="warning" icon={TriangleAlert}>
          {t("syncStatus.connectError")}
        </Banner>
      ) : null}

      <section className="grid grid-cols-[1fr_auto] gap-4 rounded-2xl border border-border bg-card p-5 shadow-raised">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <StatusChip tone={LEVEL_TONE[ladder.level] ?? "neutral"} dot>
              <span data-testid="ladder-level">{t(`fiscalLadder.level.${ladder.level}`)}</span>
            </StatusChip>
            {ladder.oldestUnackedAt ? (
              <span className="text-[14px]" data-testid="ladder-elapsed">
                {t("syncStatus.elapsed", { h: elapsed.h, m: elapsed.m })}
              </span>
            ) : (
              <span className="text-[14px] text-muted-foreground">{t("syncStatus.allAcked")}</span>
            )}
          </div>
          {ladder.oldestUnackedAt ? (
            <>
              <div className="text-[18px] font-extrabold">
                {t("syncStatus.left", { h: left.h, m: left.m })}
              </div>
              <div
                className="h-3 overflow-hidden rounded-full bg-muted"
                role="progressbar"
                aria-valuenow={pct}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className={cn(
                    "h-full",
                    ladder.level === "ok" && "w-0",
                    pct > 0 && "bg-warning-strong",
                    (ladder.level === "red40" || ladder.level === "modal46" || blocked) && "bg-destructive",
                    pct < 25
                      ? "w-1/4"
                      : pct < 50
                        ? "w-1/2"
                        : pct < 84
                          ? "w-3/4"
                          : pct < 100
                            ? "w-11/12"
                            : "w-full",
                  )}
                />
              </div>
            </>
          ) : null}
          <p className="text-[13px] text-muted-foreground">{t("syncStatus.ladderHint")}</p>
        </div>
        <dl className="grid grid-cols-[auto_auto] content-start gap-x-4 gap-y-1 text-[13px]">
          <dt className="text-muted-foreground">{t("syncStatus.pending")}</dt>
          <dd className="font-bold" data-testid="sync-pending">
            {sync.pending}
          </dd>
          <dt className="text-muted-foreground">{t("syncStatus.rejected")}</dt>
          <dd className="font-bold" data-testid="sync-rejected">
            {sync.rejected}
          </dd>
          <dt className="text-muted-foreground">{t("syncStatus.lastPush")}</dt>
          <dd>{sync.lastPushAt ? tashkentDateTime(sync.lastPushAt) : "—"}</dd>
          <dt className="text-muted-foreground">{t("syncStatus.lastPull")}</dt>
          <dd>{sync.lastPullAt ? tashkentDateTime(sync.lastPullAt) : "—"}</dd>
          <dt className="text-muted-foreground">{t("syncStatus.fmState")}</dt>
          <dd data-testid="fm-state">{t(`syncStatus.fm.${register?.fm_state ?? "unknown"}`)}</dd>
        </dl>
      </section>

      <section className="flex min-h-0 flex-1 flex-col gap-2 rounded-2xl border border-border bg-card p-5 shadow-raised">
        <div className="flex items-center gap-2">
          <h2 className="text-[16px] font-extrabold">{t("syncStatus.listTitle", { n: rows.length })}</h2>
          <div className="grow" />
          <Button
            size="default"
            variant="secondary"
            onClick={() => void downloadOutboxExport()}
            data-testid="outbox-export"
          >
            <Icon as={Download} size="md" />
            {t("syncStatus.export")}
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {rows.length === 0 ? (
            <EmptyState icon={RefreshCw} title={t("syncStatus.empty")} />
          ) : (
            <>
              {groups.escalated.length > 0 ? (
                <section
                  aria-label={t("syncStatus.escalatedTitle")}
                  data-testid="outbox-escalated"
                  className="mb-3"
                >
                  <h3 className="text-[14px] font-extrabold text-destructive">
                    {t("syncStatus.escalatedTitle", { n: groups.escalated.length })}
                  </h3>
                  <p className="mb-1 text-[13px] text-foreground-secondary">
                    {t("syncStatus.escalatedHint")}
                  </p>
                  <ul className="flex flex-col gap-1">{groups.escalated.map(renderRow)}</ul>
                </section>
              ) : null}
              <ul className="flex flex-col gap-1" data-testid="outbox-list">
                {groups.queue.map(renderRow)}
              </ul>
            </>
          )}
        </div>
        {rejected.length > 0 ? (
          <p className="text-[13px] text-muted-foreground">{t("syncStatus.rejectedHint")}</p>
        ) : null}
        <Button
          size="pos-cta"
          className="w-full"
          disabled={busy}
          onClick={() => void retryNow()}
          data-testid="sync-retry"
        >
          <Icon as={RefreshCw} size="xl" />
          {t("syncStatus.retry")}
        </Button>
      </section>
    </div>
  );
}

export const SyncStatus = { route: "sync", titleKey: "pos:syncStatus.title", Page: SyncStatusPage } as const;

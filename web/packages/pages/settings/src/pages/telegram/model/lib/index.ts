import {
  ALERT_GROUPS,
  DAILY_REPORT,
  DAILY_TIMES,
  DEFAULT_DAILY_TIME,
  type AlertGroup,
  type LinkStart,
  type LogItem,
  type LogSummary,
  type SettingItem,
} from "../types/index.ts";

/** The link stopped working (now ≥ `expires_at`). */
export function isExpired(link: Pick<LinkStart, "expires_at"> | null, nowIso: string): boolean {
  if (!link) return false;
  return new Date(nowIso).getTime() >= new Date(link.expires_at).getTime();
}

export function setKind(items: readonly SettingItem[], kind: string, enabled: boolean): SettingItem[] {
  return items.map((i) => (i.kind === kind ? { ...i, enabled } : i));
}

export function setDailyTime(items: readonly SettingItem[], time: string): SettingItem[] {
  return items.map((i) => (i.kind === DAILY_REPORT ? { ...i, time } : i));
}

export function sameSettings(a: readonly SettingItem[], b: readonly SettingItem[]): boolean {
  return (
    a.length === b.length &&
    a.every((x, i) => x.kind === b[i]?.kind && x.enabled === b[i]?.enabled && x.time === b[i]?.time)
  );
}

/** PATCH body items (20 #70): every kind; `time` only for `daily_report`. */
export function toPatchItems(items: readonly SettingItem[]): SettingItem[] {
  return items.map((i) =>
    i.kind === DAILY_REPORT
      ? { kind: i.kind, enabled: i.enabled, time: i.time ?? DEFAULT_DAILY_TIME }
      : { kind: i.kind, enabled: i.enabled, time: null },
  );
}

/** The alert toggles grouped as in the mockup; kinds the UI does not know go to «Boshqa». */
export function groupAlerts(items: readonly SettingItem[]): { group: AlertGroup; items: SettingItem[] }[] {
  const alerts = items.filter((i) => i.kind !== DAILY_REPORT);
  const known = new Set(ALERT_GROUPS.flatMap((g) => g.kinds));
  const groups = ALERT_GROUPS.map((g) => ({
    group: g.group,
    items: g.kinds.flatMap((k) => alerts.filter((i) => i.kind === k)),
  }));
  groups.push({ group: "other", items: alerts.filter((i) => !known.has(i.kind)) });
  return groups.filter((g) => g.items.length > 0);
}

/** «N / M yoqilgan» of the alert toggles. */
export function enabledCount(items: readonly SettingItem[]): { on: number; all: number } {
  const alerts = items.filter((i) => i.kind !== DAILY_REPORT);
  return { on: alerts.filter((i) => i.enabled).length, all: alerts.length };
}

/** Time options: the 07 choices plus a stored time that is not among them. */
export function timeOptions(current: string | null): string[] {
  return current && !DAILY_TIMES.includes(current) ? [...DAILY_TIMES, current].sort() : [...DAILY_TIMES];
}

/** «Oxirgi xabar» and «Bu oy yuborildi N ta» from the loaded log rows (newest first). */
export function logSummary(rows: readonly LogItem[], hasMore: boolean, nowIso: string): LogSummary {
  const month = nowIso.slice(0, 7);
  const inMonth = rows.filter((r) => r.created_at.slice(0, 7) === month);
  const oldest = rows.at(-1);
  return {
    last: rows[0] ?? null,
    sentThisMonth: inMonth.filter((r) => r.status === "sent").length,
    more: hasMore && oldest !== undefined && oldest.created_at.slice(0, 7) === month,
  };
}

/** `"HH:mm"` of an ISO timestamp in local time. */
export function hhmm(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

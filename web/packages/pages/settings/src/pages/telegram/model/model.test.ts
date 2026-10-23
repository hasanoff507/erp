import { allSettled, fork, scopeBind } from "effector";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  $alertGroups,
  $dirty,
  $draft,
  $enabled,
  $link,
  $linkExpired,
  $log,
  $logSummary,
  $savedAt,
  $status,
  DAILY_REPORT,
  dailyTimeChanged,
  draftReset,
  groupAlerts,
  isExpired,
  kindToggled,
  linkStartRequested,
  loadLogFx,
  loadSettingsFx,
  loadStatusFx,
  logSummary,
  nowFx,
  pageMounted,
  pageUnmounted,
  saveRequested,
  saveSettingsFx,
  startLinkFx,
  timeOptions,
  toPatchItems,
  unlinkFx,
  unlinkRequested,
  type LogItem,
  type SettingItem,
  type TelegramStatus,
} from "./index.ts";

const NOW = "2026-10-17T09:48:00.000Z";
const SETTINGS: SettingItem[] = [
  { kind: "daily_report", enabled: true, time: "21:00" },
  { kind: "low_stock", enabled: true, time: null },
  { kind: "expiry_soon", enabled: true, time: null },
  { kind: "cash_variance", enabled: true, time: null },
  { kind: "future_kind", enabled: false, time: null },
];

function log(id: string, at: string, status = "sent"): LogItem {
  return {
    id,
    channel: "telegram",
    recipient: "123456",
    template: "low_stock",
    status,
    cost: null,
    created_at: at,
  };
}

function scope(statuses: TelegramStatus[]) {
  const saved: SettingItem[][] = [];
  let statusCalls = 0;
  let unlinked = 0;
  const s = fork({
    handlers: [
      [nowFx, () => NOW],
      [
        loadStatusFx,
        () => {
          const status = statuses[Math.min(statusCalls, statuses.length - 1)];
          statusCalls += 1;
          return status;
        },
      ],
      [
        startLinkFx,
        () => ({
          link_code: "lnk_7Q4M2XKDabcdefghijkl",
          bot_url: "https://t.me/erp_bot?start=lnk_7Q4M2XKDabcdefghijkl",
          expires_at: "2026-10-17T09:58:00.000Z",
        }),
      ],
      [
        unlinkFx,
        () => {
          unlinked += 1;
        },
      ],
      [loadSettingsFx, () => SETTINGS],
      [
        saveSettingsFx,
        (items: SettingItem[]) => {
          saved.push(items);
          return items;
        },
      ],
      [
        loadLogFx,
        () => ({
          items: [log("l-2", "2026-10-16T09:05:00Z"), log("l-1", "2026-09-30T21:00:00Z", "failed")],
          next_cursor: null,
        }),
      ],
    ],
  });
  return { s, saved, calls: () => statusCalls, unlinked: () => unlinked };
}

const NOT_LINKED: TelegramStatus = { linked: false, chat_id: null, linked_at: null };
const LINKED: TelegramStatus = { linked: true, chat_id: "123456", linked_at: "2026-10-17T09:49:00Z" };

describe("BO-20 Telegram link (US-M18-01, QT-M18-01)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("link-start shows the one-time link and polls the status until the bot binds it", async () => {
    const { s, calls } = scope([NOT_LINKED, NOT_LINKED, LINKED]);
    await allSettled(pageMounted, { scope: s, params: { canLink: true, canManage: false } });
    expect(s.getState($status)?.linked).toBe(false);
    // The poll is a running timer — allSettled would wait for it; drive it with fake timers.
    scopeBind(linkStartRequested, { scope: s })();
    await vi.advanceTimersByTimeAsync(0);
    expect(s.getState($link)?.bot_url).toBe("https://t.me/erp_bot?start=lnk_7Q4M2XKDabcdefghijkl");
    expect(s.getState($linkExpired)).toBe(false);

    await vi.advanceTimersByTimeAsync(3_000);
    expect(s.getState($status)?.linked).toBe(false);
    expect(s.getState($link)).not.toBeNull();

    await vi.advanceTimersByTimeAsync(3_000);
    expect(s.getState($status)?.linked).toBe(true);
    expect(s.getState($link)).toBeNull();
    const after = calls();
    await vi.advanceTimersByTimeAsync(9_000);
    expect(calls()).toBe(after); // polling stopped
    scopeBind(pageUnmounted, { scope: s })();
  });

  it("unlink → DELETE and the status is read again", async () => {
    const { s, unlinked } = scope([LINKED, NOT_LINKED]);
    await allSettled(pageMounted, { scope: s, params: { canLink: true, canManage: false } });
    await allSettled(unlinkRequested, { scope: s });
    expect(unlinked()).toBe(1);
    expect(s.getState($status)?.linked).toBe(false);
  });
});

describe("BO-20 settings (US-M18-03, QT-M18-06)", () => {
  it("toggles are a draft; «Saqlash» sends every kind, time only for daily_report", async () => {
    const { s, saved } = scope([NOT_LINKED]);
    await allSettled(pageMounted, { scope: s, params: { canLink: false, canManage: true } });
    expect(s.getState($enabled)).toEqual({ on: 3, all: 4 });
    expect(s.getState($dirty)).toBe(false);

    await allSettled(kindToggled, { scope: s, params: { kind: "low_stock", enabled: false } });
    await allSettled(dailyTimeChanged, { scope: s, params: "22:00" });
    expect(s.getState($dirty)).toBe(true);
    await allSettled(saveRequested, { scope: s });
    expect(saved).toEqual([
      [
        { kind: "daily_report", enabled: true, time: "22:00" },
        { kind: "low_stock", enabled: false, time: null },
        { kind: "expiry_soon", enabled: true, time: null },
        { kind: "cash_variance", enabled: true, time: null },
        { kind: "future_kind", enabled: false, time: null },
      ],
    ]);
    expect(s.getState($dirty)).toBe(false);
    expect(s.getState($savedAt)).not.toBeNull();

    // «Bekor qilish» goes back to the saved values; nothing to save → no request.
    await allSettled(kindToggled, { scope: s, params: { kind: "cash_variance", enabled: false } });
    await allSettled(draftReset, { scope: s });
    expect(s.getState($draft).find((i) => i.kind === "cash_variance")?.enabled).toBe(true);
    await allSettled(saveRequested, { scope: s });
    expect(saved).toHaveLength(1);
  });

  it("groups as in the mockup, unknown kinds under «Boshqa»; log summary", async () => {
    const { s } = scope([NOT_LINKED]);
    await allSettled(pageMounted, { scope: s, params: { canLink: true, canManage: true } });
    expect(s.getState($alertGroups).map((g) => [g.group, g.items.map((i) => i.kind)])).toEqual([
      ["sales", ["cash_variance"]],
      ["stock", ["low_stock", "expiry_soon"]],
      ["other", ["future_kind"]],
    ]);
    expect(s.getState($log)).toHaveLength(2);
    expect(s.getState($logSummary)).toEqual({
      last: log("l-2", "2026-10-16T09:05:00Z"),
      sentThisMonth: 1,
      more: false,
    });
  });
});

describe("BO-20 lib", () => {
  it("expiry, patch items, time options, log summary", () => {
    expect(isExpired({ expires_at: "2026-10-17T09:58:00Z" }, "2026-10-17T09:57:59Z")).toBe(false);
    expect(isExpired({ expires_at: "2026-10-17T09:58:00Z" }, "2026-10-17T09:58:00Z")).toBe(true);
    expect(isExpired(null, NOW)).toBe(false);
    expect(toPatchItems([{ kind: DAILY_REPORT, enabled: false, time: null }])).toEqual([
      { kind: DAILY_REPORT, enabled: false, time: "21:00" },
    ]);
    expect(timeOptions("21:00")).toEqual(["20:00", "21:00", "22:00", "23:00"]);
    expect(timeOptions("19:30")).toEqual(["19:30", "20:00", "21:00", "22:00", "23:00"]);
    expect(groupAlerts([{ kind: DAILY_REPORT, enabled: true, time: "21:00" }])).toEqual([]);
    expect(
      logSummary([log("a", "2026-10-02T00:00:00Z"), log("b", "2026-10-01T00:00:00Z")], true, NOW),
    ).toMatchObject({ sentThisMonth: 2, more: true });
  });
});

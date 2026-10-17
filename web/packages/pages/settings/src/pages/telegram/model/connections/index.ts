/** BO-20 wiring — sample() only (24 §2). */
import { combine, merge, sample } from "effector";
import { interval } from "patronum";

import {
  loadLogFx,
  loadSettingsFx,
  loadStatusFx,
  nowFx,
  saveSettingsFx,
  startLinkFx,
  unlinkFx,
} from "../effects/index.ts";
import {
  dailyTimeChanged,
  draftReset,
  kindToggled,
  linkStartRequested,
  logMoreRequested,
  logReloadRequested,
  pageMounted,
  pageUnmounted,
  saveRequested,
  settingsReloadRequested,
  statusReloadRequested,
  unlinkRequested,
} from "../events/index.ts";
import {
  enabledCount,
  groupAlerts,
  isExpired,
  logSummary,
  sameSettings,
  setDailyTime,
  setKind,
  toPatchItems,
} from "../lib/index.ts";
import {
  $draft,
  $link,
  $linkError,
  $linkedAtBefore,
  $log,
  $logCursor,
  $logError,
  $logStatus,
  $mounted,
  $now,
  $rights,
  $saveError,
  $saved,
  $savedAt,
  $settingsError,
  $settingsStatus,
  $status,
  $statusError,
} from "../stores/index.ts";
import { STATUS_POLL_MS } from "../types/index.ts";

export const $linkExpired = combine($link, $now, isExpired);
export const $dirty = combine($saved, $draft, (a, b) => !sameSettings(a, b));
export const $alertGroups = $draft.map(groupAlerts);
export const $enabled = $draft.map(enabledCount);
export const $logSummary = combine($log, $logCursor, $now, (rows, cursor, now) =>
  logSummary(rows, cursor !== null, now),
);
export const $saving = saveSettingsFx.pending;
export const $linking = startLinkFx.pending;
export const $unlinking = unlinkFx.pending;

// --- mount -------------------------------------------------------------------------------------------
$mounted.on(pageMounted, () => true).on(pageUnmounted, () => false);
$rights.on(pageMounted, (_, rights) => rights);
sample({ clock: pageMounted, target: nowFx });
sample({
  clock: [sample({ clock: pageMounted, filter: (r) => r.canLink }), statusReloadRequested],
  fn: () => undefined,
  target: loadStatusFx,
});
sample({
  clock: [sample({ clock: pageMounted, filter: (r) => r.canManage }), settingsReloadRequested],
  fn: () => undefined,
  target: loadSettingsFx,
});
sample({
  clock: [sample({ clock: pageMounted, filter: (r) => r.canManage }), logReloadRequested],
  fn: () => null,
  target: loadLogFx,
});
$now.on(nowFx.doneData, (_, now) => now);

// --- «Telegram akkaunt»: link → poll status until linked / expired (QT-M18-01) -----------------------
$status.on(loadStatusFx.doneData, (_, s) => s);
$statusError.on(loadStatusFx.failData, (_, e) => e).reset(loadStatusFx.done);

sample({
  clock: linkStartRequested,
  source: startLinkFx.pending,
  filter: (pending) => !pending,
  fn: () => undefined,
  target: startLinkFx,
});
$linkedAtBefore.on(
  sample({ clock: startLinkFx, source: $status, fn: (s) => s?.linked_at ?? null }),
  (_, at) => at,
);
$link.on(startLinkFx.doneData, (_, link) => link);
$linkError.on(startLinkFx.failData, (_, e) => e).reset(startLinkFx);
sample({ clock: startLinkFx.done, target: nowFx });

/** The bot bound the code (linked, and `linked_at` differs from the one before the link). */
const linked = sample({
  clock: loadStatusFx.doneData,
  source: { link: $link, before: $linkedAtBefore },
  filter: ({ link, before }, status) => link !== null && status.linked && status.linked_at !== before,
});
$link.reset(linked, unlinkFx.done, pageUnmounted);

const expired = sample({ clock: $linkExpired.updates, filter: (e) => e });
const poll = interval({
  timeout: STATUS_POLL_MS,
  start: startLinkFx.done,
  stop: merge([linked, expired, pageUnmounted, unlinkFx.done]),
});
sample({ clock: poll.tick, target: nowFx });
sample({
  clock: poll.tick,
  source: { link: $link, expired: $linkExpired, pending: loadStatusFx.pending },
  filter: ({ link, expired: e, pending }) => link !== null && !e && !pending,
  fn: () => undefined,
  target: loadStatusFx,
});

sample({ clock: unlinkRequested, fn: () => undefined, target: unlinkFx });
sample({ clock: unlinkFx.done, fn: () => undefined, target: loadStatusFx });

// --- settings draft / save (QT-M18-06, US-M18-03) ------------------------------------------------------
$saved.on(loadSettingsFx.doneData, (_, items) => items).on(saveSettingsFx.doneData, (_, items) => items);
$draft
  .on(loadSettingsFx.doneData, (_, items) => items)
  .on(saveSettingsFx.doneData, (_, items) => items)
  .on(kindToggled, (items, { kind, enabled }) => setKind(items, kind, enabled))
  .on(dailyTimeChanged, (items, time) => setDailyTime(items, time));
sample({ clock: draftReset, source: $saved, target: $draft });
$settingsStatus
  .on(loadSettingsFx, () => "loading")
  .on(loadSettingsFx.done, () => "idle")
  .on(loadSettingsFx.fail, () => "error");
$settingsError.on(loadSettingsFx.failData, (_, e) => e).reset(loadSettingsFx);

sample({
  clock: saveRequested,
  source: { draft: $draft, dirty: $dirty, pending: saveSettingsFx.pending },
  filter: ({ dirty, pending }) => dirty && !pending,
  fn: ({ draft }) => toPatchItems(draft),
  target: saveSettingsFx,
});
$saveError.on(saveSettingsFx.failData, (_, e) => e).reset(saveSettingsFx, draftReset);
$savedAt
  .on(saveSettingsFx.done, () => new Date().toISOString())
  .reset(saveSettingsFx, kindToggled, dailyTimeChanged);

// --- log -------------------------------------------------------------------------------------------------
sample({
  clock: logMoreRequested,
  source: { cursor: $logCursor, pending: loadLogFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ cursor }) => cursor,
  target: loadLogFx,
});
$log.on(loadLogFx.done, (rows, { params, result }) => (params ? [...rows, ...result.items] : result.items));
$logCursor.on(loadLogFx.doneData, (_, page) => page.next_cursor);
$logStatus
  .on(loadLogFx, (s, cursor) => (cursor === null ? "loading" : s))
  .on(loadLogFx.done, () => "idle")
  .on(loadLogFx.fail, (s, { params }) => (params === null ? "error" : s));
$logError.on(loadLogFx.failData, (_, e) => e).reset(loadLogFx);

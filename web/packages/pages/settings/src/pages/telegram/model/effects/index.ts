/**
 * BO-20 effects — generated clients only (20 #66–#71): `api.notifications.startTelegramLink`,
 * `getTelegramStatus`, `deleteTelegramLink`, `getSettings`, `updateSettings`, `listLog`.
 */
import { createEffect } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";

import {
  LOG_PAGE,
  type LinkStart,
  type LogItem,
  type SettingItem,
  type TelegramStatus,
} from "../types/index.ts";

function wrap<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw toApiError(e);
    }
  });
}

export const loadStatusFx = wrap<void, TelegramStatus>(() => api.notifications.getTelegramStatus());

export const startLinkFx = wrap<void, LinkStart>(() => api.notifications.startTelegramLink());

/** `DELETE` (204); no active link (404) is the same outcome — not linked. */
export const unlinkFx = wrap<void, void>(async () => {
  try {
    await api.notifications.deleteTelegramLink();
  } catch (e) {
    if (toApiError(e).status !== 404) throw e;
  }
});

export const loadSettingsFx = wrap<void, SettingItem[]>(
  async () => (await api.notifications.getSettings()).items,
);

export const saveSettingsFx = wrap<SettingItem[], SettingItem[]>(
  async (items) => (await api.notifications.updateSettings({ items })).items,
);

export const loadLogFx = wrap<string | null, { items: LogItem[]; next_cursor: string | null }>((cursor) =>
  api.notifications.listLog({ channel: "telegram", limit: LOG_PAGE, ...(cursor ? { cursor } : {}) }),
);

/** The clock for the link expiry (07 «Havola 10 daqiqa amal qiladi · HH:mm gacha»). */
export const nowFx = createEffect<void, string>(() => new Date().toISOString());

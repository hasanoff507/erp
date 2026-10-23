import { createStore } from "effector";

import type { ApiError } from "@shared/api";

import type {
  LinkStart,
  LoadStatus,
  LogItem,
  SettingItem,
  TelegramRights,
  TelegramStatus,
} from "../types/index.ts";

export const $mounted = createStore(false);
export const $rights = createStore<TelegramRights>({ canLink: false, canManage: false });

// --- «Telegram akkaunt» --------------------------------------------------------------------------------
export const $status = createStore<TelegramStatus | null>(null, { skipVoid: false });
export const $statusError = createStore<ApiError | null>(null, { skipVoid: false });
/** The active one-time link (`null` — none shown). */
export const $link = createStore<LinkStart | null>(null, { skipVoid: false });
/** `linked_at` when the link was started — a new value means the bot bound this link. */
export const $linkedAtBefore = createStore<string | null>(null, { skipVoid: false });
export const $linkError = createStore<ApiError | null>(null, { skipVoid: false });
export const $now = createStore<string>(new Date(0).toISOString());

// --- «Ogohlantirishlar» / «Kunlik hisobot» -----------------------------------------------------------------
export const $saved = createStore<SettingItem[]>([]);
export const $draft = createStore<SettingItem[]>([]);
export const $settingsStatus = createStore<LoadStatus>("idle");
export const $settingsError = createStore<ApiError | null>(null, { skipVoid: false });
export const $saveError = createStore<ApiError | null>(null, { skipVoid: false });

// --- notifications log ----------------------------------------------------------------------------------
export const $log = createStore<LogItem[]>([]);
export const $logCursor = createStore<string | null>(null, { skipVoid: false });
export const $logStatus = createStore<LoadStatus>("idle");
export const $logError = createStore<ApiError | null>(null, { skipVoid: false });

/** The last successful «Saqlash» (07: inline «Saqlandi»). */
export const $savedAt = createStore<string | null>(null, { skipVoid: false });

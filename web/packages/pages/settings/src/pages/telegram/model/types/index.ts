import type { LinkStartOut, LogItemOut, SettingItemOut, TelegramStatusOut } from "@shared/models";

export type TelegramStatus = TelegramStatusOut;
export type LinkStart = LinkStartOut;
export type SettingItem = SettingItemOut;
export type LogItem = LogItemOut;

export type LoadStatus = "idle" | "loading" | "error";

/** BO-20 rights: `telegram.link` — the account card; `notifications.manage` — toggles, time, log. */
export interface TelegramRights {
  canLink: boolean;
  canManage: boolean;
}

/** 20 #69 kinds; `daily_report` is the «Kunlik hisobot» block, the rest are alert toggles. */
export const DAILY_REPORT = "daily_report";

/** 07 BO-20 / mockup Bo20Telegram: alert toggles grouped. Unknown kinds go to «Boshqa». */
export type AlertGroup = "sales" | "stock" | "debts" | "system" | "other";
export const ALERT_GROUPS: readonly { group: AlertGroup; kinds: readonly string[] }[] = [
  {
    group: "sales",
    kinds: ["cash_variance", "over_limit_action", "offline_48h", "card_settlement_mismatch"],
  },
  { group: "stock", kinds: ["low_stock", "expiry_soon"] },
  { group: "debts", kinds: ["debt_due_today", "debt_aging_60", "debt_limit_exceeded_offline"] },
  {
    group: "system",
    kinds: ["state_report_diff", "subscription_due", "subscription_grace", "recurring_expense_due"],
  },
];

/** 07 BO-20 «Kunlik hisobot vaqti» choices (Toshkent vaqti); a stored other time is kept as an option. */
export const DAILY_TIMES: readonly string[] = ["20:00", "21:00", "22:00", "23:00"];
export const DEFAULT_DAILY_TIME = "21:00";

/** Status polling while a link code waits for «Start» in the bot (20 #67). */
export const STATUS_POLL_MS = 3_000;
export const LOG_PAGE = 50;

export type TelegramMountParams = TelegramRights;

export interface LogSummary {
  last: LogItem | null;
  /** Sent this calendar month among the loaded rows. */
  sentThisMonth: number;
  /** More rows of this month may be unloaded («N+»). */
  more: boolean;
}

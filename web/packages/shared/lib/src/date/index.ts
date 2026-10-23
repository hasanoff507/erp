/**
 * Dates — 08-dizayn-tizimi.md §0 band 2, §8; 32-kod-qoidalari.md §3.5.
 * `DD.MM.YYYY`, `HH:mm` (24h). Backend sends UTC (`...Z`); conversion to the browser zone
 * (Asia/Tashkent on shop devices) is done by dayjs — no hand-written offsets.
 */
import dayjs from "dayjs";
import "dayjs/locale/ru";
import "dayjs/locale/uz-latn";

export type UiLanguage = "uz" | "ru";

const DAYJS_LOCALE: Record<UiLanguage, string> = { uz: "uz-latn", ru: "ru" };

export function setDateLocale(lang: UiLanguage): void {
  dayjs.locale(DAYJS_LOCALE[lang]);
}

type DateInput = string | Date | dayjs.Dayjs;

export function formatDate(value: DateInput): string {
  return dayjs(value).format("DD.MM.YYYY");
}

export function formatDateTime(value: DateInput): string {
  return dayjs(value).format("DD.MM.YYYY HH:mm");
}

/** "Juma, 16.10.2026" — dashboard greeting line (BO-02). */
export function formatWeekdayDate(value: DateInput, lang: UiLanguage): string {
  const d = dayjs(value).locale(DAYJS_LOCALE[lang]);
  const weekday = d.format("dddd");
  return `${weekday.charAt(0).toUpperCase()}${weekday.slice(1)}, ${d.format("DD.MM.YYYY")}`;
}

export { dayjs };

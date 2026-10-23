/** Asia/Tashkent business day (18 §4.1 `doc_date`) and short local times for the POS screens. */
const TZ = "Asia/Tashkent";

/** "2026-10-17" — Tashkent calendar day of the instant. */
export function tashkentDate(at: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(at);
}

/** "22:41" in Tashkent time. */
export function tashkentTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "";
  return new Intl.DateTimeFormat("ru-RU", { timeZone: TZ, hour: "2-digit", minute: "2-digit" }).format(at);
}

/** "17.10.2026 22:41" in Tashkent time. */
export function tashkentDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: TZ,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
    .format(at)
    .replace(",", "");
}

/** Whole hours and minutes of a duration in ms (48 h ladder, POS-12). */
export function hoursMinutes(ms: number): { h: number; m: number } {
  const total = Math.max(0, Math.floor(ms / 60_000));
  return { h: Math.floor(total / 60), m: total % 60 };
}

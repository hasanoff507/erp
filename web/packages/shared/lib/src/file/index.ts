/**
 * File helpers for uploads (17 §12: Excel/CSV ≤ 10 MB, image ≤ 10 MB, PDF ≤ 20 MB).
 * Sizes are byte counts (not money) — plain integer arithmetic is fine here.
 */

export const MB = 1024 * 1024;

/** 17 §12 limits in bytes. */
export const UPLOAD_LIMITS = {
  spreadsheet: 10 * MB,
  image: 10 * MB,
  pdf: 20 * MB,
} as const;

/** MIME types / extensions accepted by import endpoints (17 §12). */
export const SPREADSHEET_ACCEPT = {
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".csv": "text/csv",
} as const;

export interface FileSizeUnits {
  b: string;
  kb: string;
  mb: string;
}

const DEFAULT_UNITS: FileSizeUnits = { b: "B", kb: "KB", mb: "MB" };

/** `1536` → `"1,5 KB"`, `10485760` → `"10 MB"` (comma decimal, 08 §8). Units come translated. */
export function formatFileSize(bytes: number, units: FileSizeUnits = DEFAULT_UNITS): string {
  if (!Number.isFinite(bytes) || bytes < 0) return `0 ${units.b}`;
  if (bytes < 1024) return `${Math.round(bytes)} ${units.b}`;
  const [value, unit] = bytes < MB ? [bytes / 1024, units.kb] : [bytes / MB, units.mb];
  const rounded = Math.round(value * 10) / 10;
  const text = Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1).replace(".", ",");
  return `${text} ${unit}`;
}

/** Lower-case extension with the dot: `"Tovarlar.XLSX"` → `".xlsx"`; `""` when there is none. */
export function fileExtension(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot <= 0 ? "" : name.slice(dot).toLowerCase();
}

/**
 * `accept` check like the browser's: entries are extensions (".xlsx") or MIME types ("text/csv",
 * "image/*"). Browsers report CSV inconsistently (text/csv, application/vnd.ms-excel, ""), so an
 * extension match is enough.
 */
export function fileMatchesAccept(file: { name: string; type: string }, accept: readonly string[]): boolean {
  if (accept.length === 0) return true;
  const ext = fileExtension(file.name);
  const type = file.type.toLowerCase();
  return accept.some((entry) => {
    const a = entry.trim().toLowerCase();
    if (a.startsWith(".")) return a === ext;
    if (a.endsWith("/*")) return type.startsWith(a.slice(0, -1));
    return a === type;
  });
}

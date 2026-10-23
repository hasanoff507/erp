/**
 * CP866 encoder for ESC/POS text mode (`ESC t 17`, 24 §6.1, 08 §13).
 *
 * CP866 has Russian Cyrillic and Ў/ў, but NOT Қ/Ғ/Ҳ (Uzbek Cyrillic) and no U+02BB — a receipt with those
 * goes through raster mode (`needsRaster`). `normalizeReceiptText` runs first (ʻ → ', NBSP → space …).
 */

/** Unicode → CP866 byte for the non-ASCII part of the code page (0x80–0xFF). */
const HIGH: ReadonlyMap<string, number> = (() => {
  const map = new Map<string, number>();
  // А..Я (U+0410..U+042F) → 0x80..0x9F; а..п (U+0430..U+043F) → 0xA0..0xAF; р..я (U+0440..U+044F) → 0xE0..0xEF
  for (let i = 0; i < 32; i += 1) map.set(String.fromCharCode(0x410 + i), 0x80 + i);
  for (let i = 0; i < 16; i += 1) map.set(String.fromCharCode(0x430 + i), 0xa0 + i);
  for (let i = 0; i < 16; i += 1) map.set(String.fromCharCode(0x440 + i), 0xe0 + i);
  const rest: [string, number][] = [
    ["Ё", 0xf0],
    ["ё", 0xf1],
    ["Є", 0xf2],
    ["є", 0xf3],
    ["Ї", 0xf4],
    ["ї", 0xf5],
    ["Ў", 0xf6],
    ["ў", 0xf7],
    ["°", 0xf8],
    ["∙", 0xf9],
    ["·", 0xfa],
    ["√", 0xfb],
    ["№", 0xfc],
    ["¤", 0xfd],
    ["■", 0xfe],
    // box drawing used by receipts
    ["─", 0xc4],
    ["═", 0xcd],
    ["│", 0xb3],
  ];
  for (const [ch, b] of rest) map.set(ch, b);
  return map;
})();

/** CP866 byte for one character, or null when the code page has no such glyph. */
export function cp866Byte(ch: string): number | null {
  const code = ch.codePointAt(0) ?? -1;
  if (code === 0x0a) return 0x0a;
  if (code >= 0x20 && code <= 0x7e) return code;
  return HIGH.get(ch) ?? null;
}

export function canEncodeCp866(text: string): boolean {
  for (const ch of text) if (cp866Byte(ch) === null) return false;
  return true;
}

/** Encodes text; characters outside CP866 become `?` (only reached with render_mode = "text"). */
export function encodeCp866(text: string): Uint8Array {
  const out: number[] = [];
  for (const ch of text) out.push(cp866Byte(ch) ?? 0x3f);
  return Uint8Array.from(out);
}

/** Uzbek Cyrillic letters missing from CP866 (24 §6.1): their presence switches `auto` to raster. */
export const UZBEK_CYRILLIC_EXTRA = /[ҚқҒғҲҳ]/u;

/**
 * Printer-safe text (24 §6.1, POS-16): U+02BB/U+02BC/U+2018/U+2019 → `'` (always — the font fallback of
 * raster mode does not need them either), NBSP / thin spaces → space, minus/dashes → `-`, «» → `"`,
 * `×` → `x`, `…` → `...`.
 */
export function normalizeReceiptText(text: string): string {
  return text
    .replace(/[\u02BB\u02BC\u2018\u2019\u0060\u00B4]/gu, "'")
    .replace(/[\u00A0\u202F\u2007\u2009]/gu, " ")
    .replace(/[\u2212\u2013\u2014]/gu, "-")
    .replace(/[\u00AB\u00BB\u201C\u201D\u201E]/gu, '"')
    .replace(/\u00D7/gu, "x")
    .replace(/\u2026/gu, "...");
}

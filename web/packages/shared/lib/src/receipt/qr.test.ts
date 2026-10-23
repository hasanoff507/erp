import { describe, expect, it } from "vitest";

import { encodeQr, qrSvg } from "./qr.ts";

/** Matrix for "HELLO WORLD" (byte mode, ECC M) — decoded and verified with zxing-cpp. */
const HELLO_WORLD = [
  "111111101100101111111",
  "100000100001001000001",
  "101110100101001011101",
  "101110101001001011101",
  "101110101110101011101",
  "100000101001001000001",
  "111111101010101111111",
  "000000001001100000000",
  "100010111111011111001",
  "000100001011100001111",
  "001111110011011010010",
  "111110001100010000000",
  "111110101010101100110",
  "000000001010111101011",
  "111111101110101011010",
  "100000100101110110011",
  "101110101101011000110",
  "101110100100100011011",
  "101110100111000111000",
  "100000100001010000000",
  "111111101111111110101",
];

const rows = (text: string) => {
  const q = encodeQr(text);
  return Array.from({ length: q.size }, (_, y) =>
    Array.from({ length: q.size }, (_, x) => (q.isDark(x, y) ? "1" : "0")).join(""),
  );
};

describe("QR encoder (OFD receipt QR, 08 §13.1)", () => {
  it("matches the verified golden matrix", () => {
    expect(rows("HELLO WORLD")).toEqual(HELLO_WORLD);
  });

  it("picks the smallest version: OFD URL → version 5 (37 modules), long data → version 7+ with version info", () => {
    const url = "https://ofd.soliq.uz/check?t=ZZ000000000000&r=77&c=20261012224100&s=123456789012";
    expect(encodeQr(url).version).toBe(5);
    expect(encodeQr(url).size).toBe(37);
    const big = encodeQr("x".repeat(150));
    expect(big.version).toBe(8);
    expect(() => encodeQr("z".repeat(3000))).toThrow();
  });

  it("SVG is ≥ 30 mm and has no inline style", () => {
    const svg = qrSvg("A");
    expect(svg).toContain('width="32mm"');
    expect(svg).not.toContain("style=");
  });
});

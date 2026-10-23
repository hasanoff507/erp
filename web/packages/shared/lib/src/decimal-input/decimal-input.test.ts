import { describe, expect, it } from "vitest";

import { ean13CheckDigit, isValidEan13, isValidGtin } from "../barcode/index.ts";
import { fileMatchesAccept, formatFileSize } from "../file/index.ts";

import {
  caretAfterSignificantChars,
  fromDecimalString,
  groupDecimalInput,
  sanitizeDecimalInput,
  significantCharsBefore,
  toDecimalString,
} from "./index.ts";

const NBSP = " ";

describe("decimal input — string only (qaror #57)", () => {
  it("sanitizes typing: grouping, comma/dot, leading zeros, scale", () => {
    expect(sanitizeDecimalInput(`1${NBSP}234${NBSP}567`, { scale: 0 })).toBe("1234567");
    expect(sanitizeDecimalInput("12,5", { scale: 2 })).toBe("12.5");
    expect(sanitizeDecimalInput("12.567", { scale: 2 })).toBe("12.56");
    expect(sanitizeDecimalInput("12,5", { scale: 0 })).toBe("12");
    expect(sanitizeDecimalInput(",5", { scale: 0 })).toBe("");
    expect(sanitizeDecimalInput("007", { scale: 0 })).toBe("7");
    expect(sanitizeDecimalInput("0", { scale: 0 })).toBe("0");
    expect(sanitizeDecimalInput(",5", { scale: 3 })).toBe("0.5");
    expect(sanitizeDecimalInput("12.", { scale: 2 })).toBe("12.");
    expect(sanitizeDecimalInput("abc", { scale: 2 })).toBe("");
    expect(sanitizeDecimalInput("1e6", { scale: 2 })).toBe("16");
  });

  it("minus only when allowed", () => {
    expect(sanitizeDecimalInput("-500", { scale: 0 })).toBe("500");
    expect(sanitizeDecimalInput("-500", { scale: 0, allowNegative: true })).toBe("-500");
    expect(sanitizeDecimalInput("-", { scale: 0, allowNegative: true })).toBe("-");
    expect(sanitizeDecimalInput("5-00", { scale: 0, allowNegative: true })).toBe("500");
  });

  it("limits integer digits", () => {
    expect(sanitizeDecimalInput("12345678901234567890", { scale: 0, maxIntegerDigits: 4 })).toBe("1234");
  });

  it("groups for display with NBSP and comma", () => {
    expect(groupDecimalInput("1234567")).toBe(`1${NBSP}234${NBSP}567`);
    expect(groupDecimalInput("1234.5")).toBe(`1${NBSP}234,5`);
    expect(groupDecimalInput("12.")).toBe("12,");
    expect(groupDecimalInput("-1000")).toBe(`−1${NBSP}000`);
    expect(groupDecimalInput("")).toBe("");
    expect(groupDecimalInput("999")).toBe("999");
  });

  it("produces API decimal strings with a fixed scale and never rounds", () => {
    expect(toDecimalString("12000", 2)).toBe("12000.00");
    expect(toDecimalString("8333.3", 4)).toBe("8333.3000");
    expect(toDecimalString("12.", 2)).toBe("12.00");
    expect(toDecimalString("-0", 2)).toBe("0.00");
    expect(toDecimalString("-", 2)).toBe("");
    expect(toDecimalString("", 2)).toBe("");
    expect(toDecimalString("5", 0)).toBe("5");
  });

  it("reads API values back", () => {
    expect(fromDecimalString("12000.00", 0)).toBe("12000");
    expect(fromDecimalString("12000.50", 0)).toBe("12000.5");
    expect(fromDecimalString("1.250", 3)).toBe("1.250");
    expect(fromDecimalString("8333.3300", 4)).toBe("8333.3300");
    expect(fromDecimalString(null, 2)).toBe("");
    expect(fromDecimalString("1e3", 2)).toBe("");
  });

  it("keeps the caret on the same digit across regrouping", () => {
    const display = `1${NBSP}234${NBSP}567`;
    expect(significantCharsBefore(display, 5)).toBe(4);
    expect(caretAfterSignificantChars(display, 4)).toBe(5);
    expect(caretAfterSignificantChars(display, 0)).toBe(0);
    expect(caretAfterSignificantChars(display, 99)).toBe(display.length);
  });
});

describe("barcode — GS1 check digit", () => {
  it("computes and validates EAN-13", () => {
    expect(ean13CheckDigit("460123456789")).toBe("3");
    expect(isValidEan13("4601234567893")).toBe(true);
    expect(isValidEan13("4601234567890")).toBe(false);
    expect(isValidEan13("46012345678")).toBe(false);
  });

  it("validates EAN-8 and GTIN-14", () => {
    expect(isValidGtin("96385074")).toBe(true);
    expect(isValidGtin("10012345678902")).toBe(true);
    expect(isValidGtin("1001234567890a")).toBe(false);
  });
});

describe("file helpers — 17 §12", () => {
  it("formats sizes", () => {
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(1536)).toBe("1,5 KB");
    expect(formatFileSize(10 * 1024 * 1024)).toBe("10 MB");
    expect(formatFileSize(1024 * 1024, { b: "Б", kb: "КБ", mb: "МБ" })).toBe("1 МБ");
  });

  it("matches accept lists by extension or MIME", () => {
    const accept = [".xlsx", ".csv"];
    expect(fileMatchesAccept({ name: "Tovarlar.XLSX", type: "" }, accept)).toBe(true);
    expect(fileMatchesAccept({ name: "a.csv", type: "application/vnd.ms-excel" }, accept)).toBe(true);
    expect(fileMatchesAccept({ name: "a.pdf", type: "application/pdf" }, accept)).toBe(false);
    expect(fileMatchesAccept({ name: "a.png", type: "image/png" }, ["image/*"])).toBe(true);
    expect(fileMatchesAccept({ name: "x", type: "" }, [])).toBe(true);
  });
});

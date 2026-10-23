/**
 * zod → i18n keys (08 §11, 17 §15.1). `installZodErrorMap()` runs once on import of @shared/ui/form,
 * so `z.string().min(1)` yields `validation.required`, `.max(100)` → `validation.max_length`, etc.
 * Explicit messages in a schema (`{ message: "validation.terms_required" }`) still win.
 */
import { z } from "zod";

import { isValidGtin } from "@shared/lib/barcode";
import { isCompleteNationalPhone } from "@shared/lib/phone";

import { withParams } from "#/composites/form-field.tsx";

let installed = false;

export function installZodErrorMap(): void {
  if (installed) return;
  installed = true;
  z.config({
    customError: (issue) => {
      switch (issue.code) {
        case "invalid_type":
          return issue.input === undefined || issue.input === null
            ? "validation.required"
            : "validation.invalid_format";
        case "too_small": {
          const min = issue.minimum.toString();
          if (issue.origin === "string")
            return min === "1" ? "validation.required" : withParams("validation.min_length", { min });
          if (issue.origin === "array" || issue.origin === "set") return "validation.required";
          return withParams("validation.min_value", { min });
        }
        case "too_big": {
          const max = issue.maximum.toString();
          if (issue.origin === "string" || issue.origin === "array") return "validation.max_length";
          return withParams("validation.max_value", { max });
        }
        case "invalid_format":
          return issue.format === "email" ? "validation.email_format" : "validation.invalid_format";
        case "invalid_value":
          return "validation.invalid_choice";
        default:
          return undefined;
      }
    },
  });
}

installZodErrorMap();

/** Required trimmed text, optional max length (free text ≤ 1000 — 17 §3). */
export function zRequiredString(max = 1000) {
  return z.string().trim().min(1).max(max);
}

/** Uzbek phone as typed in PhoneInput (`"90 123 45 67"` or E.164) — 9 national digits. */
export function zPhone() {
  return z.string().refine((v) => isCompleteNationalPhone(v), { message: "validation.phone_format" });
}

/** 6-digit OTP (14 §OTP). */
export function zOtp(length = 6) {
  return z
    .string()
    .refine((v) => v.length === length && [...v].every((ch) => ch >= "0" && ch <= "9"), {
      message: "validation.otp_length",
    });
}

/** GTIN/EAN barcode with a valid check digit (8/12/13/14 digits). */
export function zEan() {
  return z.string().refine((v) => isValidGtin(v), { message: "validation.barcode_check_digit" });
}

export interface ZDecimalOptions {
  /** Max fraction digits (money 2, price 4, qty 3). */
  scale: number;
  /** Allow an empty string (optional field). Default false → `validation.required`. */
  optional?: boolean;
  /** Reject zero and negatives (`validation.must_be_positive`). */
  positive?: boolean;
  allowNegative?: boolean;
}

function isDecimalString(v: string, scale: number, allowNegative: boolean): boolean {
  const body = allowNegative && v.startsWith("-") ? v.slice(1) : v;
  const dot = body.indexOf(".");
  const intPart = dot === -1 ? body : body.slice(0, dot);
  const frac = dot === -1 ? "" : body.slice(dot + 1);
  const digits = (s: string) => s.length > 0 && [...s].every((ch) => ch >= "0" && ch <= "9");
  return digits(intPart) && (dot === -1 || (digits(frac) && frac.length <= scale));
}

/**
 * Decimal STRING field (MoneyInput/PriceInput output, 17 §3). Validates the shape only — no Number
 * conversion (qaror #57). `positive` checks "not all zeros" and no minus sign.
 */
export function zDecimal({
  scale,
  optional = false,
  positive = false,
  allowNegative = false,
}: ZDecimalOptions) {
  return z.string().superRefine((v, ctx) => {
    if (v === "") {
      if (!optional) ctx.addIssue({ code: "custom", message: "validation.required" });
      return;
    }
    if (!isDecimalString(v, scale, allowNegative)) {
      ctx.addIssue({ code: "custom", message: "validation.decimal_format" });
      return;
    }
    if (positive && (v.startsWith("-") || [...v].every((ch) => ch === "0" || ch === "."))) {
      ctx.addIssue({ code: "custom", message: "validation.must_be_positive" });
    }
  });
}

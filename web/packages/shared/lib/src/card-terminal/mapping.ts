/**
 * `CardTxResult` → `CardResult` (24 §6.5, 21 §9.4) — same rules as the backend `card_result_from_port`:
 * status map (cancelled/error → declined, timeout → unknown), 4+4 mask (the BIN is used only here, in memory,
 * for the `card_bin_rules` lookup and then dropped — 15 §9.3), `card_type` terminal → BIN table → `unknown`.
 */
import { fromTiyin, type Money } from "#/money/index.ts";

import type {
  CardBinRule,
  CardResult,
  CardTxResult,
  CardTypeSource,
  CardTypeValue,
  PortStatus,
  ResolvedBy,
  TxStatus,
} from "./types.ts";

export const MASK_RE = /^[0-9]{4}\*+[0-9]{4}$/;
const RAW_MASK_RE = /^([0-9]{4,8})[*Xx•]+([0-9]{4})$/;

export function txStatusOf(status: PortStatus): Exclude<TxStatus, "pending" | "voided"> {
  switch (status) {
    case "approved":
      return "approved";
    case "declined":
    case "cancelled":
    case "error":
      return "declined";
    case "timeout":
    case "unknown":
      return "unknown";
  }
}

export function declineCodeOf(status: PortStatus, bankCode: string | null): string | null {
  if (status === "cancelled" || status === "error") return status;
  return status === "declined" ? bankCode : null;
}

export interface NormalizedMask {
  mask: string;
  /** First 6–8 digits when the driver gave them — keep only in memory. */
  bin: string | null;
}

/** `860031******1234` → `8600********1234` + BIN; a full PAN never matches (no stars). */
export function normalizeMask(raw: string | null | undefined): NormalizedMask | null {
  if (!raw) return null;
  const compact = raw.replace(/[\s-]/g, "");
  const m = RAW_MASK_RE.exec(compact);
  if (!m) return null;
  const head = m[1] ?? "";
  const tail = m[2] ?? "";
  const stars = compact.length - 4 - tail.length;
  const mask = `${head.slice(0, 4)}${"*".repeat(stars)}${tail}`;
  if (!MASK_RE.test(mask)) return null;
  return { mask, bin: head.length >= 6 ? head : null };
}

/** Longest matching prefix valid on `today` (YYYY-MM-DD). */
export function lookupBin(bin: string, rules: readonly CardBinRule[], today: string): CardBinRule | null {
  let best: CardBinRule | null = null;
  for (const rule of rules) {
    if (!bin.startsWith(rule.bin_prefix)) continue;
    if (rule.valid_from > today) continue;
    if (rule.valid_to && rule.valid_to < today) continue;
    if (!best || rule.bin_prefix.length > best.bin_prefix.length) best = rule;
  }
  return best;
}

export function deriveCardType(
  terminalType: CardTypeValue | null,
  binRuleType: CardTypeValue | null,
): { card_type: CardTypeValue; card_type_source: CardTypeSource } {
  if (terminalType) return { card_type: terminalType, card_type_source: "terminal" };
  if (binRuleType && binRuleType !== "unknown")
    return { card_type: binRuleType, card_type_source: "bin_table" };
  return { card_type: "unknown", card_type_source: "bin_table" };
}

export interface ToCardResultOptions {
  cardTerminalId: string;
  requestedAmount: Money;
  resolvedBy: Exclude<ResolvedBy, "manager">;
  originalAttemptId?: string | null;
  binRules?: readonly CardBinRule[];
  today?: string;
}

export function toCardResult(tx: CardTxResult, options: ToCardResultOptions): CardResult {
  const status = txStatusOf(tx.status);
  const norm = normalizeMask(tx.card_mask);
  let cardType: CardTypeValue | null = null;
  let source: CardTypeSource | null = null;
  if (status === "approved" && tx.kind === "purchase") {
    const today = options.today ?? new Date().toISOString().slice(0, 10);
    const rule = norm?.bin && !tx.card_type ? lookupBin(norm.bin, options.binRules ?? [], today) : null;
    const derived = deriveCardType(tx.card_type, rule?.card_type ?? null);
    cardType = derived.card_type;
    source = derived.card_type_source;
  }
  return {
    attempt_id: tx.attempt_id,
    card_terminal_id: options.cardTerminalId,
    kind: tx.kind,
    original_attempt_id: options.originalAttemptId ?? null,
    status,
    amount: tx.amount_tiyin === null ? options.requestedAmount : fromTiyin(tx.amount_tiyin),
    approval_code: tx.approval_code,
    rrn: tx.rrn,
    stan: tx.stan,
    card_mask: norm?.mask ?? null,
    card_scheme: tx.card_scheme,
    card_type: cardType,
    card_type_source: source,
    entry_mode: tx.entry_mode,
    tid: tx.tid,
    mid: tx.mid,
    acquirer: tx.acquirer,
    tx_at: tx.tx_at,
    resolved_by: options.resolvedBy,
    decline_code: declineCodeOf(tx.status, tx.decline_code),
    decline_message: tx.decline_message,
    slip_text: tx.slip_text ?? null,
  };
}

/** Manager closes an `unknown` attempt from the terminal slip (18 §16a.4) — no card details at all. */
export function managerCardResult(input: {
  attemptId: string;
  cardTerminalId: string;
  amount: Money;
  passed: boolean;
}): CardResult {
  return {
    attempt_id: input.attemptId,
    card_terminal_id: input.cardTerminalId,
    kind: "purchase",
    original_attempt_id: null,
    status: input.passed ? "approved" : "declined",
    amount: input.amount,
    approval_code: null,
    rrn: null,
    stan: null,
    card_mask: null,
    card_scheme: null,
    card_type: null,
    card_type_source: null,
    entry_mode: null,
    tid: null,
    mid: null,
    acquirer: null,
    tx_at: null,
    resolved_by: "manager",
    decline_code: input.passed ? null : "not_found",
    decline_message: null,
    slip_text: null,
  };
}

/** UUIDv7 (RFC 9562) without dependencies — `attempt_id` is created before the terminal call. */
export function newAttemptId(now: number = Date.now()): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let ts = now;
  for (let i = 5; i >= 0; i--) {
    bytes[i] = ts % 256;
    ts = Math.floor(ts / 256);
  }
  bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x70;
  bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

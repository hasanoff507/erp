/**
 * The TS DTOs mirror the backend Pydantic contract (23 §1 item 16, 24 §6.5): every field of the Python
 * `CardPurchaseRequest`, `CardTxResult`, `SettlementResult`, `TerminalHealth` (ports.py) and `CardResultIn`
 * (schemas.py) exists in the TS sample objects below and vice versa.
 */
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import type { Money } from "#/money/index.ts";

import type {
  CardPurchaseRequest,
  CardResult,
  CardTxResult,
  SettlementResult,
  TerminalHealth,
} from "./types.ts";

const APP = "../../../../../../backend/app/modules/integrations/card_terminal/application/";
const portsPy = fileURLToPath(new URL(`${APP}ports.py`, import.meta.url));
const schemasPy = fileURLToPath(new URL(`${APP}schemas.py`, import.meta.url));

function pyFields(source: string, cls: string): string[] {
  const start = source.indexOf(`class ${cls}(`);
  if (start < 0) throw new Error(`class ${cls} not found`);
  const body = source.slice(start).split("\n").slice(1);
  const fields: string[] = [];
  for (const line of body) {
    if (/^\S/.test(line)) break; // next top-level statement
    const m = /^ {4}([a-z_]+): /.exec(line);
    if (m?.[1] && m[1] !== "model_config") fields.push(m[1]);
  }
  return fields.sort();
}

const purchase: Required<CardPurchaseRequest> = {
  attempt_id: "",
  terminal: { card_terminal_id: "", local_id: null },
  amount_tiyin: 0,
  currency: "UZS",
  cash_register_id: "",
  client_event_id: "",
  receipt_seq: null,
};
const tx: Required<CardTxResult> = {
  attempt_id: "",
  kind: "purchase",
  status: "approved",
  amount_tiyin: 0,
  approval_code: null,
  rrn: null,
  stan: null,
  card_mask: null,
  card_scheme: null,
  card_type: null,
  entry_mode: null,
  tid: null,
  mid: null,
  acquirer: null,
  tx_at: null,
  decline_code: null,
  decline_message: null,
  slip_text: null,
};
const settlement: Required<SettlementResult> = {
  tid: null,
  batch_no: null,
  count: 0,
  total_tiyin: 0,
  by_scheme: [],
  settled_at: "",
  refund_count: 0,
  refund_total_tiyin: 0,
};
const health: Required<TerminalHealth> = { status: "online", tid: null, last_tx_at: null, message: null };
const result: CardResult = {
  attempt_id: "",
  card_terminal_id: "",
  kind: "purchase",
  original_attempt_id: null,
  status: "approved",
  amount: "0.00" as Money,
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
  resolved_by: "auto",
  decline_code: null,
  decline_message: null,
  slip_text: null,
};

describe.skipIf(!existsSync(portsPy))("card terminal DTOs mirror the Pydantic contract", () => {
  const ports = existsSync(portsPy) ? readFileSync(portsPy, "utf8") : "";
  const schemas = existsSync(schemasPy) ? readFileSync(schemasPy, "utf8") : "";
  it.each([
    ["CardPurchaseRequest", purchase, ports],
    ["CardTxResult", tx, ports],
    ["SettlementResult", settlement, ports],
    ["TerminalHealth", health, ports],
    ["CardResultIn", result, schemas],
  ] as const)("%s", (cls, sample, source) => {
    expect(Object.keys(sample).sort()).toEqual(pyFields(source, cls));
  });
});

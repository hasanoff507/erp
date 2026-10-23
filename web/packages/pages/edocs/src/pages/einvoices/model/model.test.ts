import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { FAKE_KEY } from "@shared/lib/eimzo";

import { toLines } from "../ui/dialogs/CreateOutDialog.tsx";
import {
  $detail,
  $inbound,
  $kpis,
  $notice,
  $outbound,
  computeKpis,
  einvoiceSelected,
  getDetailFx,
  inboundParams,
  listEttnFx,
  listInboundFx,
  listOutboundFx,
  listPoaFx,
  loadKeysFx,
  loadKpiFx,
  normalizeDecimal,
  pageMounted,
  payloadLines,
  riskFilterChanged,
  signAcceptFx,
  signAcceptRequested,
  type EInvoice,
} from "./index.ts";

function einvoice(id: string, patch: Partial<EInvoice> = {}): EInvoice {
  return {
    id,
    direction: "in",
    operator: "faktura",
    operator_doc_id: `OP-${id}`,
    counterparty_id: "c-1",
    counterparty: { id: "c-1", name: "Mega Trade", stir: "301234567" },
    status: "received",
    risk_flag: "unknown",
    factura_type: "standard",
    related_einvoice_id: null,
    related_doc_type: null,
    related_doc_id: null,
    number: `EHF-${id}`,
    doc_date: "2026-10-10",
    total_amount: "112000.00",
    vat_amount: "12000.00",
    signed_at: null,
    signed_by: null,
    last_error: null,
    created_at: "2026-10-10T08:00:00Z",
    updated_at: "2026-10-10T08:00:00Z",
    ...patch,
  };
}

const empty = { items: [], next_cursor: null };

describe("BO-15 lib", () => {
  it("KPI: month count/sum/VAT, awaiting signature, deferred red+unknown, unsent outgoing", () => {
    const k = computeKpis(
      [
        einvoice("1"),
        einvoice("2", { risk_flag: "green", status: "accepted" }),
        einvoice("3", { risk_flag: "red", doc_date: "2026-09-30", status: "accepted" }),
        einvoice("4", { status: "rejected" }),
      ],
      [
        einvoice("o1", { direction: "out", status: "draft" }),
        einvoice("o2", { direction: "out", status: "sent" }),
      ],
      "2026-10",
    );
    expect(k).toEqual({
      inCount: 3,
      inTotal: "336000.00",
      inVat: "36000.00",
      awaitingSignature: 1,
      deferredVat: "24000.00",
      outUnsent: 1,
    });
  });

  it("inbound params map the filters (19 §19)", () => {
    expect(inboundParams({ filters: { risk: "all", status: "all" }, cursor: null })).toEqual({
      direction: "in",
      limit: 50,
    });
    expect(inboundParams({ filters: { risk: "unknown", status: "received" }, cursor: "c" })).toEqual({
      direction: "in",
      risk_flag: "unknown",
      status: "received",
      cursor: "c",
      limit: 50,
    });
  });

  it("payload lines are read defensively", () => {
    expect(payloadLines({ lines: [{ name: "Suv", qty: "2.000", net_amount: "100.00", vat_amount: "12.00", vat_rate: "12.00" }] })).toEqual([
      { line_no: 1, name: "Suv", qty: "2.000", net_amount: "100.00", vat_rate: "12.00", vat_amount: "12.00", total_amount: "112.00" },
    ]); // prettier-ignore
    expect(payloadLines(undefined)).toEqual([]);
  });

  it("decimal inputs never go through Number()", () => {
    expect(normalizeDecimal("1 200,5", 3)).toBe("1200.500");
    expect(normalizeDecimal("abc", 3)).toBeNull();
    expect(normalizeDecimal("1.23456", 4)).toBeNull();
    expect(toLines([{ key: 1, name: "Xizmat", qty: "2", price: "1000", vat: "12.00" }])).toEqual([
      { name: "Xizmat", qty: "2.000", price: "1000.0000", vat_rate: "12.00" },
    ]);
    expect(toLines([{ key: 1, name: "", qty: "2", price: "1000", vat: "12.00" }])).toBeNull();
  });
});

describe("BO-15 model", () => {
  function scope(calls: unknown[]) {
    return fork({
      handlers: [
        [listInboundFx, (p: unknown) => (calls.push(["in", p]), Promise.resolve({ items: [einvoice("1")], next_cursor: null }))],
        [listOutboundFx, () => Promise.resolve({ items: [einvoice("o1", { direction: "out", status: "draft" })], next_cursor: null })],
        [listEttnFx, () => Promise.resolve(empty)],
        [listPoaFx, () => Promise.resolve(empty)],
        [loadKpiFx, () => Promise.resolve({ inbound: { items: [einvoice("1")], next_cursor: null }, outbound: empty })],
        [loadKeysFx, () => Promise.resolve([FAKE_KEY])],
        [getDetailFx, (id: string) => Promise.resolve({ ...einvoice(id), payload: {} })],
        [signAcceptFx, (p: unknown) => (calls.push(["signAccept", p]), Promise.resolve({ status: "queued" }))],
      ],
    }); // prettier-ignore
  }

  it("mount loads lists, KPI and keys; a filter reloads the inbound list", async () => {
    const calls: unknown[] = [];
    const s = scope(calls);
    await allSettled(pageMounted, { scope: s, params: { today: "2026-10-18", canOutbound: true } });
    expect(s.getState($inbound).map((e) => e.id)).toEqual(["1"]);
    expect(s.getState($outbound).map((e) => e.id)).toEqual(["o1"]);
    expect(s.getState($kpis)?.awaitingSignature).toBe(1);
    await allSettled(riskFilterChanged, { scope: s, params: "red" });
    expect(calls.at(-1)).toEqual(["in", { filters: { risk: "red", status: "all" }, cursor: null }]);
  });

  it("«Imzolab qabul qilish» signs with the chosen key, then shows a notice", async () => {
    const calls: unknown[] = [];
    const s = scope(calls);
    await allSettled(pageMounted, { scope: s, params: { today: "2026-10-18", canOutbound: false } });
    await allSettled(einvoiceSelected, { scope: s, params: "1" });
    expect(s.getState($detail)?.id).toBe("1");
    await allSettled(signAcceptRequested, { scope: s });
    expect(calls).toContainEqual(["signAccept", { id: "1", key: FAKE_KEY, signed: false }]);
    expect(s.getState($notice)?.key).toBe("notices.accepted");
  });
});

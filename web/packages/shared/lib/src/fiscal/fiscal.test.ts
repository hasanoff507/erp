import { describe, expect, it, vi } from "vitest";

import { AgentError } from "#/agent/index.ts";
import type { Money } from "#/money/index.ts";

import {
  createLocalBridgeFiscalAdapter,
  fiscalItem,
  fiscalPayments,
  fiscalReceipt,
  fiscalShares,
  FiscalError,
  localFiscalReadiness,
  milliOf,
  parseFiscalResult,
  tiyinOf,
  type FiscalLineInput,
} from "./index.ts";

const m = (v: string) => v as Money;
const REGISTER = { cash_register_id: "0190a000-0000-7000-8000-0000000000c1", local_id: "fm-1" };
const RESULT = {
  fm_terminal_id: "ZZ000000000001",
  fm_receipt_seq: 17,
  fiscal_sign: "123456789012",
  qr_url: "https://ofd.soliq.uz/check?t=ZZ000000000001&r=17&c=20261018120000&s=123456789012",
  fiscal_at: "2026-10-18T07:00:00Z",
};

const line = (over: Partial<FiscalLineInput> = {}): FiscalLineInput => ({
  name: "Non Patir",
  nameRu: "Лепёшка",
  mxik: "10101001001000000",
  packageCode: "1500000",
  unitCode: "dona",
  qty: "2.000",
  price: "4000.0000",
  lineTotal: m("8000.00"),
  vatRate: "12.00",
  vatAmount: m("857.14"),
  markingCode: null,
  ...over,
});

describe("tiyin boundary (21 §1, qaror #12)", () => {
  it("decimal strings → int tiyin / milli, HALF_UP, int53-safe", () => {
    expect(tiyinOf("12000.00")).toBe(1_200_000);
    expect(tiyinOf("8333.3350")).toBe(833_334);
    expect(tiyinOf("0.01")).toBe(1);
    expect(milliOf("1.250")).toBe(1250);
    expect(() => tiyinOf("99999999999999999999.00")).toThrow();
    expect(() => tiyinOf("12 000")).toThrow();
  });

  it("item: two-language name, 17-digit MXIK only, marking code as scanned", () => {
    const item = fiscalItem(line({ markingCode: "0104780000000011215abc\u001d93xyz", mxik: "123" }));
    expect(item).toEqual({
      name: "Non Patir / Лепёшка",
      mxik: null,
      package_code: "1500000",
      unit_code: "dona",
      qty_milli: 2000,
      price_tiyin: 400_000,
      amount_tiyin: 800_000,
      vat_rate: "12.00",
      vat_tiyin: 85_714,
      marking_codes: ["0104780000000011215abc\u001d93xyz"],
    });
  });

  it("18 §4.5 shares: ratio, rest on the largest line (ties — later), qty ≥ 0.001, VAT per share", () => {
    const lines = [
      line({ lineTotal: m("10000.00"), qty: "1.000" }),
      line({ lineTotal: m("20000.00"), qty: "3.000" }),
      line({ lineTotal: m("20000.00"), qty: "0.001" }),
    ];
    const shares = fiscalShares(lines, m("33333.33"));
    expect(shares.map((s) => s.amount)).toEqual(["6666.67", "13333.33", "13333.33"]);
    expect(shares.reduce((a, s) => a + tiyinOf(s.amount), 0)).toBe(3_333_333);
    expect(shares.map((s) => s.qty)).toEqual(["0.667", "2.000", "0.001"]);
    expect(shares[1]?.vat).toBe("1428.57");
    // the whole receipt paid → lines unchanged
    expect(fiscalShares([line()], m("8000.00"))).toEqual([{ amount: "8000.00", qty: "2.000", vat: "857.14" }]);
  });

  it("payments: forms, mixed, integrated card requisites only as a 4+4 mask (PCI), Σ must match", () => {
    expect(fiscalPayments([{ method: "click", amount: m("5000.00") }])).toMatchObject({
      payment_form: "qr",
      qr_tiyin: 500_000,
    });
    const mixed = fiscalPayments([
      { method: "cash", amount: m("3000.00") },
      {
        method: "card",
        amount: m("5000.00"),
        card: { cardType: "social", cardMask: "860031******1234", rrn: "612345678901" },
      },
    ]);
    expect(mixed).toEqual({
      payment_form: "mixed",
      cash_tiyin: 300_000,
      card_tiyin: 500_000,
      qr_tiyin: 0,
      card_type: "social",
      card_mask: null, // not a 4+4 mask → never sent
      rrn: "612345678901",
    });
    expect(() =>
      fiscalReceipt({
        register: REGISTER,
        receiptSeq: 1,
        kind: "sale",
        items: [fiscalItem(line())],
        payments: [{ method: "cash", amount: m("7000.00") }],
      }),
    ).toThrow();
    const ok = fiscalReceipt({
      register: REGISTER,
      receiptSeq: 4,
      kind: "sale",
      items: [fiscalItem(line())],
      payments: [{ method: "cash", amount: m("8000.00") }],
    });
    expect(ok).toMatchObject({ receipt_seq: 4, kind: "sale", total_tiyin: 800_000, cash_register: REGISTER });
  });
});

describe("LocalBridgeFiscalAdapter (21 §16.1, agent-local-api.md)", () => {
  const receipt = () =>
    fiscalReceipt({
      register: REGISTER,
      receiptSeq: 9,
      kind: "sale",
      items: [fiscalItem(line())],
      payments: [{ method: "cash", amount: m("8000.00") }],
    });

  it("sale → POST /v1/fiscal/sale with the tiyin payload; only the five result fields come back", async () => {
    const request = vi.fn(() => Promise.resolve({ ...RESULT, extra: "x" }));
    const port = createLocalBridgeFiscalAdapter({ request } as never);
    await expect(port.registerSale(receipt())).resolves.toEqual(RESULT);
    expect(request).toHaveBeenCalledWith("POST", "/v1/fiscal/sale", receipt(), { timeoutMs: 20_000 });
  });

  it("error mapping: unreachable / unpaired / 404 → not connected; timeout / outcome_unknown → retry the same", async () => {
    const fail = (e: unknown) =>
      createLocalBridgeFiscalAdapter({ request: () => Promise.reject(e) } as never).registerSale(receipt());
    await expect(fail(new AgentError("unreachable", "AGENT_UNREACHABLE"))).rejects.toMatchObject({
      code: "FISCAL_MODULE_NOT_CONNECTED",
    });
    await expect(fail(new AgentError("unpaired", "AGENT_NOT_PAIRED", { status: 401 }))).rejects.toMatchObject({
      code: "FISCAL_MODULE_NOT_CONNECTED",
    });
    await expect(fail(new AgentError("http", "NOT_FOUND", { status: 404 }))).rejects.toMatchObject({
      code: "FISCAL_MODULE_NOT_CONNECTED",
    });
    const timeout = await fail(new AgentError("timeout", "AGENT_TIMEOUT")).catch((e: unknown) => e);
    expect(timeout).toBeInstanceOf(FiscalError);
    expect(timeout).toMatchObject({ code: "FISCAL_RESULT_UNKNOWN", retrySame: true });
    await expect(
      fail(
        new AgentError("http", "FISCAL_PROVIDER_ERROR", {
          status: 502,
          params: { reason: "outcome_unknown" },
        }),
      ),
    ).rejects.toMatchObject({ code: "FISCAL_RESULT_UNKNOWN" });
    for (const code of ["FISCAL_DEVICE_LOCKED", "FISCAL_OFFLINE_48H_BLOCKED", "SHIFT_NOT_OPEN", "RECEIPT_SEQ_CONFLICT"]) {
      const err = await fail(new AgentError("http", code, { status: 409 })).catch((e: unknown) => e);
      expect(err).toMatchObject({ code, retrySame: false });
    }
  });

  it("a malformed answer of a signed receipt is 'result unknown' (resend, never re-sign)", () => {
    expect(() => parseFiscalResult({ ...RESULT, fiscal_sign: "12" })).toThrow(FiscalError);
    expect(() => parseFiscalResult({ ...RESULT, qr_url: "http://x" })).toThrow(/FISCAL_RESULT_UNKNOWN/);
  });

  it("shift, status, unsent, resend and refund routes", async () => {
    const request = vi.fn((_m: string, path: string) =>
      Promise.resolve(path.startsWith("/v1/fiscal/unsent") ? { items: [] } : RESULT),
    );
    const port = createLocalBridgeFiscalAdapter({ request } as never);
    await port.openShift(REGISTER, 214, "Dilnoza");
    await port.closeShift(REGISTER, 214);
    await port.getDeviceStatus(REGISTER);
    expect(await port.listUnsent(REGISTER)).toEqual([]);
    await port.resendUnsent(REGISTER);
    await expect(port.registerRefund({ ...receipt(), kind: "return" })).rejects.toMatchObject({
      code: "VALIDATION_ERROR",
    });
    await port.registerRefund({
      ...receipt(),
      kind: "return",
      refund_info: { fm_terminal_id: "ZZ1", fm_receipt_seq: 3, fiscal_sign: "111111111111" },
    });
    expect(request.mock.calls.map((c) => c[1])).toEqual([
      "/v1/fiscal/open-shift",
      "/v1/fiscal/close-shift",
      "/v1/fiscal/device-status?local_id=fm-1",
      "/v1/fiscal/unsent?local_id=fm-1",
      "/v1/fiscal/resend",
      "/v1/fiscal/refund",
    ]);
  });
});

describe("local fiscal readiness (21 §16, 24 §6.4)", () => {
  const agent = (fm: string | null, over: object = {}) => ({
    status: "online" as const,
    capabilities: { fiscal: { enabled: true } },
    fiscal_devices: fm === null ? [] : [{ local_id: "fm-1", fm_state: fm }],
    ...over,
  });
  it("online + ok → ready; locked states → locked; anything else → not connected", () => {
    expect(localFiscalReadiness(agent("ok"), "fm-1")).toEqual({ state: "ready", fmState: "ok" });
    expect(localFiscalReadiness(agent("ack_overdue"), "fm-1")).toMatchObject({ state: "locked" });
    expect(localFiscalReadiness(agent("unknown"), "fm-1")).toMatchObject({ reason: "fm_unknown" });
    expect(localFiscalReadiness(agent(null), "fm-1")).toMatchObject({ reason: "device_missing" });
    expect(localFiscalReadiness(agent("ok", { status: "offline" }), "fm-1")).toMatchObject({
      reason: "agent_offline",
    });
    expect(
      localFiscalReadiness(agent("ok", { capabilities: { fiscal: { enabled: false } } }), "fm-1"),
    ).toMatchObject({ reason: "capability_off" });
    expect(localFiscalReadiness(null, "fm-1")).toMatchObject({ state: "not_connected" });
  });
});

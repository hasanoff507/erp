import { afterEach, beforeEach, describe, expect, it } from "vitest";

import type { Money } from "@shared/lib/money";

import { enqueueEvent } from "../outbox/enqueue.ts";
import { posDb } from "../runtime.ts";
import { CASHIER, DEVICE, SHIFT_ID, setupOffline, teardownOffline } from "../testing/setup.ts";
import type { CustomerRow, OpenDebtDocRow, OutboxRow } from "../types.ts";
import {
  allocateOnDevice,
  createQuickCustomer,
  customerDebtView,
  customerDebts,
  enqueueDebtPayment,
  fiscalShares,
  localSaleDoc,
  overCreditLimit,
  unreflected,
} from "./debts.ts";
import { customers } from "./reference.ts";

const m = (v: string) => v as Money;
const CUSTOMER = "0190a000-0000-7000-8000-0000000000k1";
const SALE_A = "0190a000-0000-7000-8000-0000000000a1";
const SALE_B = "0190a000-0000-7000-8000-0000000000b2";

function saleDoc(id: string, amount: string, due: string, lineTotals: string[]): OpenDebtDocRow {
  return {
    doc_type: "sales",
    doc_id: id,
    number: `S-${id.slice(-2)}`,
    doc_date: "2026-10-01",
    due_date: due,
    open_amount: amount,
    lines: lineTotals.map((t, i) => ({
      sale_line_id: `${id.slice(0, -4)}${id.slice(-2)}${String(i + 10)}`,
      line_no: i + 1,
      product_id: `0190a000-0000-7000-8000-0000000000p${i}`,
      name: `Tovar ${i + 1}`,
      qty: "2.000",
      line_total: t,
      vat_rate: "12.00",
      settled_amount: "0.00",
      marking_code: null,
    })),
  };
}

function customerRow(patch: Partial<CustomerRow> = {}): CustomerRow {
  return {
    id: CUSTOMER,
    name: "Botir Aliyev",
    phone: "+998901234567",
    receivable_balance: "500000.00",
    credit_limit: "600000.00",
    open_debt_docs: [
      saleDoc(SALE_B, "200000.00", "2026-10-20", ["120000.00", "80000.00"]),
      saleDoc(SALE_A, "300000.00", "2026-10-10", ["300000.00"]),
    ],
    _pulled_at: "2026-10-14T03:00:00.000Z",
    tokens: ["botir", "aliyev"],
    ...patch,
  };
}

const event = (patch: Partial<OutboxRow>): OutboxRow =>
  ({
    seq: 1,
    client_event_id: "e1",
    device_id: DEVICE.deviceId,
    actor_user_id: CASHIER,
    type: "debt_payment.created",
    created_at: "2026-10-14T04:00:00.000Z",
    payload: {},
    status: "pending",
    error_code: null,
    message: null,
    retryable: null,
    warnings: [],
    server: null,
    attempts: 0,
    last_attempt_at: null,
    result_at: null,
    receipt_seq: 1,
    cash_register_id: DEVICE.cashRegisterId,
    shift_id: SHIFT_ID,
    fiscal: true,
    ofd_acked_at: null,
    ...patch,
  }) as OutboxRow;

describe("customer debt view — conservative overlay (16 §5, w-debts contract)", () => {
  it("QT-M08-16 (device half): 350 000 closes A (early due) and 50 000 of B; receipt lines total the payment", () => {
    const view = customerDebtView(customerRow(), []);
    expect(view.openDocs.map((d) => d.doc_id)).toEqual([SALE_B, SALE_A]);
    const result = allocateOnDevice(m("350000.00"), view);
    expect(result.allocations).toEqual([
      { target_doc_type: "sales", target_doc_id: SALE_A, amount: "300000.00" },
      { target_doc_type: "sales", target_doc_id: SALE_B, amount: "50000.00" },
    ]);
    expect(result.unallocated_amount).toBe("0.00");
    // B: ratio 50 000 / 200 000 → 30 000 + 20 000
    expect(result.fiscal_lines.map((l) => l.amount)).toEqual(["300000.00", "30000.00", "20000.00"]);
    expect(result.fiscal_lines[0]?.qty).toBe("2.000"); // A closed, nothing fiscalized before → full qty
  });

  it("QT-M08-17 (device half): an offline overpayment keeps the rest unallocated on one general line", () => {
    const view = customerDebtView(
      customerRow({
        receivable_balance: "300000.00",
        open_debt_docs: [saleDoc(SALE_A, "300000.00", "2026-10-10", ["300000.00"])],
      }),
      [],
    );
    const result = allocateOnDevice(m("350000.00"), view);
    expect(result.unallocated_amount).toBe("50000.00");
    const general = result.fiscal_lines.find((l) => l.sale_id === null);
    expect(general).toMatchObject({ amount: "50000.00", qty: "1.000", vat_rate: "0.00", vat_amount: "0.00" });
    expect(view.payable).toBe("300000.00");
  });

  it("a pending payment does not lower the balance, but takes its documents off; accepted lowers it", () => {
    const first = allocateOnDevice(m("350000.00"), customerDebtView(customerRow(), []));
    const payload = {
      counterparty_id: CUSTOMER,
      amount: "350000.00",
      allocations: first.allocations,
      fiscal_lines: first.fiscal_lines,
    };
    const pending = customerDebtView(customerRow(), [event({ payload })]);
    expect(pending.balance).toBe("500000.00"); // never below the server value before it is accepted
    expect(pending.pendingPayments).toBe("350000.00");
    expect(pending.openDocs).toHaveLength(1);
    expect(pending.openDocs[0]).toMatchObject({ doc_id: SALE_B, open_amount: "150000.00" });
    expect(pending.openDocs[0]?.lines?.map((l) => l.settled_amount)).toEqual(["30000.00", "20000.00"]);
    // the second offline payment allocates only what is left
    const second = allocateOnDevice(m("150000.00"), pending);
    expect(second.allocations).toEqual([
      { target_doc_type: "sales", target_doc_id: SALE_B, amount: "150000.00" },
    ]);
    expect(second.fiscal_lines.map((l) => l.amount)).toEqual(["90000.00", "60000.00"]);

    const acceptedAfterPull = customerDebtView(customerRow(), [
      event({ payload, status: "accepted", result_at: "2026-10-14T05:00:00.000Z" }),
    ]);
    expect(acceptedAfterPull.balance).toBe("150000.00");
    expect(acceptedAfterPull.syncedPayments).toBe("350000.00");
    // the next pull reflects it — never counted twice
    const pulledLater = customerDebtView(
      customerRow({ receivable_balance: "150000.00", _pulled_at: "2026-10-14T06:00:00.000Z" }),
      [event({ payload, status: "accepted", result_at: "2026-10-14T05:00:00.000Z" })],
    );
    expect(pulledLater.balance).toBe("150000.00");
  });

  it("a local debt sale raises the balance at once and becomes an open document; limit check uses it", () => {
    const sale = {
      id: "0190a000-0000-7000-8000-0000000000s9",
      counterparty_id: CUSTOMER,
      doc_date: "2026-10-14",
      temp_number: "D1-7",
      lines: [
        {
          id: "l1",
          product_id: "p1",
          qty: "1.000",
          line_total: "60000.00",
          vat_rate: "12.00",
          unit_code: "dona",
        },
        {
          id: "l2",
          product_id: "p2",
          qty: "1.000",
          line_total: "40000.00",
          vat_rate: "0.00",
          unit_code: "dona",
        },
      ],
      payments: [
        { method: "cash", amount: "50000.00" },
        { method: "debt", amount: "50000.00", due_date: "2026-10-21" },
      ],
    };
    const view = customerDebtView(customerRow(), [event({ type: "sale.created", payload: sale })]);
    expect(view.pendingDebt).toBe("50000.00");
    expect(view.balance).toBe("550000.00");
    expect(view.available).toBe("50000.00");
    expect(overCreditLimit(view, m("50000.00"))).toBe(false);
    expect(overCreditLimit(view, m("50000.01"))).toBe(true);
    const doc = view.openDocs.find((d) => d.local);
    expect(doc).toMatchObject({ open_amount: "50000.00", due_date: "2026-10-21", number: "D1-7" });
    // the mixed sale's first receipt fiscalized half of each line (backend fiscal_shares)
    expect(doc?.lines?.map((l) => l.settled_amount)).toEqual(["30000.00", "20000.00"]);
    // a non-retryable rejected sale never posted → ignored
    const rejected = customerDebtView(customerRow(), [
      event({ type: "sale.created", payload: sale, status: "rejected", retryable: false }),
    ]);
    expect(rejected.balance).toBe("500000.00");
  });

  it("fiscalShares puts the rounding rest on the largest (later on ties) line; unreflected rules", () => {
    expect(fiscalShares([m("100.00"), m("100.00"), m("100.00")], m("100.00"))).toEqual([
      "33.33",
      "33.33",
      "33.34",
    ]);
    expect(fiscalShares([m("10.00")], m("10.00"))).toEqual(["10.00"]);
    expect(localSaleDoc({ id: "x", payments: [{ method: "cash", amount: "1.00" }], lines: [] })).toBeNull();
    expect(unreflected({ status: "pending", retryable: null, result_at: null }, "2026")).toBe(true);
    expect(unreflected({ status: "rejected", retryable: true, result_at: "x" }, "2026")).toBe(true);
    expect(
      unreflected({ status: "accepted", retryable: null, result_at: "2026-10-14T05" }, "2026-10-14T06"),
    ).toBe(false);
  });
});

describe("quick customer + debt payment enqueue (18 §11.1, §12.2)", () => {
  beforeEach(async () => {
    await setupOffline();
  });
  afterEach(teardownOffline);

  it("QT-M08-08 (device half): «+ Yangi mijoz» writes counterparty.created and a searchable local row", async () => {
    const row = await createQuickCustomer(
      { name: "  Malika Yusupova ", phone: "+998977114022" },
      { actorUserId: CASHIER },
    );
    const events = await posDb().outbox.toArray();
    expect(events).toHaveLength(1);
    expect(events[0]?.type).toBe("counterparty.created");
    expect(events[0]?.payload).toEqual({
      id: row.id,
      kind: "person",
      name: "Malika Yusupova",
      phone: "+998977114022",
      notify_consent: false,
    });
    expect((await customers.search("malika")).map((c) => c.id)).toEqual([row.id]);
    expect((await customers.search("711 40 22")).length).toBe(0);
    expect((await customers.search("977114022")).map((c) => c.id)).toEqual([row.id]);
    const view = await customerDebts.view(row.id);
    expect(view).toMatchObject({ local: true, balance: "0.00", creditLimit: null });
  });

  it("debt payment gets the next receipt_seq of the shift and shows up in the debtor list", async () => {
    await posDb().customers.put(customerRow());
    await enqueueEvent(
      "sale.created",
      { id: "s0", shift_id: SHIFT_ID, payments: [{ method: "cash", amount: "1.00" }], lines: [] },
      {
        actorUserId: CASHIER,
        receiptSeq: { cashRegisterId: DEVICE.cashRegisterId ?? "", shiftId: SHIFT_ID },
      },
    );
    const view = await customerDebts.view(CUSTOMER);
    if (!view) throw new Error("view");
    const allocation = allocateOnDevice(m("100000.00"), view);
    const res = await enqueueDebtPayment(
      {
        counterpartyId: CUSTOMER,
        branchId: DEVICE.branchId,
        cashRegisterId: DEVICE.cashRegisterId ?? "",
        shiftId: SHIFT_ID,
        amount: m("100000.00"),
        method: "cash",
        isOffline: true,
        offlineSince: "2026-10-14T03:30:00.000Z",
        promiseDate: "2026-10-30",
        comment: " ",
        allocation,
      },
      { actorUserId: CASHIER },
    );
    expect(res.receiptSeq).toBe(2);
    expect(res.payload).toMatchObject({
      counterparty_id: CUSTOMER,
      receipt_seq: 2,
      is_offline: true,
      offline_since: "2026-10-14T03:30:00.000Z",
      method: "cash",
      amount: "100000.00",
      promise_date: "2026-10-30",
      comment: null,
      fiscal_result: null,
    });
    expect(res.payload).not.toHaveProperty("card_entry_mode");
    const row = await posDb().outbox.where("client_event_id").equals(res.clientEventId).first();
    expect(row?.fiscal).toBe(true);
    const [debtor] = await customerDebts.debtors();
    expect(debtor?.pendingPayments).toBe("100000.00");
    expect(debtor?.balance).toBe("500000.00");
    expect(debtor?.payable).toBe("400000.00");
  });
});

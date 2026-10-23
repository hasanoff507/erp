/** BO-21 ④ opening debts (US-M08-07, 18 §12.4): paste parsing, row rules, create → post per row. */
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@shared/api";

import {
  newRow,
  normalizeAmount,
  normalizeDate,
  parsePasted,
  submitRows,
  toOpeningBody,
  validateRow,
  type OpeningDebtsDeps,
} from "./index.ts";

describe("opening debts table", () => {
  it("parses an Excel paste (tab separated, header skipped, spaces / commas in amounts, dd.mm.yyyy)", () => {
    const rows = parsePasted(
      "Ism\tTelefon\tSumma\nAliyev Botir\t+998 90 123 45 67\t350 000\t01.11.2026\nKarimova Malika\t97 711 40 22\t1 240 000,50\n",
    );
    expect(rows.map((r) => [r.name, r.phone, r.amount, r.dueDate])).toEqual([
      ["Aliyev Botir", "901234567", "350000.00", "2026-11-01"],
      ["Karimova Malika", "977114022", "1240000.50", ""],
    ]);
    expect(normalizeAmount("0")).toBe("");
    expect(normalizeAmount("12.500,00")).toBe("12500.00");
    expect(normalizeAmount("abc")).toBe("");
    expect(normalizeDate("2026-12-31")).toBe("2026-12-31");
    expect(normalizeDate("31/12/26")).toBe("");
  });

  it("test_web04_dot_thousands_paste", () => {
    expect(normalizeAmount("350.000")).toBe("350000.00");
    expect(normalizeAmount("1.500.000")).toBe("1500000.00");
    expect(normalizeAmount("350.5")).toBe("350.50");
    expect(normalizeAmount("350.000,50")).toBe("350000.50");
    expect(normalizeAmount("350.00")).toBe("350.00");
  });

  it("a customer row needs name, a full phone and an amount; a supplier row may omit the phone", () => {
    expect(validateRow(newRow({ name: "A", phone: "901234567", amount: "1.00" }), "receivable")).toEqual({});
    expect(validateRow(newRow({ name: " ", phone: "90", amount: "" }), "receivable")).toEqual({
      name: "validation.required",
      phone: "validation.phone_uz",
      amount: "validation.required",
    });
    expect(validateRow(newRow({ name: "Ta'minot", amount: "5.00" }), "payable")).toEqual({});
    expect(
      toOpeningBody(newRow({ name: " Ali ", phone: "901234567", amount: "350000.00" }), "receivable"),
    ).toEqual({
      counterparty: { name: "Ali", phone: "+998901234567", kind: "person" },
      amount: "350000.00",
      direction: "receivable",
      due_date: null,
    });
  });

  it("creates and posts each new row once; a failed post cancels its draft; go-live missing stops the run", async () => {
    const a = newRow({ name: "A", phone: "901234567", amount: "100.00" });
    const b = newRow({ name: "B", phone: "901234568", amount: "200.00" });
    const c = newRow({ name: "C", phone: "901234569", amount: "300.00" });
    let n = 0;
    const deps: OpeningDebtsDeps = {
      create: vi.fn(() => {
        n += 1;
        return Promise.resolve({ id: `d${n}` } as never);
      }),
      post: vi.fn((id: string) =>
        id === "d2"
          ? Promise.reject(
              new ApiError({
                status: 422,
                code: "VALIDATION_ERROR",
                messageKey: "validation.go_live_date_missing",
                params: {},
                details: [],
              }),
            )
          : Promise.resolve({ id } as never),
      ),
      cancel: vi.fn(() => Promise.resolve()),
    };
    const out = await submitRows([a, b, c], "receivable", new Set([]), deps);
    expect(out[a.key]).toEqual({ ok: true, id: "d1" });
    expect(out[b.key]?.ok).toBe(false);
    expect(out[c.key]).toBeUndefined(); // stopped: every row would fail the same way
    expect(deps.cancel).toHaveBeenCalledWith("d2");
    // the saved row is never sent again
    const again = await submitRows([a], "receivable", new Set([a.key]), deps);
    expect(again).toEqual({});
  });
});

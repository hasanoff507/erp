/**
 * POS-14 (07; 18 §13.1; US-M16-01; QT-M16-01, QT-M16-02, QT-PERM-05) and POS-15 (07; US-M16-02;
 * QT-M01-06/-07): reason ↔ direction, withdrawal limit, payload; counting and the variance note rule.
 */
import { describe, expect, it } from "vitest";

import type { Money } from "@shared/lib/money";

import { cashMovementPayload, digitsToMoney, validateMovement, withdrawalNeedsApproval } from "./index.ts";

const cashier = { roleCodes: ["cashier"] };

describe("POS-14 cash movement", () => {
  it("test_qt_m16_01: 40 000 «Boshqa» withdrawal under the 50 000 limit passes without approval", () => {
    expect(
      validateMovement({ direction: "out", digits: "40000", reason: "other", comment: "Suv" }, true),
    ).toEqual([]);
    expect(withdrawalNeedsApproval(cashier, "50000.0000", "40000.00")).toBe(false);
    expect(
      cashMovementPayload({
        id: "m-1",
        cashRegisterId: "cr-1",
        shiftId: "s-1",
        direction: "out",
        reason: "other",
        amount: "40000.00" as Money,
        comment: " Suv ",
        approval: null,
      }),
    ).toEqual({
      id: "m-1",
      cash_register_id: "cr-1",
      shift_id: "s-1",
      direction: "out",
      reason: "other",
      account: null,
      counterparty_id: null,
      employee_id: null,
      amount: "40000.00",
      comment: "Suv",
      approval: null,
    });
  });

  it("test_qt_perm_05 / test_qt_m16_02: 50 000.00 passes, 50 001.00 needs cash_withdrawal_over_limit", () => {
    expect(withdrawalNeedsApproval(cashier, "50000.0000", "50000.00")).toBe(false);
    expect(withdrawalNeedsApproval(cashier, "50000.0000", "50001.00")).toBe(true);
    expect(withdrawalNeedsApproval(cashier, undefined, "1.00")).toBe(true);
    expect(withdrawalNeedsApproval({ roleCodes: ["owner"] }, undefined, "9999999.00")).toBe(false);
  });

  it("validation: amount > 0, reason pair, comment for «other», founder for an LLC owner withdrawal", () => {
    expect(validateMovement({ direction: "out", digits: "", reason: null, comment: "" }, true)).toEqual([
      "amount",
      "reason",
    ]);
    expect(
      validateMovement({ direction: "in", digits: "100", reason: "collection", comment: "" }, true),
    ).toEqual(["reason"]);
    expect(
      validateMovement({ direction: "out", digits: "100", reason: "other", comment: " " }, true),
    ).toEqual(["comment"]);
    expect(
      validateMovement({ direction: "out", digits: "100", reason: "owner_withdrawal", comment: "" }, false),
    ).toEqual(["founder"]);
    expect(
      validateMovement({ direction: "out", digits: "100", reason: "owner_withdrawal", comment: "" }, true),
    ).toEqual([]);
    expect(digitsToMoney("150000")).toBe("150000.00");
    expect(digitsToMoney("")).toBeNull();
  });
});

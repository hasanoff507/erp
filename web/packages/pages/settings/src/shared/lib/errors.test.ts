import { beforeAll, describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";
import { initI18n } from "@shared/i18n";

import { errorText, fieldErrorMessage, messageText, splitFieldErrors } from "./errors.ts";
import { isOwnerRole, limitUnitOf, systemRoleKey } from "./roles.ts";

beforeAll(() => {
  initI18n("uz");
});

describe("server message keys → text", () => {
  it("server keys resolve in common, never the raw key", () => {
    expect(messageText("validation.cannot_block_self")).toBe("O'zingizni bloklab bo'lmaydi");
    expect(messageText("validation.phone_already_member")).toBe("Bu telefon raqami allaqachon ro'yxatda");
    expect(messageText("validation.something_new")).toBe(messageText("validation.invalid_format"));
    expect(messageText("errors.something_new")).toBe(messageText("errors.internal_error"));
  });

  it("form fields get keys FormField can translate, or ready text", () => {
    expect(fieldErrorMessage("validation.required")).toBe("validation.required");
    // server keys now live in `common` (FormField translates them), so they pass through as keys
    expect(fieldErrorMessage("validation.owner_role_not_assignable")).toBe(
      "validation.owner_role_not_assignable",
    );
  });

  it("details are split between form fields (with a server→form map) and a banner", () => {
    const error = new ApiError({
      status: 422,
      code: "VALIDATION_ERROR",
      messageKey: "errors.validation",
      details: [
        { field: "phone", messageKey: "validation.phone_already_member" },
        { field: "role_ids", messageKey: "validation.owner_role_not_assignable" },
        { field: "status", messageKey: "validation.tenant_requires_active_owner" },
      ],
    });
    const { fieldErrors, other } = splitFieldErrors(error, ["phone", "roleIds"], { role_ids: "roleIds" });
    expect(fieldErrors.map((f) => f.field)).toEqual(["phone", "roleIds"]);
    expect(other).toEqual(["Do'konda kamida bitta faol Egasi qolishi kerak"]);
    expect(errorText(error)).toBe("Bu telefon raqami allaqachon ro'yxatda");
    expect(
      errorText(
        new ApiError({
          status: 409,
          code: "WAREHOUSE_ACCOUNT_LOCKED",
          messageKey: "errors.warehouse_account_locked",
        }),
      ),
    ).toMatch(/^Omborda harakat bor/);
  });
});

describe("roles helpers", () => {
  it("recognises system roles by system_code (not by name) and limit units by code (15 §2.1)", () => {
    expect(systemRoleKey({ id: "1", name: "Kassir", is_system: true, system_code: "cashier" })).toBe(
      "cashier",
    );
    expect(systemRoleKey({ id: "2", name: "Kassir", is_system: false, system_code: null })).toBeNull();
    // a renamed/translated system role is still recognised; a custom role named "Egasi" is not
    expect(isOwnerRole({ id: "3", name: "Владелец", is_system: true, system_code: "owner" })).toBe(true);
    expect(isOwnerRole({ id: "4", name: "Egasi", is_system: false, system_code: null })).toBe(false);
    expect(systemRoleKey({ id: "5", name: "X", is_system: true, system_code: "unknown" })).toBeNull();
    expect(limitUnitOf("discount.give")).toBe("percent");
    expect(limitUnitOf("prices.approve")).toBe("percent");
    expect(limitUnitOf("returns.approve")).toBe("amount");
    expect(limitUnitOf("cash.withdraw")).toBe("amount");
  });
});

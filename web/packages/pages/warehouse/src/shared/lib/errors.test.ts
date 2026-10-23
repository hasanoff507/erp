import { beforeAll, describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";
import { changeLanguage, initI18n } from "@shared/i18n";

import { errorText } from "./errors.ts";

function refused(reason: string): ApiError {
  return new ApiError({
    status: 409,
    code: "DOC_INVALID_STATE",
    messageKey: "errors.doc_invalid_state",
    params: { reason },
  });
}

beforeAll(async () => {
  await initI18n("uz").changeLanguage("uz");
});

describe("warehouse errorText — params.reason texts", () => {
  it("test_web05_reason_texts", async () => {
    expect(errorText(refused("supplier_payment_allocated"))).toBe(
      "Kirimga yetkazib beruvchiga to'lov tushgan — avval to'lovni bekor qiling",
    );
    expect(errorText(refused("shift_closed"))).toBe("Smena yopilgan — naqd hujjatni bekor qilib bo'lmaydi");
    await changeLanguage("ru");
    expect(errorText(refused("supplier_payment_allocated"))).toBe(
      "На поступление легла оплата поставщику — сначала отмените оплату",
    );
    expect(errorText(refused("shift_closed"))).toBe("Смена закрыта — кассовый документ отменить нельзя");
    await changeLanguage("uz");
  });
});

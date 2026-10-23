import { beforeAll, describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";
import { changeLanguage, initI18n, serverErrorText } from "@shared/i18n";

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

describe("finance errorText — params.reason texts", () => {
  it("test_web05_reason_texts", async () => {
    expect(errorText(refused("shift_closed"))).toBe("Smena yopilgan — naqd hujjatni bekor qilib bo'lmaydi");
    await changeLanguage("ru");
    expect(errorText(refused("shift_closed"))).toBe("Смена закрыта — кассовый документ отменить нельзя");
    await changeLanguage("uz");
    // unknown reasons fall back to the generic server text
    const other = refused("something_else");
    expect(errorText(other)).toBe(serverErrorText(other));
  });
});

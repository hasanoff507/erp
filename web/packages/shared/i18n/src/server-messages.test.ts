import { beforeAll, describe, expect, it } from "vitest";

import { i18next, initI18n } from "./index.ts";
import { hasServerMessage, serverErrorText, translateServerMessage } from "./server-messages.ts";

beforeAll(async () => {
  await initI18n("uz").changeLanguage("uz");
});

describe("translateServerMessage — one translator for every page (08 §11)", () => {
  it("resolves in common, decodes `key?param=value` and never shows the raw key", () => {
    expect(translateServerMessage("validation.phone_already_member")).toBe(
      "Bu telefon raqami allaqachon ro'yxatda",
    );
    expect(translateServerMessage("validation.min_length?min=3")).toBe("Kamida 3 ta belgi kiriting");
    expect(translateServerMessage("validation.brand_new")).toBe("Format mos kelmadi — tekshirib ko'ring");
    expect(translateServerMessage("errors.brand_new")).toBe("Xatolik yuz berdi. Qayta urinib ko'ring");
    expect(translateServerMessage("validation.brand_new", {}, { fallback: "errors.internal_error" })).toBe(
      "Xatolik yuz berdi. Qayta urinib ko'ring",
    );
  });

  it("consults extra namespaces after common", () => {
    i18next.addResource("uz", "settings", "legacy.validation.only_here", "Faqat shu yerda");
    expect(hasServerMessage("validation.only_here")).toBe(false);
    expect(hasServerMessage("validation.only_here", ["settings:legacy"])).toBe(true);
    expect(translateServerMessage("validation.only_here", {}, { namespaces: ["settings:legacy"] })).toBe(
      "Faqat shu yerda",
    );
  });

  it("translates the cross-tenant credential refusal in both languages", async () => {
    expect(translateServerMessage("validation.credential_shared_across_tenants")).toMatch(
      /^Bu xodim boshqa do'konda ham ishlaydi/,
    );
    await i18next.changeLanguage("ru");
    expect(translateServerMessage("validation.credential_shared_across_tenants")).toMatch(
      /^Этот сотрудник работает и в другом магазине/,
    );
    await i18next.changeLanguage("uz");
  });
});

describe("serverErrorText", () => {
  it("a generic VALIDATION_ERROR shows its first detail; a specific top key wins", () => {
    expect(
      serverErrorText({
        code: "VALIDATION_ERROR",
        messageKey: "errors.validation",
        details: [{ messageKey: "validation.phone_taken" }],
      }),
    ).toBe("Bu raqam allaqachon ro'yxatdan o'tgan");
    expect(
      serverErrorText({
        code: "VALIDATION_ERROR",
        messageKey: "validation.credential_shared_across_tenants",
        details: [{ messageKey: "validation.invalid" }],
      }),
    ).toMatch(/^Bu xodim boshqa do'konda/);
  });

  it("RATE_LIMITED with retry_after_s says how many minutes to wait", () => {
    expect(
      serverErrorText({
        code: "RATE_LIMITED",
        messageKey: "errors.rate_limited",
        params: { retry_after_s: 90 },
      }),
    ).toBe("Juda ko'p urinish. 2 daqiqadan keyin qayta urinib ko'ring");
  });
});

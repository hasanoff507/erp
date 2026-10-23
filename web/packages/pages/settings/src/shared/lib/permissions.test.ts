import { beforeAll, describe, expect, it } from "vitest";

import { i18next, initI18n } from "@shared/i18n";

import { moduleLabel, permissionLabel, primaryModule } from "./permissions.ts";

beforeAll(async () => {
  await initI18n("uz").changeLanguage("uz");
});

describe("BO-11 permission labels (WEB-06)", () => {
  it("translates codes and module names in the UI language", async () => {
    const item = { code: "sales.create", description: "Chek yaratish/yakunlash" };
    expect(permissionLabel(item)).toBe("Chek yaratish/yakunlash");
    expect(moduleLabel("M01")).toBe("Kassa (POS)");
    await i18next.changeLanguage("ru");
    expect(permissionLabel(item)).toBe("Создание/закрытие чека");
    expect(moduleLabel("M07, M10")).toBe("Закупки · НДС");
    await i18next.changeLanguage("uz");
  });

  it("falls back to the server description / raw module code for unknown codes", () => {
    expect(permissionLabel({ code: "future.thing", description: "Server matni" })).toBe("Server matni");
    expect(moduleLabel("M42")).toBe("M42");
  });

  it("groups a multi-module permission under its primary module", () => {
    expect(primaryModule("M07, M10")).toBe("M07");
    expect(primaryModule("M17/ADM-01")).toBe("M17");
    expect(primaryModule("AI-01")).toBe("AI-01");
  });
});

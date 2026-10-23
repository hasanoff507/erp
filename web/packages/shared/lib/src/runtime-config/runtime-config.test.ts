import { afterEach, describe, expect, it, vi } from "vitest";

import {
  type ErpRuntimeConfigInput,
  getRuntimeConfig,
  googleStartUrl,
  parseHttpsUrl,
  parsePhone,
  parseRuntimeConfig,
  parseTelegramUsername,
  RUNTIME_CONFIG_DEFAULTS,
  supportLinks,
  telegramBotLink,
} from "./index.ts";

/** The page's `window` as /config.js leaves it (node test environment: a stub). */
const setConfig = (config?: ErpRuntimeConfigInput) => vi.stubGlobal("window", { __ERP_CONFIG__: config });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("runtime config — 24 §3", () => {
  it("falls back to safe defaults when /config.js sets nothing", () => {
    expect(getRuntimeConfig()).toEqual(RUNTIME_CONFIG_DEFAULTS); // no window (SSR / node)
    setConfig(undefined);
    expect(getRuntimeConfig()).toEqual(RUNTIME_CONFIG_DEFAULTS);
    expect(telegramBotLink()).toBeNull();
    expect(supportLinks()).toEqual({ telegram: null, phone: null, web: null });
  });

  it("reads and normalises the window config", () => {
    setConfig({
      environment: "production",
      agentPort: 47111,
      telegramBot: "https://t.me/erp_uz_bot",
      supportTelegram: "@erp_yordam",
      supportPhone: "tel:+998 71 200-00-00",
      supportUrl: "https://help.example.uz/start",
    });
    expect(getRuntimeConfig()).toMatchObject({
      environment: "production",
      agentPort: 47111,
      telegramBot: "erp_uz_bot",
      supportTelegram: "erp_yordam",
      supportPhone: "+998712000000",
      supportUrl: "https://help.example.uz/start",
    });
    expect(telegramBotLink()).toEqual({ label: "@erp_uz_bot", href: "https://t.me/erp_uz_bot" });
    expect(supportLinks()).toEqual({
      telegram: { label: "@erp_yordam", href: "https://t.me/erp_yordam" },
      phone: { label: "+998 71 200 00 00", href: "tel:+998712000000" },
      web: { label: "help.example.uz", href: "https://help.example.uz/start" },
    });
  });

  it("invalid values never become links — each falls back to its default", () => {
    const config = parseRuntimeConfig({
      environment: "prod",
      agentPort: 70000,
      apiBaseUrl: 42,
      telegramBot: "javascript:alert(1)",
      supportTelegram: "https://evil.example/erp_yordam",
      supportPhone: "call me",
      supportUrl: "http://help.example.uz",
      googleEnabled: "true",
    });
    expect(config).toEqual(RUNTIME_CONFIG_DEFAULTS);
  });

  it.each([
    ["erp_uz_bot", "erp_uz_bot"],
    ["@erp_uz_bot", "erp_uz_bot"],
    ["https://t.me/erp_uz_bot", "erp_uz_bot"],
    ["https://t.me/erp_uz_bot/", "erp_uz_bot"],
    ["  erp_uz_bot ", "erp_uz_bot"],
    ["http://t.me/erp_uz_bot", null],
    ["https://t.me.evil.example/erp_uz_bot", null],
    ["https://t.me/erp_uz_bot?start=x", null],
    ["bot", null],
    ["1erp_bot", null],
    ["erp-bot-name", null],
    [null, null],
    [123, null],
  ])("parseTelegramUsername(%j) → %j", (input, expected) => {
    expect(parseTelegramUsername(input)).toBe(expected);
  });

  it.each([
    ["+998712000000", "+998712000000"],
    ["tel:+998712000000", "+998712000000"],
    ["+998 (71) 200-00-00", "+998712000000"],
    ["998712000000", null],
    ["+0123456789", null],
    ["tel:+99871200000000000", null],
    ["javascript:alert(1)", null],
  ])("parsePhone(%j) → %j", (input, expected) => {
    expect(parsePhone(input)).toBe(expected);
  });

  it.each([
    ["https://help.example.uz", "https://help.example.uz/"],
    ["http://help.example.uz", null],
    ["javascript:alert(1)", null],
    ["https://user:pw@help.example.uz", null],
    ["/relative", null],
    ["not a url", null],
  ])("parseHttpsUrl(%j) → %j", (input, expected) => {
    expect(parseHttpsUrl(input)).toBe(expected);
  });

  it("non-Uzbek support numbers keep the E.164 label", () => {
    const links = supportLinks(parseRuntimeConfig({ supportPhone: "+74951234567" }));
    expect(links.phone).toEqual({ label: "+74951234567", href: "tel:+74951234567" });
  });

  it("Google start URL only when googleEnabled === true (14 §2.2)", () => {
    expect(googleStartUrl({ returnTo: "/" }, RUNTIME_CONFIG_DEFAULTS)).toBeNull();
    const on = parseRuntimeConfig({ googleEnabled: true });
    expect(googleStartUrl({ returnTo: "/app/debts" }, on)).toBe(
      "/auth/google/start?return_to=%2Fapp%2Fdebts",
    );
    expect(googleStartUrl({ returnTo: "/", tenantId: "t" }, { ...on, apiBaseUrl: "https://api" })).toBe(
      "https://api/auth/google/start?return_to=%2F&tenant_id=t",
    );
    expect(googleStartUrl({}, on)).toBe("/auth/google/start");
  });
});

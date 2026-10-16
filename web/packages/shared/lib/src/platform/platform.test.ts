import { afterEach, describe, expect, it, vi } from "vitest";

import { detectPlatform, IOS_INSTALL_PATH, isIosNotInstalled } from "./index.ts";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("UX-INSTALL platform rule (24 §6.2)", () => {
  it("iPadOS desktop UA with touch counts as iOS", () => {
    expect(
      detectPlatform({ userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15)", maxTouchPoints: 5 }),
    ).toBe("ios");
    expect(
      detectPlatform({ userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15)", maxTouchPoints: 0 }),
    ).toBeNull();
  });

  it("an iOS Safari tab is blocked, the installed app is not", () => {
    const iphone = { userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)", maxTouchPoints: 5 };
    const matchMedia = () => ({ matches: false });
    vi.stubGlobal("navigator", { ...iphone, standalone: false });
    vi.stubGlobal("window", { matchMedia });
    expect(isIosNotInstalled()).toBe(true);
    vi.stubGlobal("navigator", { ...iphone, standalone: true });
    expect(isIosNotInstalled()).toBe(false);
    expect(IOS_INSTALL_PATH).toBe("/install?platform=ios");
  });
});

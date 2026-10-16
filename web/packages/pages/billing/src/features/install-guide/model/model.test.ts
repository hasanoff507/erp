import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { detectPlatform } from "../lib/platform.ts";

import {
  $installed,
  $installOutcome,
  $installPrompt,
  $platform,
  appInstalled,
  detectPlatformFx,
  guideMounted,
  installClicked,
  installPromptCaptured,
  platformSelected,
  promptInstallFx,
  resolvePlatform,
  trackFx,
  type BeforeInstallPromptEvent,
} from "./index.ts";

const UA = {
  iphone: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Safari",
  ipad13: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.0 Safari",
  android: "Mozilla/5.0 (Linux; Android 14; SM-A145F) AppleWebKit/537.36 Chrome/130.0 Mobile Safari",
  windows: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari",
  linux: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0 Safari",
};

describe("UX-INSTALL platform detection", () => {
  it("detects iOS (incl. iPadOS desktop UA with touch), Android and Windows", () => {
    expect(detectPlatform({ userAgent: UA.iphone, maxTouchPoints: 5 })).toBe("ios");
    expect(detectPlatform({ userAgent: UA.ipad13, maxTouchPoints: 5 })).toBe("ios");
    expect(detectPlatform({ userAgent: UA.ipad13, maxTouchPoints: 0 })).toBeNull();
    expect(detectPlatform({ userAgent: UA.android, maxTouchPoints: 5 })).toBe("android");
    expect(detectPlatform({ userAgent: UA.windows, maxTouchPoints: 0 })).toBe("windows");
    expect(detectPlatform({ userAgent: UA.linux, maxTouchPoints: 0 })).toBeNull();
  });

  it("?platform= wins, unknown values fall back to detection, desktop → Windows", () => {
    expect(resolvePlatform("ios", "windows")).toBe("ios");
    expect(resolvePlatform("mac", "android")).toBe("android");
    expect(resolvePlatform(null, null)).toBe("windows");
  });
});

describe("UX-INSTALL model", () => {
  it("mount picks the platform; manual switch; analytics", async () => {
    const tracked: string[] = [];
    const scope = fork({
      handlers: [
        [
          detectPlatformFx,
          (requested: string | null) => ({
            platform: resolvePlatform(requested, "android"),
            detected: "android" as const,
            standalone: false,
          }),
        ],
        [trackFx, ({ event }: { event: string }) => void tracked.push(event)],
      ],
    });
    await allSettled(guideMounted, { scope, params: { requested: "ios", embedded: false } });
    expect(scope.getState($platform)).toBe("ios");
    await allSettled(platformSelected, { scope, params: "windows" });
    expect(scope.getState($platform)).toBe("windows");
    expect(tracked).toEqual(["install_guide_viewed"]);
  });

  it("install button uses the captured prompt once; appinstalled is tracked", async () => {
    const tracked: string[] = [];
    const scope = fork({
      handlers: [
        [promptInstallFx, () => Promise.resolve("accepted" as const)],
        [trackFx, ({ event }: { event: string }) => void tracked.push(event)],
      ],
    });
    const prompt = { type: "beforeinstallprompt" } as unknown as BeforeInstallPromptEvent;
    await allSettled(installPromptCaptured, { scope, params: prompt });
    expect(scope.getState($installPrompt)).toBe(prompt);
    await allSettled(installClicked, { scope });
    expect(scope.getState($installOutcome)).toBe("accepted");
    expect(scope.getState($installPrompt)).toBeNull();
    await allSettled(appInstalled, { scope });
    expect(scope.getState($installed)).toBe(true);
    expect(tracked).toEqual(["pwa_installed"]);
  });
});

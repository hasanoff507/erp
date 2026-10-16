/**
 * UX-INSTALL model: chosen platform (auto-detected, `?platform=` override, manual switch), the
 * Chrome/Android `beforeinstallprompt` event (captured from app start — it fires once, usually before
 * the guide is open) and the `appinstalled` analytics event (07 «pwa_installed»).
 */
import { createEffect, createEvent, createStore, sample } from "effector";

import { track, type AnalyticsEvent } from "#/shared/lib/analytics.ts";

import { currentPlatform, isInstallPlatform, isStandalone, type InstallPlatform } from "../lib/platform.ts";

/** Chrome's install prompt event (not in lib.dom). */
export interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
}

export type InstallOutcome = "accepted" | "dismissed";

export interface PlatformInfo {
  /** Section shown: `?platform=` when valid, else the detected one, else Windows (desktop). */
  platform: InstallPlatform;
  detected: InstallPlatform | null;
  standalone: boolean;
}

export const guideMounted = createEvent<{ requested: string | null; embedded: boolean }>();
export const platformSelected = createEvent<InstallPlatform>();
export const installPromptCaptured = createEvent<BeforeInstallPromptEvent>();
export const installClicked = createEvent();
export const appInstalled = createEvent();

export function resolvePlatform(requested: string | null, detected: InstallPlatform | null): InstallPlatform {
  if (isInstallPlatform(requested)) return requested;
  return detected ?? "windows";
}

export const detectPlatformFx = createEffect((requested: string | null): PlatformInfo => {
  const detected = currentPlatform();
  return { platform: resolvePlatform(requested, detected), detected, standalone: isStandalone() };
});

export const promptInstallFx = createEffect(
  async (event: BeforeInstallPromptEvent): Promise<InstallOutcome> => {
    await event.prompt();
    const choice = await event.userChoice;
    return choice.outcome;
  },
);

export const trackFx = createEffect(
  ({ event, props }: { event: AnalyticsEvent; props?: Record<string, string> }) => track(event, props),
);

export const $platform = createStore<InstallPlatform>("windows");
export const $detected = createStore<InstallPlatform | null>(null);
export const $standalone = createStore(false);
export const $installPrompt = createStore<BeforeInstallPromptEvent | null>(null);
export const $installOutcome = createStore<InstallOutcome | null>(null);
export const $installed = createStore(false);

sample({ clock: guideMounted, fn: ({ requested }) => requested, target: detectPlatformFx });
sample({ clock: detectPlatformFx.doneData, fn: (info) => info.platform, target: $platform });
sample({ clock: detectPlatformFx.doneData, fn: (info) => info.detected, target: $detected });
sample({ clock: detectPlatformFx.doneData, fn: (info) => info.standalone, target: $standalone });
sample({
  clock: guideMounted,
  fn: ({ requested, embedded }) => ({
    event: "install_guide_viewed" as const,
    props: { platform: requested ?? "auto", embedded: embedded ? "true" : "false" },
  }),
  target: trackFx,
});

sample({ clock: platformSelected, target: $platform });

sample({ clock: installPromptCaptured, target: $installPrompt });
sample({
  clock: installClicked,
  source: $installPrompt,
  filter: (event): event is BeforeInstallPromptEvent => event !== null,
  target: promptInstallFx,
});
sample({ clock: promptInstallFx.doneData, target: $installOutcome });
// A captured prompt can be shown only once.
sample({ clock: promptInstallFx.finally, fn: () => null, target: $installPrompt });

$installed.on(appInstalled, () => true);
sample({ clock: appInstalled, fn: () => null, target: $installPrompt });
sample({ clock: appInstalled, fn: () => ({ event: "pwa_installed" as const }), target: trackFx });

let capturing = false;

/**
 * Called once at app start (shell router): keeps Chrome's install prompt for the «O'rnatish» button
 * and reports `appinstalled`. Safe to call repeatedly.
 */
export function startInstallPromptCapture(): void {
  if (capturing || typeof window === "undefined") return;
  capturing = true;
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPromptCaptured(event as BeforeInstallPromptEvent);
  });
  window.addEventListener("appinstalled", () => appInstalled());
}

/**
 * UX-INSTALL platform detection (07, 24 §6.2) — shared by the shell (iOS gate) and @pages/billing
 * (install guide), so the shell does not import a page package for it. iOS must run the installed PWA (Home Screen web apps
 * are exempt from Safari ITP's 7-day storage wipe, 24 §6.2) — `navigator.standalone` is the iOS
 * flag, `display-mode: standalone` the standard one. iPadOS 13+ reports a desktop Mac UA, so a Mac
 * UA with touch points counts as iOS.
 */
export type InstallPlatform = "ios" | "android" | "windows";

export const INSTALL_PLATFORMS: readonly InstallPlatform[] = ["ios", "android", "windows"];

export interface PlatformProbe {
  userAgent: string;
  maxTouchPoints: number;
}

export function detectPlatform({ userAgent, maxTouchPoints }: PlatformProbe): InstallPlatform | null {
  const ua = userAgent.toLowerCase();
  if (/iphone|ipad|ipod/.test(ua)) return "ios";
  if (ua.includes("macintosh") && maxTouchPoints > 1) return "ios";
  if (ua.includes("android")) return "android";
  if (ua.includes("windows")) return "windows";
  return null;
}

export function isInstallPlatform(value: string | null | undefined): value is InstallPlatform {
  return value === "ios" || value === "android" || value === "windows";
}

function browserProbe(): PlatformProbe | null {
  if (typeof navigator === "undefined") return null;
  return { userAgent: navigator.userAgent, maxTouchPoints: navigator.maxTouchPoints || 0 };
}

export function currentPlatform(): InstallPlatform | null {
  const probe = browserProbe();
  return probe ? detectPlatform(probe) : null;
}

/** Running as an installed app (iOS Home Screen web app or any standalone PWA window). */
export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  const nav = navigator as Navigator & { standalone?: boolean };
  if (nav.standalone === true) return true;
  return typeof window.matchMedia === "function" && window.matchMedia("(display-mode: standalone)").matches;
}

/** UX-INSTALL (b): iOS Safari tab (not installed) — POS is blocked, back-office shows a banner. */
export function isIosNotInstalled(): boolean {
  return currentPlatform() === "ios" && !isStandalone();
}

export const IOS_INSTALL_PATH = "/install?platform=ios";

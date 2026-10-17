/**
 * Trusted monotonic time (16 §8, 14 §17.2 p.5): `max(local clock, last server time seen)` never goes
 * backwards, so moving the device clock back does not shrink the 48 h fiscal timer.
 */
import { getMeta, META, setMeta } from "../db/meta.ts";
import { now } from "../runtime.ts";

let cachedMax = 0;
let lastSkewMs: number | null = null;

/** 16 §8: warn when the device clock differs from the server by more than 5 min. */
export const CLOCK_SKEW_WARN_MS = 300_000;

export interface ClockReset {
  /** Server time the trusted clock was reset to (ms). */
  to: number;
  /** Trusted time before the reset (ms) — it was ahead of the server by more than the skew limit. */
  from: number;
}

/**
 * A server clock reading (HTTP `Date` / pull `server_time`): updates the trusted time and the skew.
 * SYNC-08: the server is the authority — a trusted time ahead of it by more than CLOCK_SKEW_WARN_MS
 * (a local clock that once ran ahead) is reset to the server time and recorded (`lastClockReset`,
 * audit flag for the UI/log). Without server contact the trusted time still never goes back.
 */
export async function observeServerTime(ms: number): Promise<void> {
  if (!Number.isFinite(ms)) return;
  lastSkewMs = now() - ms;
  const stored = Math.max((await getMeta<number>(META.maxSeenTime)) ?? 0, cachedMax);
  if (stored > ms + CLOCK_SKEW_WARN_MS) {
    cachedMax = ms;
    await setMeta(META.maxSeenTime, ms);
    await setMeta(META.clockReset, { to: ms, from: stored } satisfies ClockReset);
    return;
  }
  await observeTime(ms);
}

/** The last server-driven reset of the trusted clock (null = never). */
export async function lastClockReset(): Promise<ClockReset | null> {
  return (await getMeta<ClockReset>(META.clockReset)) ?? null;
}

/** Device clock minus server clock at the last server contact (null = never seen). */
export function clockSkewMs(): number | null {
  return lastSkewMs;
}

/** Records a server time (pull `server_time` / HTTP `Date`) or the local clock. */
export async function observeTime(ms: number): Promise<void> {
  if (!Number.isFinite(ms)) return;
  const stored = (await getMeta<number>(META.maxSeenTime)) ?? 0;
  const next = Math.max(stored, cachedMax, ms);
  cachedMax = next;
  if (next > stored) await setMeta(META.maxSeenTime, next);
}

export async function trustedNow(): Promise<number> {
  const stored = (await getMeta<number>(META.maxSeenTime)) ?? 0;
  cachedMax = Math.max(cachedMax, stored);
  return Math.max(now(), cachedMax);
}

/** Local clock behind the trusted time by more than `toleranceMs` → clock moved back (warning). */
export async function clockMovedBack(toleranceMs = 10 * 60 * 1000): Promise<boolean> {
  return now() < (await trustedNow()) - toleranceMs;
}

export function resetClockCache(): void {
  cachedMax = 0;
  lastSkewMs = null;
}

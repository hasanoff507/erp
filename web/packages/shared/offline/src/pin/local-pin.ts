/**
 * Local (offline) PIN check — decision D1, 14 §4.3/§12, 16 §12, contracts/device-auth.md §2.
 * The device verifies `pin_local_hash` = `pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>`
 * (PBKDF2-HMAC-SHA256, PIN as UTF-8, 32-byte key) with WebCrypto — no WASM, CSP stays strict.
 * The result is not a grant: it only fills `actor_user_id` / `approved_by` (14 §4.3).
 * Lockout per (user, device): 5 wrong PINs → 1 min, then 5 / 15 / 60 min; success resets.
 */
import { deviceDb, now, posDb } from "../runtime.ts";
import type { PinLockoutRow, StaffRow } from "../types.ts";

export const PIN_MAX_ATTEMPTS = 5;
export const PIN_LOCK_STEPS_MIN = [1, 5, 15, 60] as const;

export type PinResult =
  | { ok: true; user: StaffRow; mustChangePin: boolean }
  | { ok: false; reason: "invalid"; attemptsLeft: number }
  | { ok: false; reason: "locked"; lockedUntil: string }
  | { ok: false; reason: "no_verifier" | "inactive" | "unknown_user" };

interface ParsedVerifier {
  iterations: number;
  salt: Uint8Array;
  hash: Uint8Array;
}

function base64ToBytes(value: string): Uint8Array | null {
  try {
    const binary = atob(value);
    const out = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i);
    return out;
  } catch {
    return null;
  }
}

function digitsToInt(value: string): number | null {
  if (value.length === 0 || value.length > 9) return null;
  let n = 0;
  for (const ch of value) {
    const d = "0123456789".indexOf(ch);
    if (d === -1) return null;
    n = n * 10 + d;
  }
  return n;
}

export function parsePinVerifier(encoded: string): ParsedVerifier | null {
  const parts = encoded.split("$");
  if (parts.length !== 4 || parts[0] !== "pbkdf2_sha256") return null;
  const iterations = digitsToInt(parts[1] ?? "");
  const salt = base64ToBytes(parts[2] ?? "");
  const hash = base64ToBytes(parts[3] ?? "");
  if (!iterations || iterations < 1 || !salt || !hash || hash.length === 0) return null;
  return { iterations, salt, hash };
}

function constantTimeEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) diff |= (a[i] ?? 0) ^ (b[i] ?? 0);
  return diff === 0;
}

/** PBKDF2-SHA256 check of `pin` against an encoded verifier. */
export async function checkPinVerifier(pin: string, encoded: string): Promise<boolean> {
  const parsed = parsePinVerifier(encoded);
  if (!parsed) return false;
  const subtle = globalThis.crypto.subtle;
  const key = await subtle.importKey("raw", new TextEncoder().encode(pin), "PBKDF2", false, ["deriveBits"]);
  const bits = await subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt: parsed.salt as BufferSource, iterations: parsed.iterations },
    key,
    parsed.hash.length * 8,
  );
  return constantTimeEqual(new Uint8Array(bits), parsed.hash);
}

function lockMinutes(level: number): number {
  const index = Math.min(Math.max(level, 1), PIN_LOCK_STEPS_MIN.length) - 1;
  return PIN_LOCK_STEPS_MIN[index] ?? 60;
}

export const pinLockout = {
  async get(userId: string): Promise<PinLockoutRow> {
    return (await deviceDb().pin_lockouts.get(userId)) ?? emptyLockout(userId);
  },
};

function emptyLockout(userId: string): PinLockoutRow {
  return { user_id: userId, failures: 0, level: 0, locked_until: null };
}

function lockedResult(lockedUntil: number): PinResult {
  return { ok: false, reason: "locked", lockedUntil: new Date(lockedUntil).toISOString() };
}

/**
 * SEC-09: the lockout lives in `erp-device` (a logout does not reset it) and every update is a
 * read-modify-write inside ONE rw transaction, so two tabs failing at once both count. The PBKDF2
 * check itself runs outside the transaction (WebCrypto is not an IndexedDB request).
 */
export async function verifyLocalPin(userId: string, pin: string): Promise<PinResult> {
  const user = await posDb().permissions.get(userId);
  if (!user) return { ok: false, reason: "unknown_user" };
  if (!user.active) return { ok: false, reason: "inactive" };
  if (!user.pin_local_hash) return { ok: false, reason: "no_verifier" };

  const before = await pinLockout.get(userId);
  if (before.locked_until !== null && before.locked_until > now()) return lockedResult(before.locked_until);

  const ok = await checkPinVerifier(pin, user.pin_local_hash);
  const db = deviceDb();
  return db.transaction("rw", db.pin_lockouts, async (): Promise<PinResult> => {
    const lockout = (await db.pin_lockouts.get(userId)) ?? emptyLockout(userId);
    const nowMs = now();
    // another tab may have locked the user while the hash was computed
    if (lockout.locked_until !== null && lockout.locked_until > nowMs)
      return lockedResult(lockout.locked_until);
    if (ok) {
      await db.pin_lockouts.put(emptyLockout(userId));
      return { ok: true, user, mustChangePin: user.must_change_pin };
    }
    // an expired lock is over: failures were reset when it started, the level is kept
    const failures = lockout.failures + 1;
    if (failures >= PIN_MAX_ATTEMPTS) {
      const level = lockout.level + 1;
      const lockedUntil = nowMs + lockMinutes(level) * 60_000;
      await db.pin_lockouts.put({ user_id: userId, failures: 0, level, locked_until: lockedUntil });
      return lockedResult(lockedUntil);
    }
    await db.pin_lockouts.put({ user_id: userId, failures, level: lockout.level, locked_until: null });
    return { ok: false, reason: "invalid", attemptsLeft: PIN_MAX_ATTEMPTS - failures };
  });
}

/** After a successful online `POST /auth/pin/verify`: store the fresh verifier it returned. */
export async function storePinVerifier(userId: string, pinLocalHash: string): Promise<void> {
  await posDb()
    .permissions.where("user_id")
    .equals(userId)
    .modify((row) => {
      row.pin_local_hash = pinLocalHash;
    });
}

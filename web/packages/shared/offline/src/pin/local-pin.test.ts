import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { posDb } from "../runtime.ts";
import { CASHIER, setupOffline, teardownOffline, type TestEnv } from "../testing/setup.ts";
import type { StaffRow } from "../types.ts";
import {
  checkPinVerifier,
  parsePinVerifier,
  pinLockout,
  storePinVerifier,
  verifyLocalPin,
} from "./local-pin.ts";

// contracts/device-auth.md §2 known-answer vectors (salt = bytes 0x00..0x0f)
const V1234_1000 = "pbkdf2_sha256$1000$AAECAwQFBgcICQoLDA0ODw==$IkDqKiJ1SjxGEDVu+OTXrPJa8qw9LRGGbel6i3gSxSw=";
const V1234_600K =
  "pbkdf2_sha256$600000$AAECAwQFBgcICQoLDA0ODw==$nznZxxwixMRZvCy6zG104hhBhdZx2R8KNKaDRBOghJ0=";
const V908172_600K =
  "pbkdf2_sha256$600000$AAECAwQFBgcICQoLDA0ODw==$ZFpC4a2/irbU78Q8BXzcFRObJpCksrlR4+9qsCkAHJQ=";
const MINUTE = 60_000;

const cashier = (patch: Partial<StaffRow> = {}): StaffRow => ({
  user_id: CASHIER,
  full_name: "Kassir",
  role_codes: ["cashier"],
  branch_ids: [],
  active: true,
  must_change_pin: false,
  pin_local_hash: V1234_1000,
  permissions: [],
  ...patch,
});

let env: TestEnv;
beforeEach(async () => {
  env = await setupOffline();
});
afterEach(teardownOffline);

describe("PBKDF2 verifier (D1)", () => {
  it("matches the b3-device test vectors and rejects malformed verifiers", async () => {
    expect(await checkPinVerifier("1234", V1234_1000)).toBe(true);
    expect(await checkPinVerifier("1235", V1234_1000)).toBe(false);
    expect(await checkPinVerifier("1234", V1234_600K)).toBe(true);
    expect(await checkPinVerifier("908172", V908172_600K)).toBe(true);
    expect(parsePinVerifier("argon2id$...")).toBeNull();
    expect(parsePinVerifier("pbkdf2_sha256$x$AA==$AA==")).toBeNull();
    expect(await checkPinVerifier("1234", "pbkdf2_sha256$1000$%%%$AA==")).toBe(false);
  });
});

describe("verifyLocalPin + lockout 5 → 1/5/15/60 min (14 §12, 16 §12)", () => {
  it("accepts the right PIN and reports must_change_pin", async () => {
    await posDb().permissions.put(cashier({ must_change_pin: true }));
    expect(await verifyLocalPin(CASHIER, "1234")).toMatchObject({ ok: true, mustChangePin: true });
  });

  it("refuses unknown / inactive / verifier-less users without counting attempts", async () => {
    expect(await verifyLocalPin("nobody", "1234")).toEqual({ ok: false, reason: "unknown_user" });
    await posDb().permissions.put(cashier({ active: false }));
    expect(await verifyLocalPin(CASHIER, "1234")).toEqual({ ok: false, reason: "inactive" });
    await posDb().permissions.put(cashier({ pin_local_hash: null }));
    expect(await verifyLocalPin(CASHIER, "1234")).toEqual({ ok: false, reason: "no_verifier" });
    await storePinVerifier(CASHIER, V1234_1000);
    expect((await verifyLocalPin(CASHIER, "1234")).ok).toBe(true);
  });

  it("locks after 5 wrong PINs with a progressive 1 → 5 → 15 → 60 min lock, success resets", async () => {
    await posDb().permissions.put(cashier());
    const fail5 = async () => {
      let last;
      for (let i = 0; i < 5; i += 1) last = await verifyLocalPin(CASHIER, "0000");
      return last;
    };
    for (let i = 0; i < 4; i += 1) {
      expect(await verifyLocalPin(CASHIER, "0000")).toEqual({
        ok: false,
        reason: "invalid",
        attemptsLeft: 4 - i,
      });
    }
    const locked = await verifyLocalPin(CASHIER, "0000");
    expect(locked).toEqual({
      ok: false,
      reason: "locked",
      lockedUntil: new Date(env.clock.now + MINUTE).toISOString(),
    });
    // the right PIN is refused while locked
    expect((await verifyLocalPin(CASHIER, "1234")).ok).toBe(false);

    for (const minutes of [5, 15, 60, 60]) {
      env.clock.advance(61 * MINUTE);
      expect(await fail5()).toEqual({
        ok: false,
        reason: "locked",
        lockedUntil: new Date(env.clock.now + minutes * MINUTE).toISOString(),
      });
    }
    env.clock.advance(61 * MINUTE);
    expect((await verifyLocalPin(CASHIER, "1234")).ok).toBe(true);
    expect(await pinLockout.get(CASHIER)).toEqual({
      user_id: CASHIER,
      failures: 0,
      level: 0,
      locked_until: null,
    });
  });
});

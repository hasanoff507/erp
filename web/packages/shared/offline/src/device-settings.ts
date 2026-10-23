/**
 * `erp-device` — device-level storage that survives logout (16 §1 last row, §12; 24 §5.1):
 * `deviceSettings` (printer.*, pos.catalog_view, agent token …) and the device identity
 * (`device.identity`, contracts/device-auth.md §1). Never synced, never holds tenant business data.
 * Wiped only on DEVICE_REVOKED (lifecycle.wipeAfterRevoke).
 */
import { deviceDb } from "./runtime.ts";
import type { DeviceIdentity } from "./types.ts";

const RESERVED_PREFIX = "device.";
export const IDENTITY_KEY = "device.identity";
/** Counter floors copied here before `erp-pos` is deleted on logout (seq / receipt_seq stay monotonic). */
export const COUNTER_FLOORS_KEY = "device.counter_floors";

export interface CounterFloors {
  seq: number;
  receiptSeq: Record<string, number>;
}

function assertPublicKey(key: string): void {
  if (key.startsWith(RESERVED_PREFIX)) throw new Error(`deviceSettings key "${key}" is reserved`);
}

export const deviceSettings = {
  async get<T>(key: string): Promise<T | undefined> {
    const row = await deviceDb().device_settings.get(key);
    return row?.value as T | undefined;
  },
  async set<T>(key: string, value: T): Promise<void> {
    assertPublicKey(key);
    await deviceDb().device_settings.put({ key, value });
  },
  async remove(key: string): Promise<void> {
    assertPublicKey(key);
    await deviceDb().device_settings.delete(key);
  },
  async all(): Promise<Record<string, unknown>> {
    const rows = await deviceDb().device_settings.toArray();
    return Object.fromEntries(
      rows.filter((r) => !r.key.startsWith(RESERVED_PREFIX)).map((r) => [r.key, r.value]),
    );
  },
};

/** The parts of GET /auth/session the POS bootstrap compares with the local identity (SEC-07). */
export interface SessionBinding {
  tenant: { id: string } | null;
  device?: { id: string } | null;
}

/**
 * SEC-07: the cached POS data (erp-pos) may be used only by a session of the same tenant bound to the
 * same device. Pure — callers decide what to show when it is false (no Dexie reads).
 */
export function identityMatchesSession(
  identity: DeviceIdentity | null,
  session: SessionBinding | null,
): boolean {
  if (!identity || !session?.tenant || !session.device) return false;
  return session.device.id === identity.deviceId && session.tenant.id === identity.tenantId;
}

export const deviceIdentity = {
  async matchesSession(session: SessionBinding | null): Promise<boolean> {
    return identityMatchesSession(await deviceIdentity.get(), session);
  },
  async get(): Promise<DeviceIdentity | null> {
    const row = await deviceDb().device_settings.get(IDENTITY_KEY);
    return (row?.value as DeviceIdentity | undefined) ?? null;
  },
  async set(identity: DeviceIdentity): Promise<void> {
    await deviceDb().device_settings.put({ key: IDENTITY_KEY, value: { ...identity } });
  },
  async clear(): Promise<void> {
    await deviceDb().device_settings.delete(IDENTITY_KEY);
  },
};

export async function readCounterFloors(): Promise<CounterFloors> {
  const row = await deviceDb().device_settings.get(COUNTER_FLOORS_KEY);
  return (row?.value as CounterFloors | undefined) ?? { seq: 0, receiptSeq: {} };
}

export async function writeCounterFloors(floors: CounterFloors): Promise<void> {
  await deviceDb().device_settings.put({ key: COUNTER_FLOORS_KEY, value: floors });
}

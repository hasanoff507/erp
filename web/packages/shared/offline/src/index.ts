/**
 * @shared/offline — placeholder (24 §1, 16-offline-sync.md).
 * Dexie databases `erp-pos` (catalog, outbox, card_attempts) and `erp-device` (device_settings),
 * the append-only outbox and /sync push/pull arrive with the web POS (Bosqich 3).
 */
export const OFFLINE_DB_NAMES = { pos: "erp-pos", device: "erp-device" } as const;

/**
 * @shared/offline — offline-first engine of the web POS (24 §1, §5; 16-offline-sync.md).
 * Contract: .claude-scratch/b3/contracts/offline-api.md (contract 7). No UI, no user-facing strings.
 *
 * - Dexie `erp-pos` (catalog, prices, customers, permissions, outbox, card_attempts, …) and `erp-device`
 *   (device settings + identity, survives logout) — db/schema.ts.
 * - Append-only outbox (`enqueueEvent`) under Web Lock "erp-outbox-writer", BroadcastChannel "erp-sync".
 * - Sync engine: `/sync/push` (seq order, ≤ 100, outbox_state) and `/sync/pull` (snapshot + deltas).
 * - Local queries for the POS screens, local PIN (PBKDF2, D1), 48 h fiscal ladder, logout/revoke wipe.
 */
export { DEFAULT_DB_NAMES, configureOffline, resetOfflineRuntime, type OfflineOptions } from "./runtime.ts";
export { DEVICE_DB_VERSION, POS_DB_VERSION } from "./db/schema.ts";
export {
  deviceIdentity,
  deviceSettings,
  identityMatchesSession,
  type SessionBinding,
} from "./device-settings.ts";
export { OfflineError, isOfflineError, type OfflineErrorCode } from "./lib/errors.ts";
export { OUTBOX_WRITER_LOCK, SYNC_PUSH_LOCK } from "./lib/locks.ts";
export { SYNC_CHANNEL, closeSyncChannel } from "./lib/broadcast.ts";
export {
  CLOCK_SKEW_WARN_MS,
  clockMovedBack,
  clockSkewMs,
  lastClockReset,
  trustedNow,
  type ClockReset,
} from "./lib/clock.ts";

export { enqueueEvent, type EnqueueOptions, type EnqueueResult } from "./outbox/enqueue.ts";
export { awaitEventResult, outbox, type OutboxExport, type OutboxSummary } from "./outbox/queries.ts";

export {
  INITIAL_SYNC_STATUS,
  authRequired,
  deviceRevoked,
  outboxChanged,
  pullApplied,
  quotaWarning,
  subscriptionRestricted,
  syncRequested,
  syncStatusChanged,
  type QuotaLevel,
  type QuotaState,
  type SyncStatus,
} from "./events.ts";
export {
  backoffDelayMs,
  runPull,
  runPush,
  startSyncEngine,
  stopSyncEngine,
  syncIdle,
  syncNow,
  nextPushAt,
  LOCK_RETRY_MS,
} from "./sync/engine.ts";
export { closeBlockers } from "./sync/push.ts";
export { getSyncStatus } from "./sync/status.ts";
export {
  SYNC_PULL_PATH,
  SYNC_PUSH_PATH,
  SyncHttpError,
  createHttpSyncTransport,
  type SyncTransport,
  type TransportResult,
} from "./sync/transport.ts";

export { catalog, effectivePrice, prices, type BarcodeHit, type ProductView } from "./repos/catalog.ts";
export {
  cardTerminals,
  customers,
  fiscal,
  limits,
  markingCodes,
  salesHistory,
  settings,
  shift,
  staff,
  stock,
} from "./repos/reference.ts";
export { cardAttempts } from "./repos/card-attempts.ts";
// --- B4 debt book (w-debts) ---
export {
  allocateOnDevice,
  createQuickCustomer,
  customerDebtView,
  customerDebts,
  debtPaymentPayload,
  enqueueDebtPayment,
  fiscalShares,
  localSaleDoc,
  overCreditLimit,
  quickCustomerPayload,
  saleDebtPart,
  unreflected,
  type CustomerDebtView,
  type DebtPaymentInput,
  type DebtPaymentMethod,
  type QuickCustomerInput,
} from "./repos/debts.ts";

export {
  PIN_LOCK_STEPS_MIN,
  PIN_MAX_ATTEMPTS,
  checkPinVerifier,
  pinLockout,
  storePinVerifier,
  verifyLocalPin,
  type PinResult,
} from "./pin/local-pin.ts";

export {
  $fiscalLadder,
  OFFLINE_BLOCK_HOURS,
  OFFLINE_WARN_HOURS,
  fiscalLadderLevel,
  refreshFiscalLadder,
  type FiscalLadder,
  type FiscalLadderLevel,
} from "./fiscal/ladder.ts";
// --- B5 local-bridge fiscal receipts (w-pos) ---
export {
  fiscalReservations,
  rememberFiscalResult,
  releaseReservation,
  reserveReceiptSeq,
  type FiscalReservation,
} from "./fiscal/reservation.ts";

export {
  logout,
  logoutCheck,
  wipePosForLogout,
  type PosLogoutWipe,
  wipeAfterRevoke,
  type LogoutCheck,
} from "./lifecycle/logout.ts";
export { checkStorageQuota, requestPersistentStorage, runRetention } from "./lifecycle/retention.ts";

export * from "./types.ts";

/** Kept for existing imports (Bosqich 0 placeholder). */
export const OFFLINE_DB_NAMES = { pos: "erp-pos", device: "erp-device" } as const;

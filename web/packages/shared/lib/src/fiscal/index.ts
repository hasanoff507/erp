/**
 * @shared/lib/fiscal — the web POS side of `FiscalPort` (21 §1: "frontendda `@shared/lib/fiscal` — xuddi shu
 * shakldagi TypeScript interfeys"). Separate, rarely changing package (fiscal code isolation, VMQ-943 2-ilova
 * 6-band). Pure TS: no React, no storage — the POS screens decide the mode from the register's BO-12 binding.
 */
export * from "./types.ts";
export {
  fiscalItem,
  fiscalPayments,
  fiscalReceipt,
  fiscalShares,
  milliOf,
  tiyinOf,
  type FiscalLineInput,
  type FiscalPaymentInput,
  type FiscalReceiptInput,
  type FiscalShare,
} from "./boundary.ts";
export {
  createLocalBridgeFiscalAdapter,
  FISCAL_TIMEOUTS,
  parseFiscalResult,
  toFiscalError,
} from "./local-bridge.ts";
export {
  localFiscalReadiness,
  LOCKED_FM_STATES,
  type AgentFiscalState,
  type LocalFiscalReadiness,
} from "./readiness.ts";

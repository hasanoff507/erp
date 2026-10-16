import type { SignupInBusinessType, SignupInLegalForm } from "@shared/models";

/** BO-21 steps (07): ① account ② store ③ products ④ opening debts ⑤ OFD/e-invoice ⑥ device install. */
export type StepId = "account" | "store" | "products" | "debts" | "ofd" | "install";

export const STEP_IDS: readonly StepId[] = ["account", "store", "products", "debts", "ofd", "install"];

/** ④⑤⑥ may be skipped (07 "O'tkazib yuborish") — shown as `ixtiyoriy` until reached. */
export const SKIPPABLE_STEPS: readonly StepId[] = ["debts", "ofd", "install"];

/** Steps before the tenant exists; after POST /auth/signup they cannot be reopened. */
export const PRE_SIGNUP_STEPS: readonly StepId[] = ["account", "store"];

/** ① `signupMethod` (07): phone + password, or Google (phone asked after the return, 14 §2.2). */
export type SignupMethod = "phone" | "google";

export type OtpChannel = "telegram" | "sms";

export interface OtpChallenge {
  challengeId: string;
  /** E.164 the code was sent to. */
  phone: string;
  channel: OtpChannel;
  expiresAt: string;
  /** `TELEGRAM_NOT_LINKED` warning — show the bot link (07 BO-21 `otp`). */
  telegramNotLinked: boolean;
  verified: boolean;
}

/** Step ① result (kept in memory only until signup; never persisted). */
export interface AccountData {
  /** E.164. */
  phone: string;
  ownerName: string;
  /** `null` on the Google path (14 §20: password optional only with the pending Google identity). */
  password: string | null;
}

/** Step ② form (07 fields `storeName` … `aiCrossBorderConsent`). */
export interface StoreData {
  storeName: string;
  businessType: SignupInBusinessType;
  legalForm: SignupInLegalForm;
  acceptTerms: boolean;
  aiCrossBorderConsent: boolean;
}

export const DEFAULT_STORE: StoreData = {
  storeName: "",
  businessType: "retail",
  legalForm: "llc",
  acceptTerms: false,
  aiCrossBorderConsent: false,
};

export const BUSINESS_TYPES: readonly SignupInBusinessType[] = ["retail", "other"];
export const LEGAL_FORMS: readonly SignupInLegalForm[] = [
  "llc",
  "jsc",
  "private_enterprise",
  "sole_proprietor",
];

/** ③a `method` (07): manual product form, Excel/CSV import, photo (AI-03 — Bosqich 6). */
export type ProductsMethod = "manual" | "import" | "photo";

/** How POST /auth/signup failed, for routing the user back to the right step. */
export type SignupFailure =
  "phone_taken" | "otp_stale" | "terms_outdated" | "google_expired" | "fields" | "general";

/** Seconds between two code requests (UI guard; the server has its own limits, 14 §12). */
export const RESEND_COOLDOWN_S = 60;
export const TRIAL_DAYS = 30;

/**
 * Slot for ③a Excel/CSV (07): the catalog's import flow, injected by the shell — page packages do
 * not import each other (24 §1, eslint `otherPages`). The shell adapts the catalog component's own
 * result to `createdProductCount` (commit result `created_product_count`, 19 §6).
 */
export interface ProductImportResult {
  createdProductCount: number;
}

export interface ProductImportSlotProps {
  embedded?: boolean;
  onDone?: (result: ProductImportResult) => void;
}

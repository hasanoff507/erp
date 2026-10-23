import { createEvent } from "effector";

import type { ApprovalRef, StartInput } from "../types/index.ts";

/** "Karta" pressed on POS-03 (or a card part of a mixed payment). */
export const cardPaymentStarted = createEvent<StartInput>();
/** "Terminalda bekor qilish" — only while the amount waits on the terminal. */
export const cancelPressed = createEvent();
/** "Qayta yuborish" — only after a final decline; always a NEW attempt_id. */
export const retryPressed = createEvent();
/** "Holatni tekshirish" — repeat the safe status query of an unknown attempt. */
export const statusCheckRequested = createEvent();
/** "Menejer tasdig'i bilan yopish": passed / not passed from the terminal slip (after the PIN approval). */
export const managerResolved = createEvent<{ passed: boolean; approval: ApprovalRef }>();
/** Integrated path closed → "Karta terminalsiz" (21 §9.2). */
export const manualRequested = createEvent();
/** "Karta terminalsiz qabul qilindi" confirmed (with the PIN approval when the policy needs it). */
export const manualConfirmed = createEvent<{ approval: ApprovalRef | null }>();
/** The cashier cancels the sale after an approved card (fiscal receipt failed) → automatic void. */
export const saleCancelled = createEvent();
/** The sale event took the outcome (`enqueueEvent(..., {removeCardAttemptIds})`) — back to idle. */
export const cardOutcomeConsumed = createEvent();
/** Leave the card panel without a payment (idle / declined / voided / unavailable only). */
export const cardPaymentClosed = createEvent();
/** POS opened / reloaded: unresolved attempts keep blocking and are re-queried; final ones are flushed. */
export const cardPaymentRestored = createEvent<{
  cashRegisterId: string | null;
  shiftId: string | null;
} | void>();
/** SYNC-03: attach the dangling approved purchase to the current receipt (same amount only). */
export const danglingAttached = createEvent();
/** SYNC-03: void the dangling approved purchase on the terminal. */
export const danglingVoided = createEvent();
/** Logout / revoke blocker (16 §12) or a manual check: look for unresolved / dangling attempts and show them. */
export const cardRecoveryRequested = createEvent();
/** The recovery dialog was dismissed (the attempt itself stays until resolved). */
export const cardRecoveryClosed = createEvent();
/** 1 s countdown tick while pending. */
export const clockTicked = createEvent<number>();

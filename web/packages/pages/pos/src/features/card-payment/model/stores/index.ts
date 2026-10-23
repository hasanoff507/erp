import { createStore } from "effector";

import { IDLE, type CardAttemptState } from "../types/index.ts";

/** The one card attempt state of POS-03 (24 §6.5). */
export const $cardAttempt = createStore<CardAttemptState>(IDLE);
/** ms epoch "now" for the countdown (ticks every second while pending). */
export const $now = createStore<number>(0);
/** Staff who may approve a manual card / close an unknown attempt (local PIN). */
export const $approvers = createStore<{ userId: string; name: string }[]>([]);
/** SYNC-03: the standalone recovery dialog (unknown / dangling attempt found on reload or at logout). */
export const $cardRecoveryOpen = createStore(false);
/** Last approval / PIN error of the approval dialog (i18n code). */
export const $approvalError = createStore<string | null>(null, { skipVoid: false });

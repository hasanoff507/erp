/**
 * Online PIN re-prompt for `actor_not_verified` (device-auth.md §4): the POS shows `<ActorPinPrompt />` for the
 * current cashier; `/auth/pin/verify` succeeds → the waiting REST call is retried. Without a mounted prompt
 * (or on cancel) the original 403 goes to the screen.
 */
import { createEvent, createStore } from "effector";

import { http } from "@shared/api";

import { installActorBinding } from "./actor.ts";
import { $posCashier, posSessionStarted } from "./index.ts";

export const actorPromptRequested = createEvent<string>();
export const actorPromptClosed = createEvent();
export const $actorPrompt = createStore<{ userId: string } | null>(null, { skipVoid: false })
  .on(actorPromptRequested, (_, userId) => ({ userId }))
  .reset(actorPromptClosed);

let mounted = 0;
let pending: ((ok: boolean) => void) | null = null;

/** The prompt component registers itself (mount / unmount). */
export function registerActorPrompt(): () => void {
  mounted += 1;
  return () => {
    mounted -= 1;
  };
}

/** Called by the prompt: true after a successful online `/auth/pin/verify`, false on cancel. */
export function settleActorPrompt(ok: boolean): void {
  const resolve = pending;
  pending = null;
  actorPromptClosed();
  resolve?.(ok);
}

export function requestActorReverify(userId: string): Promise<boolean> {
  if (mounted === 0) return Promise.resolve(false);
  pending?.(false);
  return new Promise<boolean>((resolve) => {
    pending = resolve;
    actorPromptRequested(userId);
  });
}

let uninstall: (() => void) | null = null;

/** Once per page (POS runtime start): header + re-prompt on the shared axios instance. */
export function startActorBinding(): void {
  if (uninstall) return;
  uninstall = installActorBinding(http as unknown as Parameters<typeof installActorBinding>[0], {
    actor: () => $posCashier.getState()?.userId ?? null,
    reverify: requestActorReverify,
  });
}

// the POS runtime start installs the binding (idempotent)
posSessionStarted.watch(() => startActorBinding());

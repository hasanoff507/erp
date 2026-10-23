/**
 * Dynamic payments of the web POS — dynamic UzQR / Click / Payme / Uzum (07 POS-03, POS-13; 18 §16; 21 §9;
 * QT-M01-13). Online only:
 *  1. `checkoutStarted` → `POST /payments/checkouts` (`checkout_ref` UUIDv7 from the device, Idempotency-Key by the
 *     API client — a double tap never makes a second checkout) → QR / link on screen;
 *  2. «to'lov kutilmoqda»: `GET /payments/checkouts/{ref}` every 2 s while `pending` (the webhook is server side);
 *     offline → polling pauses and the payment STAYS pending — the sale is never closed with this method;
 *  3. `confirmed` (with `provider_tx_id`) → `$checkoutConfirmed`: the sale / debt payment is written with
 *     `checkout_ref` + `provider_tx_id`; `failed` / `expired` → the cashier picks another method;
 *  4. «Bekor qilish» asks the server once more first — a payment that arrived meanwhile is kept (never dropped).
 * Nothing card-related is typed here (PCI); the provider page is on the customer's phone.
 */
import { combine, createEffect, createEvent, createStore, sample } from "effector";
import { delay } from "patronum";

import { api } from "@shared/api";
import type { CheckoutIn, CheckoutOut } from "@shared/models";
import { newAttemptId as newId } from "@shared/lib/card-terminal";
import type { Money } from "@shared/lib/money";
import { $isOnline } from "@shared/state/network";

export type CheckoutProvider = "uzqr" | "click" | "payme" | "uzum";
export type CheckoutPurpose = "sale" | "debt_payment";
export type CheckoutPhase = "creating" | "pending" | "confirmed" | "failed" | "expired" | "error";

export interface CheckoutState {
  ref: string;
  provider: CheckoutProvider;
  purpose: CheckoutPurpose;
  amount: Money;
  phase: CheckoutPhase;
  qrPayload: string | null;
  checkoutUrl: string | null;
  providerTxId: string | null;
  expiresAt: string | null;
  /** Catalog code (or `validation.*` message key) of a failed creation. */
  error: { code: string; params: Record<string, unknown> } | null;
}

export interface ConfirmedCheckout {
  ref: string;
  provider: CheckoutProvider;
  amount: Money;
  providerTxId: string;
}

export interface CheckoutDeps {
  create(body: CheckoutIn): Promise<CheckoutOut>;
  get(ref: string): Promise<CheckoutOut>;
  now(): number;
}

export const CHECKOUT_POLL_MS = 2_000;

let deps: CheckoutDeps = {
  create: (body) => api.sales.createPaymentCheckout(body),
  get: (ref) => api.sales.getPaymentCheckout(ref),
  now: () => Date.now(),
};
const original = deps;
/** Tests: fake API / clock. */
export function configureCheckout(patch: Partial<CheckoutDeps> | null): void {
  deps = patch ? { ...original, ...patch } : original;
}

export interface StartInput {
  provider: CheckoutProvider;
  purpose: CheckoutPurpose;
  amount: Money;
  cashRegisterId: string;
}

export const checkoutStarted = createEvent<StartInput>();
export const checkoutCancelled = createEvent();
/** The sale / debt payment carrying this checkout is in the outbox (or the payment closed). */
export const checkoutReset = createEvent();

function phaseOf(out: CheckoutOut, nowMs: number): CheckoutPhase {
  if (out.status === "confirmed" || out.status === "consumed") return out.provider_tx_id ? "confirmed" : "pending";
  if (out.status === "failed") return "failed";
  if (out.status === "expired") return "expired";
  if (out.expires_at && Date.parse(out.expires_at) <= nowMs) return "expired";
  return "pending";
}

function apply(state: CheckoutState, out: CheckoutOut): CheckoutState {
  if (out.checkout_ref !== state.ref) return state;
  return {
    ...state,
    phase: phaseOf(out, deps.now()),
    qrPayload: out.qr_payload ?? state.qrPayload,
    checkoutUrl: out.checkout_url ?? state.checkoutUrl,
    providerTxId: out.provider_tx_id ?? state.providerTxId,
    expiresAt: out.expires_at ?? state.expiresAt,
  };
}

const errorOf = (e: unknown): { code: string; params: Record<string, unknown> } => {
  const err = e as { code?: unknown; params?: unknown; details?: { messageKey?: unknown }[] } | null;
  const key = err?.details?.[0]?.messageKey;
  if (typeof key === "string" && key.startsWith("validation.")) return { code: key, params: {} };
  return {
    code: typeof err?.code === "string" ? err.code : "PAYMENT_PROVIDER_ERROR",
    params: err?.params && typeof err.params === "object" ? (err.params as Record<string, unknown>) : {},
  };
};

export const createCheckoutFx = createEffect(async (input: StartInput & { ref: string }) =>
  deps.create({
    checkout_ref: input.ref,
    provider: input.provider,
    cash_register_id: input.cashRegisterId,
    amount: input.amount,
    ...(input.provider === "uzqr" ? { qr_type: "dynamic" as const } : {}),
  }),
);
export const pollCheckoutFx = createEffect((ref: string) => deps.get(ref));
/** «Bekor qilish»: one last look — a payment that already arrived is kept. */
export const cancelCheckFx = createEffect((ref: string) => deps.get(ref));

export const $checkout = createStore<CheckoutState | null>(null, { skipVoid: false });
export const $checkoutConfirmed = $checkout.map((c): ConfirmedCheckout | null =>
  c?.phase === "confirmed" && c.providerTxId
    ? { ref: c.ref, provider: c.provider, amount: c.amount, providerTxId: c.providerTxId }
    : null,
);
/** A checkout waits for the customer — the payment dialog must not be left silently. */
export const $checkoutWaiting = $checkout.map((c) => c?.phase === "creating" || c?.phase === "pending");

const started = sample({
  clock: checkoutStarted,
  source: $checkout,
  // one checkout at a time; a confirmed one is never replaced
  filter: (c) => !c || (c.phase !== "creating" && c.phase !== "pending" && c.phase !== "confirmed"),
  fn: (_, input) => ({ ...input, ref: newId() }),
});
$checkout.on(started, (_, input) => ({
  ref: input.ref,
  provider: input.provider,
  purpose: input.purpose,
  amount: input.amount,
  phase: "creating",
  qrPayload: null,
  checkoutUrl: null,
  providerTxId: null,
  expiresAt: null,
  error: null,
}));
sample({ clock: started, target: createCheckoutFx });

$checkout
  .on(createCheckoutFx.doneData, (s, out) => (s ? apply(s, out) : s))
  .on(createCheckoutFx.fail, (s, { params, error }) =>
    s && s.ref === params.ref ? { ...s, phase: "error", error: errorOf(error) } : s,
  )
  .on([pollCheckoutFx.doneData, cancelCheckFx.doneData], (s, out) => (s ? apply(s, out) : s))
  .reset(checkoutReset);

// polling while pending and online (QT-M01-13: offline → stays pending, never "paid")
const pollLater = delay({
  source: sample({
    clock: [createCheckoutFx.doneData, pollCheckoutFx.finally],
    source: $checkout,
    filter: (c) => c?.phase === "pending",
    fn: (c) => (c as CheckoutState).ref,
  }),
  timeout: CHECKOUT_POLL_MS,
});
sample({
  clock: pollLater,
  source: { c: $checkout, online: $isOnline, busy: pollCheckoutFx.pending },
  filter: ({ c, online, busy }, ref) => online && !busy && c?.phase === "pending" && c.ref === ref,
  fn: (_, ref) => ref,
  target: pollCheckoutFx,
});
// back online → resume
sample({
  clock: $isOnline.updates,
  source: $checkout,
  filter: (c, online) => online && c?.phase === "pending",
  fn: (c) => (c as CheckoutState).ref,
  target: pollCheckoutFx,
});

sample({
  clock: checkoutCancelled,
  source: { c: $checkout, online: $isOnline },
  filter: ({ c, online }) => online && (c?.phase === "pending" || c?.phase === "creating"),
  fn: ({ c }) => (c as CheckoutState).ref,
  target: cancelCheckFx,
});
// not paid → drop it locally (the server expires it); paid meanwhile → stays confirmed
sample({
  clock: cancelCheckFx.done,
  source: $checkout,
  filter: (c) => c !== null && c.phase !== "confirmed",
  fn: () => undefined,
  target: checkoutReset,
});
// offline / finished / failed / errored: just drop it
sample({
  clock: checkoutCancelled,
  source: { c: $checkout, online: $isOnline },
  filter: ({ c, online }) =>
    c !== null && c.phase !== "confirmed" && (!online || (c.phase !== "pending" && c.phase !== "creating")),
  fn: () => undefined,
  target: checkoutReset,
});

/** The checkout as the panel shows it (with the network state). */
export const $checkoutView = combine($checkout, $isOnline, (c, online) =>
  c ? { ...c, offline: !online } : null,
);

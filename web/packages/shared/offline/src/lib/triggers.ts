/** Late-bound triggers so low-level modules (outbox) can wake the engine without an import cycle. */
type Trigger = () => void;

let pushTrigger: Trigger = () => undefined;

export function setPushTrigger(trigger: Trigger): void {
  pushTrigger = trigger;
}

export function triggerPush(): void {
  pushTrigger();
}

let countersTrigger: Trigger = () => undefined;

/** Registered by sync/status.ts: re-read the outbox counters of $syncState (works offline too). */
export function setCountersTrigger(trigger: Trigger): void {
  countersTrigger = trigger;
}

export function triggerCounters(): void {
  countersTrigger();
}

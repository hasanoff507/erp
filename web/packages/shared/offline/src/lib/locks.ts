/**
 * Web Locks (16 §11, 24 §5): `erp-outbox-writer` serialises outbox writes + seq/receipt_seq across tabs;
 * `erp-sync-push` elects the single pushing tab. Where `navigator.locks` is missing (old browser, Node
 * tests) an in-process queue gives the same guarantee inside one tab.
 */
export const OUTBOX_WRITER_LOCK = "erp-outbox-writer";
export const SYNC_PUSH_LOCK = "erp-sync-push";

interface LockManagerLike {
  request<T>(name: string, options: { ifAvailable?: boolean }, cb: (lock: unknown) => Promise<T>): Promise<T>;
}

function lockManager(): LockManagerLike | null {
  if (typeof navigator === "undefined") return null;
  const locks = (navigator as { locks?: LockManagerLike }).locks;
  return locks && typeof locks.request === "function" ? locks : null;
}

const localQueues = new Map<string, Promise<unknown>>();
const localHeld = new Set<string>();

async function localExclusive<T>(name: string, fn: () => Promise<T>): Promise<T> {
  const previous = localQueues.get(name) ?? Promise.resolve();
  let release!: () => void;
  const current = new Promise<void>((resolve) => {
    release = resolve;
  });
  const chained = previous.then(() => current);
  localQueues.set(name, chained);
  await previous.catch(() => undefined);
  localHeld.add(name);
  try {
    return await fn();
  } finally {
    localHeld.delete(name);
    release();
    if (localQueues.get(name) === chained) localQueues.delete(name);
  }
}

/** Runs `fn` while holding the exclusive lock `name` (waits for it). */
export function withLock<T>(name: string, fn: () => Promise<T>): Promise<T> {
  const manager = lockManager();
  if (manager) return manager.request(name, {}, () => fn());
  return localExclusive(name, fn);
}

/** Runs `fn` only if the lock is free right now; otherwise resolves `{ acquired: false }`. */
export async function tryWithLock<T>(
  name: string,
  fn: () => Promise<T>,
): Promise<{ acquired: true; value: T } | { acquired: false }> {
  const manager = lockManager();
  if (manager) {
    return manager.request(name, { ifAvailable: true }, async (lock) =>
      lock === null ? { acquired: false as const } : { acquired: true as const, value: await fn() },
    );
  }
  if (localHeld.has(name) || localQueues.has(name)) return { acquired: false };
  return { acquired: true, value: await localExclusive(name, fn) };
}

/**
 * Fire-and-forget work (ladder refresh, counters, retention) — never an unhandled rejection: errors
 * are logged, except a database closed by logout/wipe in the middle (expected). `backgroundIdle()`
 * lets tests and logout wait for it.
 */
const running = new Set<Promise<unknown>>();

function isClosedDatabase(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    (error as { name?: unknown }).name === "DatabaseClosedError"
  );
}

export function runBackground(task: () => Promise<unknown>): void {
  const promise = (async () => {
    try {
      await task();
    } catch (error) {
      if (!isClosedDatabase(error)) console.error(error);
    }
  })();
  running.add(promise);
  void promise.finally(() => running.delete(promise));
}

export async function backgroundIdle(): Promise<void> {
  while (running.size > 0) await Promise.all([...running]);
}

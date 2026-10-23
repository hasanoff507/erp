/**
 * USB HID "keyboard wedge" scanner detection — 24 §4 (`useBarcodeWedge`), 08 `BarcodeField`, 06 §1.6.
 * A scanner types characters < ~30 ms apart and ends with Enter; a human types slower. Framework-free:
 * the React hook in `BarcodeField` wraps `createBarcodeWedge` in a `useEffect`.
 */

export interface BarcodeWedgeOptions {
  onScan: (code: string) => void;
  /** Maximum gap between scanner keystrokes (ms). */
  maxIntervalMs?: number;
  /** Shorter bursts are treated as typing. */
  minLength?: number;
  /** Clock (tests). */
  now?: () => number;
}

interface KeyLikeEvent {
  key: string;
  ctrlKey?: boolean;
  altKey?: boolean;
  metaKey?: boolean;
  preventDefault(): void;
  stopPropagation?(): void;
}

export interface WedgeTarget {
  addEventListener(
    type: "keydown",
    listener: (event: KeyLikeEvent) => void,
    options?: boolean | { capture?: boolean },
  ): void;
  removeEventListener(
    type: "keydown",
    listener: (event: KeyLikeEvent) => void,
    options?: boolean | { capture?: boolean },
  ): void;
}

/** Pure state machine (testable without DOM). Returns the scanned code on the terminating Enter, else null. */
export function createWedgeDetector({
  maxIntervalMs = 30,
  minLength = 4,
  now = () => Date.now(),
}: Omit<BarcodeWedgeOptions, "onScan"> = {}) {
  let buffer = "";
  let last = 0;
  return {
    /** Feeds one key; returns the code when a scan completes. */
    key(key: string): string | null {
      const t = now();
      const gap = t - last;
      last = t;
      if (key === "Enter") {
        const code = buffer;
        buffer = "";
        return gap <= maxIntervalMs && code.length >= minLength ? code : null;
      }
      if (key.length !== 1) {
        buffer = "";
        return null;
      }
      buffer = buffer && gap <= maxIntervalMs ? buffer + key : key;
      return null;
    },
    reset() {
      buffer = "";
    },
  };
}

/**
 * Listens on `target` (window / document / an element, capture phase) and calls `onScan` with complete
 * scans. The terminating Enter of a scan is `preventDefault`-ed so forms are not submitted.
 * Returns the unsubscribe function.
 */
export function createBarcodeWedge(target: WedgeTarget, options: BarcodeWedgeOptions): () => void {
  const detector = createWedgeDetector(options);
  const listener = (event: KeyLikeEvent) => {
    if (event.ctrlKey || event.altKey || event.metaKey) {
      detector.reset();
      return;
    }
    const code = detector.key(event.key);
    if (code !== null) {
      event.preventDefault();
      event.stopPropagation?.();
      options.onScan(code);
    }
  };
  target.addEventListener("keydown", listener, { capture: true });
  return () => target.removeEventListener("keydown", listener, { capture: true });
}

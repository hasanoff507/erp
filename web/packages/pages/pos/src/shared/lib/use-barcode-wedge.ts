/**
 * `useBarcodeWedge` — React wrapper around `@shared/lib/scanner` (24 §4, 06 §1.6): a USB HID scanner types
 * fast and ends with Enter; the scan is delivered wherever the focus is (07 POS-02 "Skaner har doim faol").
 * The listener runs in the capture phase so the scan never lands in another input.
 */
import { useEffect, useLayoutEffect, useRef } from "react";

import { createBarcodeWedge } from "@shared/lib/scanner";

let active = 0;

export function useBarcodeWedge(onScan: (code: string) => void, enabled = true): void {
  const handler = useRef(onScan);
  useLayoutEffect(() => {
    handler.current = onScan;
  });
  useEffect(() => {
    if (!enabled) return undefined;
    const stop = createBarcodeWedge(window, { onScan: (code) => handler.current(code) });
    // readiness marker for kiosk monitoring / e2e: a scanner burst is taken (counted — screens overlap on a switch)
    active += 1;
    document.documentElement.dataset.posScanner = "on";
    return () => {
      stop();
      active -= 1;
      if (active === 0) delete document.documentElement.dataset.posScanner;
    };
  }, [enabled]);
}

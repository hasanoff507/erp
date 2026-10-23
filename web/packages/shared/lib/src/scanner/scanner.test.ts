import { describe, expect, it, vi } from "vitest";

import { createBarcodeWedge, createWedgeDetector, type WedgeTarget } from "./index.ts";

function clock() {
  let t = 1000;
  return { now: () => t, advance: (ms: number) => (t += ms) };
}

describe("keyboard wedge (24 §4, 08 BarcodeField)", () => {
  it("fast burst + Enter is a scan; human typing is not", () => {
    const c = clock();
    const d = createWedgeDetector({ now: c.now });
    let result: string | null = null;
    for (const ch of "2212345012503") {
      c.advance(8);
      expect(d.key(ch)).toBeNull();
    }
    c.advance(8);
    result = d.key("Enter");
    expect(result).toBe("2212345012503");

    for (const ch of "1234") {
      c.advance(150);
      d.key(ch);
    }
    c.advance(150);
    expect(d.key("Enter")).toBeNull();
  });

  it("listener prevents Enter only for scans and can be removed", () => {
    const c = clock();
    const listeners = new Set<(e: Parameters<Parameters<WedgeTarget["addEventListener"]>[1]>[0]) => void>();
    const target: WedgeTarget = {
      addEventListener: (_t, l) => listeners.add(l),
      removeEventListener: (_t, l) => listeners.delete(l),
    };
    const onScan = vi.fn();
    const stop = createBarcodeWedge(target, { onScan, now: c.now });
    const press = (key: string) => {
      const event = { key, preventDefault: vi.fn() };
      for (const l of listeners) l(event);
      return event;
    };
    for (const ch of "4780000123456") {
      c.advance(5);
      press(ch);
    }
    c.advance(5);
    const enter = press("Enter");
    expect(onScan).toHaveBeenCalledWith("4780000123456");
    expect(enter.preventDefault).toHaveBeenCalled();
    c.advance(500);
    expect(press("Enter").preventDefault).not.toHaveBeenCalled();
    stop();
    expect(listeners.size).toBe(0);
  });
});

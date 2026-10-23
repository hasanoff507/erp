/**
 * vitest (jsdom) setup for @shared/ui: Uzbek i18n (components translate their own default labels) and
 * the browser APIs Radix needs that jsdom lacks (ResizeObserver, pointer capture, scrollIntoView).
 */
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { initI18n } from "@shared/i18n";

initI18n("uz");

class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

const proto = Element.prototype as unknown as Record<string, unknown>;
proto.hasPointerCapture ??= () => false;
proto.setPointerCapture ??= () => undefined;
proto.releasePointerCapture ??= () => undefined;
proto.scrollIntoView ??= () => undefined;

afterEach(() => {
  cleanup();
});

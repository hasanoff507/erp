/**
 * The ONE POS hotkey hook (07 "Klaviatura", 06 §1.3; review G4 UX-01…UX-04). Rules (`hotkeyMatch`, pure):
 * - Alt / Ctrl / Meta combinations match only a hotkey declared with `ctrl: true` (Ctrl or Meta);
 * - F-keys and Escape fire from anywhere (also from text fields); other keys need `allowInInput` inside a
 *   text field (input / textarea / select / contenteditable);
 * - Enter and Space are never taken from a BUTTON, A, [role=button] or [role=radio] — native activation wins;
 * - a target inside a [role=dialog] belongs to that dialog: only the hook whose `scope` element is (inside)
 *   that dialog sees it (a nested approval dialog inside POS-03 is not POS-03's);
 * - `preventDefault` only when a handler ran and did not return `false`; an F-key is always prevented
 *   (F1 help, F5 reload…, UX-04);
 * - an event another listener already prevented is skipped (the scanner wedge prevents its Enter), except
 *   F-keys (the global F-key guard prevents them up front).
 */
import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";

export interface Hotkey {
  /** `KeyboardEvent.key`: "F4", "Enter", "Escape", "Delete", "+", "0"… */
  key: string;
  ctrl?: boolean;
  allowInInput?: boolean;
  /** Return `false` to leave the key to the browser / the focused element (F-keys are still prevented). */
  handler: (event: KeyboardEvent) => unknown;
}

export interface HotkeyOptions {
  enabled?: boolean;
  /** The dialog element that owns these keys (POS-03 / POS-04): its own targets are allowed. */
  scope?: RefObject<HTMLElement | null>;
}

interface ElementLike {
  tagName?: string;
  isContentEditable?: boolean;
  getAttribute?: (name: string) => string | null;
  closest?: (selector: string) => ElementLike | null;
  contains?: (other: unknown) => boolean;
}

export type KeyEventLike = Pick<
  KeyboardEvent,
  "key" | "altKey" | "ctrlKey" | "metaKey" | "defaultPrevented"
> & {
  target: EventTarget | ElementLike | null;
};

const FKEY = /^F([1-9]|1[0-2])$/;
export const isFKey = (key: string): boolean => FKEY.test(key);

const TEXT_INPUT_TYPES = new Set(["text", "search", "number", "tel", "password", "email", "url", ""]);

function asElement(target: unknown): ElementLike | null {
  const el = target as ElementLike | null;
  return el && typeof el.tagName === "string" ? el : null;
}

function inTextField(el: ElementLike | null): boolean {
  if (!el) return false;
  if (el.isContentEditable || el.tagName === "TEXTAREA" || el.tagName === "SELECT") return true;
  if (el.tagName !== "INPUT") return false;
  return TEXT_INPUT_TYPES.has(((el as { type?: string }).type ?? "").toLowerCase());
}

function activatable(el: ElementLike | null): boolean {
  if (!el) return false;
  if (el.tagName === "BUTTON" || el.tagName === "A") return true;
  const role = el.getAttribute?.("role");
  return role === "button" || role === "radio";
}

/** The hotkey that handles `event`, or null (pure — unit-tested). */
export function hotkeyMatch(
  keys: readonly Hotkey[],
  event: KeyEventLike,
  scope: ElementLike | null = null,
): Hotkey | null {
  const fkey = isFKey(event.key);
  if (event.defaultPrevented && !fkey) return null;
  const el = asElement(event.target);
  const dialog = el?.closest?.('[role="dialog"]') ?? null;
  if (dialog && !(scope && (dialog === scope || scope.contains?.(dialog)))) return null;
  if ((event.key === "Enter" || event.key === " ") && activatable(el)) return null;
  const modified = event.ctrlKey || event.metaKey;
  for (const hk of keys) {
    if (hk.key !== event.key) continue;
    if (Boolean(hk.ctrl) !== modified) continue;
    if (event.altKey) continue;
    if (!fkey && event.key !== "Escape" && !hk.allowInInput && inTextField(el)) continue;
    return hk;
  }
  return null;
}

/** Runs the matched handler; returns true when the event was taken. */
export function dispatchHotkey(
  keys: readonly Hotkey[],
  event: KeyboardEvent,
  scope: ElementLike | null = null,
): boolean {
  const hk = hotkeyMatch(keys, event, scope);
  if (!hk) return false;
  const result = hk.handler(event);
  if (result !== false || isFKey(event.key)) event.preventDefault();
  return result !== false;
}

export function useHotkeys(keys: readonly Hotkey[], options: boolean | HotkeyOptions = true): void {
  const opts: HotkeyOptions = typeof options === "boolean" ? { enabled: options } : options;
  const enabled = opts.enabled !== false;
  const ref = useRef(keys);
  const scopeRef = useRef(opts.scope);
  useLayoutEffect(() => {
    ref.current = keys;
    scopeRef.current = opts.scope;
  });
  useEffect(() => {
    if (!enabled) return undefined;
    const onKey = (event: KeyboardEvent) => {
      dispatchHotkey(ref.current, event, (scopeRef.current?.current ?? null) as ElementLike | null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enabled]);
}

/** Digits "0"…"9" as separate hotkeys (PIN / amount pads). */
export function digitKeys(handler: (digit: string) => void): Hotkey[] {
  return Array.from({ length: 10 }, (_, d) => ({ key: String(d), handler: () => handler(String(d)) }));
}

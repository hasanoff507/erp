import { describe, expect, it, vi } from "vitest";

import {
  digitKeys,
  dispatchHotkey,
  hotkeyMatch,
  isFKey,
  type Hotkey,
  type KeyEventLike,
} from "./use-hotkeys.ts";

interface FakeEl {
  tagName: string;
  type?: string;
  role?: string;
  dialog?: FakeEl | null;
  getAttribute(name: string): string | null;
  closest(selector: string): FakeEl | null;
  contains(other: unknown): boolean;
}

function el(tagName: string, opts: { type?: string; role?: string; dialog?: FakeEl | null } = {}): FakeEl {
  const self: FakeEl = {
    tagName,
    ...opts,
    getAttribute: (name) => (name === "role" ? (opts.role ?? null) : null),
    closest: (selector) =>
      selector.includes("dialog") ? (opts.role === "dialog" ? self : (opts.dialog ?? null)) : null,
    contains: (other) => other === self,
  };
  return self;
}

const ev = (key: string, target: unknown = null, extra: Partial<KeyEventLike> = {}): KeyEventLike => ({
  key,
  target: target as KeyEventLike["target"],
  altKey: false,
  ctrlKey: false,
  metaKey: false,
  defaultPrevented: false,
  ...extra,
});

const keys = (...hk: Partial<Hotkey>[]): Hotkey[] =>
  hk.map((h) => ({ key: "Enter", handler: () => true, ...h }));

describe("POS hotkey rules (UX-02 … UX-04)", () => {
  it("Enter / Space on buttons, links, radios keep their native activation", () => {
    const enter = keys({ key: "Enter", allowInInput: true });
    expect(hotkeyMatch(enter, ev("Enter", el("BUTTON")))).toBeNull();
    expect(hotkeyMatch(enter, ev("Enter", el("A")))).toBeNull();
    expect(hotkeyMatch(enter, ev("Enter", el("DIV", { role: "radio" })))).toBeNull();
    expect(hotkeyMatch(keys({ key: " " }), ev(" ", el("BUTTON")))).toBeNull();
    expect(hotkeyMatch(enter, ev("Enter", el("BODY")))).not.toBeNull();
  });

  it("targets inside a dialog belong to that dialog unless it is the hook's scope", () => {
    const dialog = el("DIV", { role: "dialog" });
    const input = el("INPUT", { type: "text", dialog });
    const f4 = keys({ key: "F4" });
    expect(hotkeyMatch(f4, ev("F4", input))).toBeNull();
    expect(
      hotkeyMatch(keys({ key: "Enter", allowInInput: true }), ev("Enter", input), dialog),
    ).not.toBeNull();
    const nested = el("DIV", { role: "dialog" });
    expect(hotkeyMatch(f4, ev("F4", el("INPUT", { dialog: nested })), dialog)).toBeNull();
  });

  it("text fields: F-keys and Escape always, other keys only with allowInInput", () => {
    const input = el("INPUT", { type: "text" });
    expect(hotkeyMatch(keys({ key: "F2" }), ev("F2", input))).not.toBeNull();
    expect(hotkeyMatch(keys({ key: "Escape" }), ev("Escape", input))).not.toBeNull();
    expect(hotkeyMatch(keys({ key: "Delete" }), ev("Delete", input))).toBeNull();
    expect(hotkeyMatch(keys({ key: "Delete", allowInInput: true }), ev("Delete", input))).not.toBeNull();
    expect(
      hotkeyMatch(keys({ key: "Delete" }), ev("Delete", el("INPUT", { type: "checkbox" }))),
    ).not.toBeNull();
  });

  it("modifiers match only ctrl hotkeys; prevented events are skipped except F-keys", () => {
    expect(hotkeyMatch(keys({ key: "p", ctrl: true }), ev("p", null, { ctrlKey: true }))).not.toBeNull();
    expect(hotkeyMatch(keys({ key: "p" }), ev("p", null, { ctrlKey: true }))).toBeNull();
    expect(hotkeyMatch(keys({ key: "Enter" }), ev("Enter", null, { altKey: true }))).toBeNull();
    expect(hotkeyMatch(keys({ key: "Enter" }), ev("Enter", null, { defaultPrevented: true }))).toBeNull();
    expect(hotkeyMatch(keys({ key: "F4" }), ev("F4", null, { defaultPrevented: true }))).not.toBeNull();
  });

  it("preventDefault only when handled; F-keys always (UX-04)", () => {
    const preventDefault = vi.fn();
    const event = { ...ev("Enter"), preventDefault } as unknown as KeyboardEvent;
    expect(dispatchHotkey(keys({ key: "Enter", handler: () => false }), event)).toBe(false);
    expect(preventDefault).not.toHaveBeenCalled();
    const f5 = { ...ev("F5"), preventDefault } as unknown as KeyboardEvent;
    dispatchHotkey(keys({ key: "F5", handler: () => false }), f5);
    expect(preventDefault).toHaveBeenCalledTimes(1);
    expect(isFKey("F12")).toBe(true);
    expect(isFKey("F13")).toBe(false);
    expect(digitKeys(() => undefined).map((k) => k.key)).toEqual([
      "0",
      "1",
      "2",
      "3",
      "4",
      "5",
      "6",
      "7",
      "8",
      "9",
    ]);
  });
});

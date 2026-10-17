/**
 * UX-11: the card block adds no window-level key handler — Esc belongs to the host dialog
 * (`PaymentDialog.onEscapeKeyDown`, UX-01) and still closes a nested dialog (manager PIN).
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

describe("CardPayment keyboard (UX-11)", () => {
  it("does not install a global Escape blocker", () => {
    const source = readFileSync(fileURLToPath(new URL("./CardPayment.tsx", import.meta.url)), "utf8");
    expect(source).not.toMatch(/addEventListener\(\s*["']keydown["']/);
    expect(source).not.toContain("stopPropagation");
  });
});

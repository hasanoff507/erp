/**
 * WEB-09 (R3): POS debt controls are ≥ 48 px touch targets (08 §2) — POS-13 promise-date quick buttons
 * (7 / 14 / 30) and date input (POS-03/06 «Tasdiq so'rash» — `sale/ui/touch-size.test.tsx`).
 * `size="pos"` = h-14, inputs h-12.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PromiseDatePicker } from "./PromiseDatePicker.tsx";

const SMALL = /\bh-(?:[1-9]|10|11)\b/;

describe("POS debt controls touch size (WEB-09)", () => {
  it("test_web09_pos_debt_controls_touch_size", () => {
    const picker = renderToStaticMarkup(
      <PromiseDatePicker
        value=""
        today="2026-10-18"
        label="Yangi va'da"
        dayLabels={["7 kun", "14 kun", "30 kun"]}
        dateFor={(n) => `2026-10-${18 + n}`}
        onChange={() => undefined}
      />,
    );
    const buttons = picker.match(/<button[^>]*>/g) ?? [];
    expect(buttons).toHaveLength(3);
    for (const b of buttons) {
      expect(b).toContain("h-14");
      expect(b).not.toMatch(SMALL);
    }
    const input = picker.match(/<input[^>]*>/)?.[0] ?? "";
    expect(input).toContain("h-12");
    expect(input).not.toMatch(SMALL);
  });
});

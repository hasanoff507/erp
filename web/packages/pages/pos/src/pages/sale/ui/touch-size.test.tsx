/** WEB-09 (R3): POS-03/06 «Tasdiq so'rash» is a ≥ 48 px touch target (08 §2) — `size="pos"` (h-14). */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DebtAskApprovalButton } from "./DebtSalePanel.tsx";

describe("POS debt sale controls touch size (WEB-09)", () => {
  it("test_web09_pos_debt_controls_touch_size", () => {
    const ask = renderToStaticMarkup(<DebtAskApprovalButton label="Tasdiq so'rash" onClick={() => undefined} />);
    expect(ask).toContain("h-14");
    expect(ask).not.toMatch(/\bh-(?:[1-9]|10|11)\b/);
  });
});

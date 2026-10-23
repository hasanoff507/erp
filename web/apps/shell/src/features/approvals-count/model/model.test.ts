import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { $approvalsPending, approvalsCountRequested, badgeText, fetchPendingCountFx } from "./index.ts";

describe("WEB-12 pending approvals badge", () => {
  it("badge text: hidden for 0 / unknown, capped at 99+", () => {
    expect(badgeText(null)).toBeNull();
    expect(badgeText(0)).toBeNull();
    expect(badgeText(3)).toBe("3");
    expect(badgeText(100)).toBe("99+");
  });

  it("no sidebar showing the item → no request", async () => {
    let calls = 0;
    const s = fork({
      handlers: [
        [
          fetchPendingCountFx,
          () => {
            calls += 1;
            return 2;
          },
        ],
      ],
    });
    await allSettled(approvalsCountRequested, { scope: s });
    expect(calls).toBe(0);
    expect(s.getState($approvalsPending)).toBeNull();
  });
});

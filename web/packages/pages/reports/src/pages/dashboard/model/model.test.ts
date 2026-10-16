import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { $period, pageMounted, periodChanged } from "./index.ts";

describe("dashboard model (BO-02)", () => {
  it("defaults to today, switches period and resets on mount", async () => {
    const scope = fork();
    expect(scope.getState($period)).toBe("today");

    await allSettled(periodChanged, { scope, params: "week" });
    expect(scope.getState($period)).toBe("week");

    await allSettled(pageMounted, { scope });
    expect(scope.getState($period)).toBe("today");
  });
});

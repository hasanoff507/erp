import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { $isOnline, offlineDetected, onlineDetected } from "./index.ts";

describe("$isOnline — 24 §3", () => {
  it("a server answer (onOnline hook → onlineDetected) clears the offline flag", async () => {
    const scope = fork();
    await allSettled(offlineDetected, { scope });
    expect(scope.getState($isOnline)).toBe(false);
    await allSettled(onlineDetected, { scope });
    expect(scope.getState($isOnline)).toBe(true);
  });
});

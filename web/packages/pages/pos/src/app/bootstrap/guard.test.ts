import { describe, expect, it } from "vitest";

import { globalKeysFor, guardTarget } from "./PosBootstrap.tsx";

const base = {
  pathname: "/pos/sale",
  search: "",
  status: "ready" as const,
  hasShift: true,
  canOpenShift: true,
};

describe("POS route guard (contracts/pos-session.md)", () => {
  it("waits while loading and lets a ready cashier with a shift sell", () => {
    expect(guardTarget({ ...base, status: "loading" })).toBeNull();
    expect(guardTarget(base)).toBeNull();
  });

  it("no device / no PIN → POS-01 with next", () => {
    expect(guardTarget({ ...base, status: "no_device" })).toBe("/pos/login?next=%2Fpos%2Fsale");
    expect(guardTarget({ ...base, status: "locked", pathname: "/pos/sync" })).toBe(
      "/pos/login?next=%2Fpos%2Fsync",
    );
  });

  it("POS-01 and POS-16 are always reachable", () => {
    expect(guardTarget({ ...base, status: "no_device", pathname: "/pos/login" })).toBeNull();
    expect(guardTarget({ ...base, status: "locked", pathname: "/pos/settings/devices" })).toBeNull();
  });

  it("cashier with shift.open but no open shift → POS-01 step 2; storekeeper stays", () => {
    expect(guardTarget({ ...base, hasShift: false })).toBe("/pos/login?next=%2Fpos%2Fsale");
    expect(guardTarget({ ...base, hasShift: false, canOpenShift: false })).toBeNull();
    expect(guardTarget({ ...base, hasShift: false, pathname: "/pos/sync" })).toBeNull();
  });
});

describe("warehouse + equipment routes (contracts/pos-wh-routes.md)", () => {
  it("POS-16 needs no cashier and no device; warehouse needs a cashier but no shift", () => {
    expect(guardTarget({ ...base, status: "no_device", pathname: "/pos/settings/devices" })).toBeNull();
    expect(guardTarget({ ...base, status: "ready", hasShift: false, pathname: "/pos/warehouse" })).toBeNull();
    expect(
      guardTarget({ ...base, status: "ready", hasShift: false, pathname: "/pos/warehouse/transfer" }),
    ).toBeNull();
    expect(guardTarget({ ...base, status: "locked", pathname: "/pos/warehouse/receive" })).toBe(
      "/pos/login?next=%2Fpos%2Fwarehouse%2Freceive",
    );
  });

  it("global keys: F9 stays with the warehouse screens; overlays own the keyboard", () => {
    expect(globalKeysFor("/pos/sale").map(([k]) => k)).toEqual(["F6", "F7", "F8", "F9", "F12"]);
    expect(globalKeysFor("/pos/warehouse/stocktake").map(([k]) => k)).toEqual(["F6", "F7", "F8", "F12"]);
    expect(globalKeysFor("/pos/sale/credit")).toEqual([]);
    expect(globalKeysFor("/pos/sale/payment")).toEqual([]);
  });
});

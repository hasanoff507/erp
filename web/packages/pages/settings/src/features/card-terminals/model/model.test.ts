import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import type { CardTerminalOut } from "@shared/models";

import {
  $cardTerminals,
  cardTerminalsOpened,
  fetchCardTerminalsFx,
  isPrivateIpv4,
  terminalsOf,
} from "./index.ts";

const term = (over: Partial<CardTerminalOut>): CardTerminalOut =>
  ({
    id: "t",
    branch_id: "b-1",
    cash_register_id: "cr-1",
    name: "T1",
    vendor: "fake",
    model: null,
    adapter: "fake",
    driver: "fake",
    agent_id: null,
    local_id: null,
    host: null,
    port: null,
    vendor_terminal_ref: null,
    tid: null,
    mid: null,
    acquirer_counterparty_id: null,
    status: "active",
    is_default: false,
    capabilities: {},
    health_status: "unknown",
    health_checked_at: null,
    version: 1,
    ...over,
  });

describe("BO-12 card terminals model (18 §16a.5)", () => {
  it("only RFC 1918 IPv4 hosts are accepted (15 §9.3)", () => {
    for (const ok of ["10.0.0.1", "172.16.5.4", "172.31.255.255", "192.168.1.40"])
      expect(isPrivateIpv4(ok)).toBe(true);
    for (const bad of [
      "8.8.8.8",
      "172.32.0.1",
      "192.169.0.1",
      "10.0.0",
      "10.0.0.256",
      "a.b.c.d",
      "10x0.0.1",
    ]) {
      expect(isPrivateIpv4(bad)).toBe(false);
    }
  });

  it("register cell: the default terminal first, archived ones hidden", () => {
    const list = [
      term({ id: "a", name: "A" }),
      term({ id: "b", name: "B", is_default: true }),
      term({ id: "c", status: "archived" }),
      term({ id: "d", cash_register_id: "cr-2" }),
    ];
    expect(terminalsOf(list, "cr-1").map((t) => t.id)).toEqual(["b", "a"]);
  });

  it("opening a branch loads its terminals", async () => {
    const scope = fork({
      handlers: [
        [
          fetchCardTerminalsFx,
          () =>
            Promise.resolve({
              items: [term({ id: "x" }), term({ id: "y", branch_id: "b-2" })],
              total: 2,
              page: 1,
              size: 200,
            }),
        ],
      ],
    });
    await allSettled(cardTerminalsOpened, { scope, params: "b-1" });
    expect(scope.getState($cardTerminals).map((t) => t.id)).toEqual(["x"]);
  });
});

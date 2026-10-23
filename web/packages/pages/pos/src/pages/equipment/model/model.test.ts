/* eslint-disable @typescript-eslint/require-await -- the fakes implement async ports */
import { allSettled, fork } from "effector";
import { describe, expect, it, vi } from "vitest";

import type { AgentClient } from "@shared/lib/agent";
import type { PrinterEnvironment, SerialLike } from "@shared/lib/printer";
import type { Rasterizer } from "@shared/lib/receipt";
import { INITIAL_AGENT_STATUS } from "@shared/state/device";

import {
  $autoDetected,
  $catalogView,
  $form,
  $formErrors,
  $lastTest,
  $pairState,
  catalogViewChanged,
  configureEquipment,
  describeScan,
  detectRequested,
  equipmentOpened,
  lanAddressChanged,
  pairRequested,
  saveRequested,
  scaleRows,
  testRequested,
  transportChanged,
  type EquipmentDeps,
} from "./index.ts";

const rasterizer: Rasterizer = {
  rasterize: (_segment, width) => ({ width, height: 1, data: new Uint8Array(width / 8).fill(0xff) }),
};

function fakeSerial() {
  const written: Uint8Array[] = [];
  const port = {
    writable: {
      getWriter: () => ({
        write: (chunk: Uint8Array) => {
          written.push(chunk.slice());
          return Promise.resolve();
        },
        releaseLock: () => undefined,
      }),
    } as unknown as WritableStream<Uint8Array>,
    open: () => Promise.resolve(),
    close: () => Promise.resolve(),
  };
  let granted = false;
  const serial: SerialLike = {
    getPorts: () => Promise.resolve(granted ? [port] : []),
    requestPort: () => {
      granted = true;
      return Promise.resolve(port);
    },
  };
  return { serial, written };
}

function memory(initial: Record<string, unknown> = {}) {
  const map = new Map(Object.entries(initial));
  return {
    map,
    get: async (k: string) => map.get(k),
    set: async (k: string, v: unknown) => void map.set(k, v),
  };
}

const bytesOf = (chunks: Uint8Array[]) => {
  const all: number[] = [];
  for (const c of chunks) all.push(...c);
  return all;
};
const contains = (hay: number[], needle: number[]) =>
  hay.some((_, i) => needle.every((b, j) => hay[i + j] === b));

function setup(over: Partial<EquipmentDeps> = {}) {
  const { serial, written } = fakeSerial();
  const store = memory();
  const env: PrinterEnvironment = { platform: "windows", serial, window: undefined, fetch: undefined };
  const pair = vi.fn(async () => undefined);
  const deps: Partial<EquipmentDeps> = {
    store,
    env: () => env,
    agentState: () => INITIAL_AGENT_STATUS,
    agent: () => ({ pair, probe: async () => INITIAL_AGENT_STATUS }) as unknown as AgentClient,
    templates: async () => null,
    deviceId: () => "dev-1",
    now: () => new Date("2026-10-17T07:05:00Z"),
    rasterizer,
    ...over,
  };
  return { deps, store, written, pair };
}

describe("POS-16 helpers", () => {
  it("scale rows with a worked example (defaults 22 = weight, 21 = amount)", () => {
    const rows = scaleRows(null);
    expect(rows.map((r) => [r.prefixes.join(","), r.kind, r.decoded])).toEqual([
      ["22", "WEIGHT", "1.250"],
      ["21", "AMOUNT", "11875.00"],
    ]);
    expect(rows[0]?.example).toBe("2212345012503");
  });

  it("scanner test: EAN-13, DataMatrix, weight label", () => {
    expect(describeScan("4780000123454", null).kind).toBe("ean13");
    expect(describeScan("0104600000000015215abc\u001d93x", null).kind).toBe("datamatrix");
    expect(describeScan("2212345012503", null)).toEqual({
      code: "2212345012503",
      kind: "weight",
      weight: { productCode: "12345", value: "1.250", valueKind: "WEIGHT" },
    });
  });
});

describe("POS-16 model — QT-M01-22 (unit part)", () => {
  it("detect (Web Serial) → test receipt: cp866 ESC t 17 + raster GS v 0 for Қ/Ғ/Ҳ; save keeps printer.* locally", async () => {
    const { deps, store, written } = setup();
    const scope = fork();
    await allSettled(configureEquipment, { scope, params: deps });
    await allSettled(equipmentOpened, { scope });
    expect(scope.getState($form).transport).toBeNull();
    expect(scope.getState($autoDetected)).toBeNull(); // nothing granted, no window → nothing detected

    await allSettled(detectRequested, { scope });
    expect(scope.getState($form).transport).toBe("webserial");
    await allSettled(testRequested, { scope });
    expect(scope.getState($lastTest)).toEqual({
      ok: true,
      at: "2026-10-17T07:05:00.000Z",
      mode: "raster",
      code: null,
    });
    const bytes = bytesOf(written);
    expect(contains(bytes, [0x1b, 0x74, 0x11])).toBe(true); // ESC t 17 = cp866
    expect(contains(bytes, [0x1d, 0x76, 0x30])).toBe(true); // GS v 0 raster band

    await allSettled(catalogViewChanged, { scope, params: "list" });
    await allSettled(saveRequested, { scope });
    expect(store.map.get("printer.transport")).toBe("webserial");
    expect(store.map.get("printer.codepage")).toBe("cp866");
    expect(store.map.get("pos.catalog_view")).toBe("list");
    expect(scope.getState($catalogView)).toBe("list");
  });

  it("LAN transports need a private IPv4; a failed print is reported with its PrinterError code", async () => {
    const { deps } = setup();
    const scope = fork();
    await allSettled(configureEquipment, { scope, params: deps });
    await allSettled(equipmentOpened, { scope });
    await allSettled(transportChanged, { scope, params: "agent_raw" });
    expect(scope.getState($formErrors)).toEqual(["lan_address_invalid"]);
    await allSettled(lanAddressChanged, { scope, params: "8.8.8.8:9100" });
    expect(scope.getState($formErrors)).toEqual(["lan_address_invalid"]);
    await allSettled(lanAddressChanged, { scope, params: "192.168.1.50:9100" });
    expect(scope.getState($formErrors)).toEqual([]);
    await allSettled(testRequested, { scope });
    expect(scope.getState($lastTest)).toMatchObject({ ok: false, code: "agent_unavailable" });
  });

  it("agent pairing: 6 digits with this device id", async () => {
    const { deps, pair } = setup();
    const scope = fork();
    await allSettled(configureEquipment, { scope, params: deps });
    await allSettled(pairRequested, { scope, params: "12345" });
    expect(pair).not.toHaveBeenCalled();
    await allSettled(pairRequested, { scope, params: "482915" });
    expect(pair).toHaveBeenCalledWith("482915", "dev-1");
    expect(scope.getState($pairState)).toBe("paired");
  });
});

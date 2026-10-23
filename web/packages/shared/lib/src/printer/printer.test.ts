import { describe, expect, it, vi } from "vitest";

import { AgentError } from "#/agent/index.ts";
import { type Rasterizer, type ReceiptDoc, TEST_RECEIPT_TEXT, testReceiptDoc } from "#/receipt/index.ts";

import {
  availableTransports,
  type CloudPrintApi,
  createPrinterPort,
  DEFAULT_PRINTER_SETTINGS,
  detectPrinterTransport,
  eposRequestBody,
  loadPrinterSettings,
  parseLanAddress,
  PRINTER_SETTING_KEYS,
  PrinterError,
  type PrinterEnvironment,
  type PrinterSettings,
  type PrintWindow,
  requestPrinterDevice,
  savePrinterSettings,
  type SerialLike,
  systemPrint,
  type UsbLike,
  webprntRequestBody,
} from "./index.ts";

const rasterizer: Rasterizer = {
  rasterize: (_segment, width) => ({ width, height: 1, data: new Uint8Array(width / 8).fill(0xff) }),
};

function memorySettings(initial: Record<string, unknown> = {}) {
  const map = new Map(Object.entries(initial));
  return {
    map,
    get: (key: string) => Promise.resolve(map.get(key)),
    set: (key: string, value: unknown) => {
      map.set(key, value);
      return Promise.resolve();
    },
  };
}

function fakeSerial(granted: boolean) {
  const written: Uint8Array[] = [];
  const port = {
    writable: {
      getWriter: () => ({
        write: (chunk: Uint8Array) => {
          written.push(chunk.slice());
          return Promise.resolve();
        },
        releaseLock: vi.fn(),
      }),
    } as unknown as WritableStream<Uint8Array>,
    open: vi.fn(() => Promise.resolve()),
    close: vi.fn(() => Promise.resolve()),
  };
  const serial: SerialLike = {
    getPorts: () => Promise.resolve(granted ? [port] : []),
    requestPort: vi.fn(() => Promise.resolve(port)),
  };
  const bytes = () => Uint8Array.from(written.flatMap((c) => Array.from(c)));
  return { serial, port, bytes };
}

function fakeUsb(claimFails = false) {
  const sent: Uint8Array[] = [];
  const device = {
    opened: false,
    configuration: {
      interfaces: [
        {
          interfaceNumber: 0,
          alternate: {
            interfaceClass: 0x07,
            endpoints: [{ endpointNumber: 2, direction: "out" as const, type: "bulk" as const }],
          },
        },
      ],
    },
    open: vi.fn(() => Promise.resolve()),
    close: vi.fn(() => Promise.resolve()),
    selectConfiguration: vi.fn(() => Promise.resolve()),
    claimInterface: vi.fn(() =>
      claimFails
        ? Promise.reject(new DOMException("Unable to claim interface.", "SecurityError"))
        : Promise.resolve(),
    ),
    releaseInterface: vi.fn(() => Promise.resolve()),
    transferOut: vi.fn((_ep: number, data: Uint8Array) => {
      sent.push(data.slice());
      return Promise.resolve({ status: "ok" });
    }),
  };
  const usb: UsbLike = {
    getDevices: () => Promise.resolve([device]),
    requestDevice: vi.fn(() => Promise.resolve(device)),
  };
  return { usb, device, sent };
}

const settings = (patch: Partial<PrinterSettings>): PrinterSettings => ({
  ...DEFAULT_PRINTER_SETTINGS,
  ...patch,
});
const desktop = (patch: Partial<PrinterEnvironment> = {}): PrinterEnvironment => ({
  platform: "windows",
  ...patch,
});
const TEST_DOC: ReceiptDoc = testReceiptDoc({
  at: "2026-10-16T10:00:00",
  transport: "webserial",
  paperWidth: 58,
});

describe("printer settings (POS-16, erp-device)", () => {
  it("loads defaults and validates stored values; saves only given keys", async () => {
    expect(await loadPrinterSettings(memorySettings())).toEqual(DEFAULT_PRINTER_SETTINGS);
    const store = memorySettings({
      [PRINTER_SETTING_KEYS.transport]: "webusb",
      [PRINTER_SETTING_KEYS.paperWidth]: 80,
      [PRINTER_SETTING_KEYS.renderMode]: "bogus",
      [PRINTER_SETTING_KEYS.lanAddress]: "192.168.1.50:9100",
    });
    expect(await loadPrinterSettings(store)).toMatchObject({
      transport: "webusb",
      paperWidth: 80,
      renderMode: "auto",
      lanAddress: "192.168.1.50:9100",
    });
    await savePrinterSettings(store, { transport: "webserial", renderMode: "raster" });
    expect(store.map.get("printer.transport")).toBe("webserial");
    expect(store.map.get("printer.render_mode")).toBe("raster");
    expect(store.map.get("printer.paper_width")).toBe(80);
  });

  it("LAN address: private IPv4 only, default port", () => {
    expect(parseLanAddress("192.168.1.50", 9100)).toEqual({ host: "192.168.1.50", port: 9100 });
    expect(parseLanAddress("10.0.0.7:8008", 9100)).toEqual({ host: "10.0.0.7", port: 8008 });
    expect(parseLanAddress("172.16.4.1:80", 9100)).toEqual({ host: "172.16.4.1", port: 80 });
    for (const bad of [
      "8.8.8.8",
      "172.32.0.1",
      "printer.local",
      "192.168.1.300",
      "192.168.1.5:70000",
      "192.168.1.5:1:2",
      "",
    ]) {
      expect(parseLanAddress(bad, 9100)).toBeNull();
    }
  });
});

describe("transport matrix and auto-detect (24 §6.1–§6.2, US-M01-07)", () => {
  it("platform availability: iOS cloud only, Android without the agent", () => {
    expect(availableTransports({ platform: "ios" })).toEqual(["cloud"]);
    const { serial } = fakeSerial(false);
    expect(availableTransports({ platform: "android", serial, window: {} as PrintWindow })).not.toContain(
      "agent_raw",
    );
    expect(availableTransports(desktop({ serial, window: {} as PrintWindow }))).toEqual([
      "agent_raw",
      "webserial",
      "http_epos",
      "http_webprnt",
      "cloud",
      "system_print",
    ]);
  });

  it("order: agent_raw → webserial → webusb → http → cloud → system_print; iOS: cloud or null", async () => {
    const online = { status: "online" as const, capabilities: { print: { enabled: true } } };
    const win = {} as PrintWindow;
    const base = { transport: null, lanAddress: null, cloudId: null };
    const serial = fakeSerial(true).serial;
    const usb = fakeUsb().usb;
    expect(
      await detectPrinterTransport({
        settings: { ...base, lanAddress: "192.168.1.9" },
        agentStatus: online,
        env: desktop({ serial, usb, window: win }),
      }),
    ).toBe("agent_raw");
    expect(
      await detectPrinterTransport({
        settings: base,
        agentStatus: online,
        env: desktop({ serial, usb, window: win }),
      }),
    ).toBe("webserial");
    expect(
      await detectPrinterTransport({
        settings: base,
        env: desktop({ serial: fakeSerial(false).serial, usb, window: win }),
      }),
    ).toBe("webusb");
    expect(
      await detectPrinterTransport({
        settings: { ...base, transport: "http_epos", lanAddress: "192.168.1.9" },
        env: desktop({ window: win }),
      }),
    ).toBe("http_epos");
    expect(
      await detectPrinterTransport({ settings: { ...base, cloudId: "cp1" }, env: desktop({ window: win }) }),
    ).toBe("cloud");
    expect(await detectPrinterTransport({ settings: base, env: desktop({ window: win }) })).toBe(
      "system_print",
    );
    expect(
      await detectPrinterTransport({ settings: base, env: { platform: "ios", window: win } }),
    ).toBeNull();
    expect(
      await detectPrinterTransport({ settings: { ...base, cloudId: "cp1" }, env: { platform: "ios" } }),
    ).toBe("cloud");
  });

  it("«PRINTERNI ANIQLASH»: Web Serial picker first, WebUSB next, else system printer", async () => {
    const { serial } = fakeSerial(false);
    expect(await requestPrinterDevice("auto", desktop({ serial }))).toBe("webserial");
    const cancelSerial: SerialLike = {
      getPorts: () => Promise.resolve([]),
      requestPort: () => Promise.reject(new DOMException("none", "NotFoundError")),
    };
    const { usb } = fakeUsb();
    expect(await requestPrinterDevice("auto", desktop({ serial: cancelSerial, usb }))).toBe("webusb");
    expect(await requestPrinterDevice("auto", desktop({ window: {} as PrintWindow }))).toBe("system_print");
    await expect(requestPrinterDevice("webbluetooth", desktop())).rejects.toMatchObject({
      code: "not_supported",
    });
  });
});

describe("PrinterPort adapters", () => {
  it("test_qt_m01_22_webserial_test_receipt: ESC t 17 + raster bytes reach the serial port", async () => {
    const { serial, bytes, port } = fakeSerial(true);
    const printer = createPrinterPort(settings({ transport: "webserial" }), {
      env: desktop({ serial }),
      rasterizer,
    });
    const result = await printer.printReceipt(TEST_DOC);
    expect(result).toEqual({ transport: "webserial", mode: "raster" });
    const out = bytes();
    expect(Array.from(out.slice(0, 5))).toEqual([0x1b, 0x40, 0x1b, 0x74, 17]);
    expect(Array.from(out.slice(-4))).toEqual([0x1d, 0x56, 66, 0]);
    expect(port.open).toHaveBeenCalledWith({ baudRate: 9600 });
    expect(port.close).toHaveBeenCalled();
    expect(await printer.status()).toEqual({ transport: "webserial", state: "ready" });
    expect(TEST_DOC.extraLines).toContain(TEST_RECEIPT_TEXT);
  });

  it("WebUSB: bulk OUT of the printer-class interface; claim failure → webusb_claim_failed", async () => {
    const ok = fakeUsb();
    await createPrinterPort(settings({ transport: "webusb", renderMode: "text" }), {
      env: desktop({ usb: ok.usb }),
    }).printReceipt(TEST_DOC);
    expect(ok.device.claimInterface).toHaveBeenCalledWith(0);
    expect(ok.device.transferOut.mock.calls[0]?.[0]).toBe(2);
    expect(ok.sent.length).toBeGreaterThan(0);
    const bad = fakeUsb(true);
    const error = await createPrinterPort(settings({ transport: "webusb", renderMode: "text" }), {
      env: desktop({ usb: bad.usb }),
    })
      .printReceipt(TEST_DOC)
      .catch((e: unknown) => e);
    expect(error).toBeInstanceOf(PrinterError);
    expect(error).toMatchObject({
      code: "webusb_claim_failed",
      messageKey: "pos:equipment.printer.errors.webusb_claim_failed",
    });
  });

  it("agent_raw: bytes to the agent with the LAN address; unpaired agent → agent_unpaired", async () => {
    const printRaw = vi.fn(() => Promise.resolve());
    const port = createPrinterPort(settings({ transport: "agent_raw", lanAddress: "192.168.1.50" }), {
      agent: { printRaw },
      agentState: () => ({ status: "online", capabilities: { print: { enabled: true } } }),
      env: desktop(),
      rasterizer,
    });
    expect(await port.printReceipt(TEST_DOC)).toEqual({ transport: "agent_raw", mode: "raster" });
    expect(printRaw).toHaveBeenCalledWith(
      expect.objectContaining({ printerLocalId: "192.168.1.50:9100", encoding: "raster" }),
    );
    expect(await port.status()).toEqual({ transport: "agent_raw", state: "ready" });
    const unpaired = createPrinterPort(settings({ transport: "agent_raw", lanAddress: "192.168.1.50" }), {
      agent: {
        printRaw: () => Promise.reject(new AgentError("unpaired", "AGENT_NOT_PAIRED", { status: 401 })),
      },
      env: desktop(),
      rasterizer,
    });
    await expect(unpaired.printReceipt(TEST_DOC)).rejects.toMatchObject({ code: "agent_unpaired" });
    expect(await unpaired.status()).toMatchObject({ state: "unavailable", code: "agent_unavailable" });
  });

  it("B5 agent_raw: 404 → printer_not_registered, 503 PRINTER_UNREACHABLE → printer_unreachable (21 §16.1)", async () => {
    const make = (status: number, code: string) =>
      createPrinterPort(settings({ transport: "agent_raw", lanAddress: "192.168.1.50:9100" }), {
        agent: { printRaw: () => Promise.reject(new AgentError("http", code, { status })) },
        env: desktop(),
        rasterizer,
      });
    await expect(make(404, "NOT_FOUND").printReceipt(TEST_DOC)).rejects.toMatchObject({
      code: "printer_not_registered",
      messageKey: "pos:equipment.printer.errors.printer_not_registered",
    });
    await expect(make(503, "PRINTER_UNREACHABLE").printReceipt(TEST_DOC)).rejects.toMatchObject({
      code: "printer_unreachable",
    });
    await expect(make(413, "FILE_TOO_LARGE").printReceipt(TEST_DOC)).rejects.toMatchObject({
      code: "write_failed",
    });
  });

  it("http_epos posts ePOS-Print with the ESC/POS bytes as hex; http_webprnt sends a bitimage", async () => {
    expect(eposRequestBody(Uint8Array.from([0x1b, 0x40]))).toContain("<command>1b40</command>");
    const fetch = vi.fn((_url: string, _init: RequestInit) =>
      Promise.resolve(new Response('<response success="true" code=""/>')),
    );
    const epos = createPrinterPort(
      settings({ transport: "http_epos", lanAddress: "192.168.1.60", renderMode: "text" }),
      { env: desktop({ fetch }) },
    );
    expect(await epos.printReceipt(TEST_DOC)).toEqual({ transport: "http_epos", mode: "text" });
    expect(fetch.mock.calls[0]?.[0]).toBe(
      "http://192.168.1.60:80/cgi-bin/epos/service.cgi?devid=local_printer&timeout=10000",
    );
    const failing = createPrinterPort(settings({ transport: "http_epos", lanAddress: "192.168.1.60" }), {
      env: desktop({ fetch: () => Promise.reject(new TypeError("blocked by CSP")) }),
      rasterizer,
    });
    await expect(failing.printReceipt(TEST_DOC)).rejects.toMatchObject({ code: "http_failed" });
    const body = webprntRequestBody({ width: 8, height: 1, data: Uint8Array.from([0xff]) });
    expect(body).toContain('&lt;bitimage width="8" height="1"&gt;/w==&lt;/bitimage&gt;');
  });

  it("cloud: without the server queue (Bosqich 5) → cloud_unavailable; with an API the raster job is queued", async () => {
    const noApi = createPrinterPort(settings({ transport: "cloud", cloudId: "cp1" }), {
      env: { platform: "ios" },
      rasterizer,
    });
    await expect(noApi.printReceipt(TEST_DOC)).rejects.toMatchObject({ code: "cloud_unavailable" });
    expect(await noApi.status()).toMatchObject({ state: "unavailable", code: "cloud_unavailable" });
    const submit = vi.fn<CloudPrintApi["submit"]>(() => Promise.resolve({ id: "j1", status: "queued" }));
    const cloud: CloudPrintApi = { submit, status: () => Promise.resolve({ online: true }) };
    const port = createPrinterPort(settings({ transport: "cloud", cloudId: "cp1" }), {
      env: { platform: "ios" },
      cloud,
      rasterizer,
      newId: () => "j1",
    });
    expect(await port.printReceipt(TEST_DOC)).toEqual({ transport: "cloud", mode: "cloud" });
    expect(submit.mock.calls[0]?.[0]).toMatchObject({
      id: "j1",
      cloud_printer_id: "cp1",
      kind: "test",
      raster: { width_dots: 384 },
    });
    expect(await port.status()).toEqual({ transport: "cloud", state: "ready" });
  });

  it("not configured → not_configured (POS-04 offers the electronic receipt)", async () => {
    const port = createPrinterPort(DEFAULT_PRINTER_SETTINGS);
    await expect(port.printReceipt(TEST_DOC)).rejects.toMatchObject({ code: "not_configured" });
    expect(await port.status()).toMatchObject({ state: "not_configured" });
  });
});

describe("system print (CSP-safe)", () => {
  it("hides the page, prints the receipt element, restores everything", async () => {
    const pageChild = { style: { display: "block" } };
    const appended: unknown[] = [];
    const root = { append: (el: unknown) => appended.push(el), remove: vi.fn() };
    const listeners: (() => void)[] = [];
    const win = {
      document: {
        body: { children: [pageChild], append: vi.fn() },
        createElement: () => root,
      },
      print: vi.fn(() => {
        expect(pageChild.style.display).toBe("none");
        for (const l of listeners) l();
      }),
      addEventListener: (_t: string, l: () => void) => listeners.push(l),
      removeEventListener: vi.fn(),
    } as unknown as PrintWindow;
    const receipt = {} as HTMLElement;
    await systemPrint(win, receipt);
    expect(appended).toEqual([receipt]);
    expect(root.remove).toHaveBeenCalled();
    expect(pageChild.style.display).toBe("block");
  });
});

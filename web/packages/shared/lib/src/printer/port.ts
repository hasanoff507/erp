/**
 * `createPrinterPort` + transport availability / auto-detection (24 §6.1–§6.2, US-M01-07, 07 POS-16).
 */
import { currentPlatform, type InstallPlatform } from "#/platform/index.ts";
import {
  createCanvasRasterizer,
  encodeEscPos,
  layoutReceipt,
  type Rasterizer,
  type ReceiptDoc,
  renderReceiptElement,
} from "#/receipt/index.ts";

import { bitmapToBase64, layoutToBitmap } from "./bitmap.ts";
import { type CloudPrintApi, cloudSubmit, type PrintWindow, systemPrint } from "./cloud-system.ts";
import { type AgentPrintClient, agentRawPrint, eposPrint, type FetchLike, webprntPrint } from "./network.ts";
import { parseLanAddress } from "./settings.ts";
import {
  type ByteSink,
  type LabelDoc,
  PrinterError,
  type PrinterPort,
  type PrinterSettings,
  type PrinterStatus,
  type PrinterTransport,
  type PrintResult,
} from "./types.ts";
import {
  type BluetoothLike,
  requestDevice,
  type SerialLike,
  type UsbLike,
  webBluetoothSink,
  webSerialSink,
  webUsbSink,
} from "./web-devices.ts";

export interface PrinterEnvironment {
  platform: InstallPlatform | null;
  serial?: SerialLike | undefined;
  usb?: UsbLike | undefined;
  bluetooth?: BluetoothLike | undefined;
  window?: PrintWindow | undefined;
  fetch?: FetchLike | undefined;
}

/** The running browser's capabilities. */
export function browserPrinterEnvironment(): PrinterEnvironment {
  const nav = (typeof navigator === "undefined" ? {} : navigator) as {
    serial?: SerialLike;
    usb?: UsbLike;
    bluetooth?: BluetoothLike;
  };
  return {
    platform: currentPlatform(),
    serial: nav.serial,
    usb: nav.usb,
    bluetooth: nav.bluetooth,
    window: typeof window === "undefined" ? undefined : window,
    fetch: typeof fetch === "undefined" ? undefined : (input, init) => fetch(input, init),
  };
}

/** Agent state as `$agentStatus` holds it (structural — @shared/lib does not import @shared/state). */
export interface AgentPrintState {
  status: "online" | "offline" | "not_installed" | "unpaired";
  capabilities: { print: { enabled: boolean } };
}

/**
 * Transports this platform can use (POS-16 radio buttons). iOS: `cloud` only (24 §6.2 — no WebUSB/Serial/BLE,
 * no agent, http LAN blocked by mixed content). Android: no agent. Windows desktop: everything.
 */
export function availableTransports(
  env: PrinterEnvironment = browserPrinterEnvironment(),
): PrinterTransport[] {
  if (env.platform === "ios") return ["cloud"];
  const list: PrinterTransport[] = [];
  if (env.platform !== "android") list.push("agent_raw");
  if (env.serial) list.push("webserial");
  if (env.usb) list.push("webusb");
  if (env.bluetooth) list.push("webbluetooth");
  list.push("http_epos", "http_webprnt", "cloud");
  if (env.window) list.push("system_print");
  return list;
}

/**
 * Non-interactive auto pick (24 §6.1): `agent_raw` (agent online with `print` + LAN address) → `webserial`
 * (granted port) → `webusb` (granted printer) → `http_*` (saved LAN address) → `cloud` (cloud id) → `system_print`.
 * iOS: `cloud` or null (electronic receipt fallback).
 */
export async function detectPrinterTransport(input: {
  settings: Pick<PrinterSettings, "transport" | "lanAddress" | "cloudId">;
  agentStatus?: AgentPrintState | null;
  env?: PrinterEnvironment;
}): Promise<PrinterTransport | null> {
  const env = input.env ?? browserPrinterEnvironment();
  const { settings, agentStatus } = input;
  const available = availableTransports(env);
  if (env.platform === "ios") return settings.cloudId ? "cloud" : null;
  if (
    available.includes("agent_raw") &&
    agentStatus?.status === "online" &&
    agentStatus.capabilities.print.enabled &&
    parseLanAddress(settings.lanAddress, 9100)
  ) {
    return "agent_raw";
  }
  if (
    await webSerialSink(env.serial)
      .ready()
      .catch(() => false)
  )
    return "webserial";
  if (
    await webUsbSink(env.usb)
      .ready()
      .catch(() => false)
  )
    return "webusb";
  if (
    (settings.transport === "http_epos" || settings.transport === "http_webprnt") &&
    parseLanAddress(settings.lanAddress, 80)
  ) {
    return settings.transport;
  }
  if (settings.cloudId) return "cloud";
  return available.includes("system_print") ? "system_print" : null;
}

/**
 * «PRINTERNI ANIQLASH» (US-M01-07): browser picker in order Web Serial → WebUSB, falling back to the system
 * printer; BLE only when asked explicitly. Must be called from a click handler.
 */
export async function requestPrinterDevice(
  transport: "webserial" | "webusb" | "webbluetooth" | "auto",
  env: PrinterEnvironment = browserPrinterEnvironment(),
): Promise<PrinterTransport> {
  if (transport !== "auto") {
    await requestDevice(transport, env);
    return transport;
  }
  for (const t of ["webserial", "webusb"] as const) {
    if ((t === "webserial" && !env.serial) || (t === "webusb" && !env.usb)) continue;
    try {
      await requestDevice(t, env);
      return t;
    } catch (e) {
      if (e instanceof PrinterError && e.code === "permission_denied") throw e;
    }
  }
  if (env.window) return "system_print";
  throw new PrinterError("device_not_found");
}

export interface PrinterDeps {
  agent?: AgentPrintClient;
  /** Whether the agent can print right now (`$agentStatus`) — status() of agent_raw. */
  agentState?: () => AgentPrintState | null;
  cloud?: CloudPrintApi;
  env?: PrinterEnvironment;
  rasterizer?: Rasterizer;
  /** Job id generator for the cloud queue (UUID v7 in the app). */
  newId?: () => string;
}

function sinkFor(transport: PrinterTransport, env: PrinterEnvironment): ByteSink | null {
  if (transport === "webserial") return webSerialSink(env.serial);
  if (transport === "webusb") return webUsbSink(env.usb);
  if (transport === "webbluetooth") return webBluetoothSink(env.bluetooth);
  return null;
}

export function createPrinterPort(settings: PrinterSettings, deps: PrinterDeps = {}): PrinterPort {
  const configured = settings.transport;
  if (!configured) {
    // Nothing chosen yet: POS-04 offers «Elektron chek (zahira)» + «Uskunalarni sozlash».
    return {
      transport: "system_print",
      printReceipt: () => Promise.reject(new PrinterError("not_configured")),
      printLabel: () => Promise.reject(new PrinterError("not_configured")),
      status: () => Promise.resolve({ transport: null, state: "not_configured", code: "not_configured" }),
    };
  }
  const transport: PrinterTransport = configured;
  const env = deps.env ?? browserPrinterEnvironment();
  const rasterizer = () => deps.rasterizer ?? createCanvasRasterizer();

  async function printReceipt(doc: ReceiptDoc): Promise<PrintResult> {
    const layout = layoutReceipt(doc, { paperWidth: settings.paperWidth });
    switch (transport) {
      case "system_print": {
        if (!env.window) throw new PrinterError("not_supported", transport);
        await systemPrint(env.window, renderReceiptElement(layout, env.window.document));
        return { transport, mode: "html" };
      }
      case "cloud": {
        if (!settings.cloudId) throw new PrinterError("not_configured", transport);
        if (!deps.cloud) throw new PrinterError("cloud_unavailable", transport);
        const bitmap = layoutToBitmap(layout, rasterizer());
        await cloudSubmit(deps.cloud, {
          id: deps.newId?.() ?? crypto.randomUUID(),
          cloud_printer_id: settings.cloudId,
          kind: doc.kind === "test" ? "test" : "receipt",
          raster: {
            width_dots: bitmap.width,
            height_dots: bitmap.height,
            data_base64: bitmapToBase64(bitmap),
          },
        });
        return { transport, mode: "cloud" };
      }
      case "http_webprnt": {
        if (!env.fetch) throw new PrinterError("not_supported", transport);
        await webprntPrint(env.fetch, settings.lanAddress, layoutToBitmap(layout, rasterizer()));
        return { transport, mode: "raster" };
      }
      default: {
        const encoded = encodeEscPos(layout, {
          renderMode: settings.renderMode,
          ...(deps.rasterizer ? { rasterizer: deps.rasterizer } : {}),
        });
        if (transport === "agent_raw") {
          await agentRawPrint(
            deps.agent,
            settings.lanAddress,
            encoded.bytes,
            encoded.mode === "raster" ? "raster" : "cp866",
          );
        } else if (transport === "http_epos") {
          if (!env.fetch) throw new PrinterError("not_supported", transport);
          await eposPrint(env.fetch, settings.lanAddress, encoded.bytes);
        } else {
          const sink = sinkFor(transport, env);
          if (!sink) throw new PrinterError("not_supported", transport);
          await sink.write(encoded.bytes);
        }
        return { transport, mode: encoded.mode };
      }
    }
  }

  async function status(): Promise<PrinterStatus> {
    const t = transport;
    const ready = (ok: boolean, code?: PrinterStatus["code"]): PrinterStatus =>
      ok
        ? { transport: t, state: "ready" }
        : {
            transport: t,
            state: code === "not_configured" ? "not_configured" : "unavailable",
            ...(code ? { code } : {}),
          };
    switch (t) {
      case "system_print":
        return ready(Boolean(env.window), "not_supported");
      case "agent_raw": {
        if (!parseLanAddress(settings.lanAddress, 9100)) return ready(false, "lan_address_invalid");
        const agent = deps.agentState?.() ?? null;
        if (!deps.agent || !agent || agent.status === "not_installed" || agent.status === "offline")
          return ready(false, "agent_unavailable");
        if (agent.status === "unpaired") return ready(false, "agent_unpaired");
        return ready(agent.capabilities.print.enabled, "agent_print_disabled");
      }
      case "http_epos":
      case "http_webprnt":
        return ready(Boolean(parseLanAddress(settings.lanAddress, 80)), "lan_address_invalid");
      case "cloud": {
        if (!settings.cloudId) return ready(false, "not_configured");
        if (!deps.cloud) return ready(false, "cloud_unavailable");
        const online = await deps.cloud
          .status(settings.cloudId)
          .then((s) => s.online)
          .catch(() => false);
        return ready(online, "cloud_unavailable");
      }
      default: {
        const sink = sinkFor(t, env);
        if (!sink) return ready(false, "not_supported");
        return ready(await sink.ready().catch(() => false), "not_configured");
      }
    }
  }

  return {
    transport,
    printReceipt,
    async printLabel(label: LabelDoc) {
      if (!env.window) throw new PrinterError("not_supported", "system_print");
      label.element.style.width = `${label.widthMm}mm`;
      label.element.style.height = `${label.heightMm}mm`;
      label.element.style.overflow = "hidden";
      await systemPrint(env.window, label.element);
    },
    status,
  };
}

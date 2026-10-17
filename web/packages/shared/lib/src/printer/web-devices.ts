/**
 * Browser device transports (24 §6.1): Web Serial, WebUSB, Web Bluetooth (BLE only). The DOM lib has no types
 * for these APIs, so minimal structural interfaces are declared here; tests pass fakes.
 */
import { PrinterError, type ByteSink } from "./types.ts";

// ---------- Web Serial
export interface SerialPortLike {
  readonly writable: WritableStream<Uint8Array> | null;
  open(options: { baudRate: number }): Promise<void>;
  close(): Promise<void>;
}
export interface SerialLike {
  getPorts(): Promise<SerialPortLike[]>;
  requestPort(options?: object): Promise<SerialPortLike>;
}

// ---------- WebUSB
export interface UsbEndpointLike {
  endpointNumber: number;
  direction: "in" | "out";
  type: "bulk" | "interrupt" | "isochronous";
}
export interface UsbInterfaceLike {
  interfaceNumber: number;
  alternate: { interfaceClass: number; endpoints: UsbEndpointLike[] };
}
export interface UsbDeviceLike {
  opened: boolean;
  configuration: { interfaces: UsbInterfaceLike[] } | null;
  open(): Promise<void>;
  close(): Promise<void>;
  selectConfiguration(value: number): Promise<void>;
  claimInterface(n: number): Promise<void>;
  releaseInterface(n: number): Promise<void>;
  transferOut(endpoint: number, data: Uint8Array): Promise<{ status: string }>;
}
export interface UsbLike {
  getDevices(): Promise<UsbDeviceLike[]>;
  requestDevice(options: { filters: { classCode?: number }[] }): Promise<UsbDeviceLike>;
}

// ---------- Web Bluetooth
export interface BleCharacteristicLike {
  properties: { write: boolean; writeWithoutResponse: boolean };
  writeValueWithResponse?(data: Uint8Array): Promise<void>;
  writeValueWithoutResponse?(data: Uint8Array): Promise<void>;
  writeValue?(data: Uint8Array): Promise<void>;
}
export interface BleServiceLike {
  getCharacteristics(): Promise<BleCharacteristicLike[]>;
}
export interface BleServerLike {
  connected: boolean;
  getPrimaryService(uuid: string): Promise<BleServiceLike>;
  disconnect(): void;
}
export interface BleDeviceLike {
  gatt?: { connect(): Promise<BleServerLike> } | undefined;
}
export interface BluetoothLike {
  requestDevice(options: object): Promise<BleDeviceLike>;
  getDevices?(): Promise<BleDeviceLike[]>;
}

/** USB printer class (24 §6.1: class 0x07 is not blocked in WebUSB). */
export const USB_PRINTER_CLASS = 0x07;

/** GATT services of common BLE receipt printers (classic SPP printers do not work — 24 §6.1). */
export const BLE_PRINTER_SERVICES = [
  "000018f0-0000-1000-8000-00805f9b34fb",
  "e7810a71-73ae-499d-8c15-faa9aef0c3f2",
  "49535343-fe7d-4ae5-8fa9-9fafd205e455",
  "0000ff00-0000-1000-8000-00805f9b34fb",
] as const;

function chunks(bytes: Uint8Array, size: number): Uint8Array[] {
  const out: Uint8Array[] = [];
  for (let i = 0; i < bytes.length; i += size) out.push(bytes.subarray(i, i + size));
  return out;
}

const isNotAllowed = (e: unknown) =>
  e instanceof Error && (e.name === "NotAllowedError" || e.name === "SecurityError");
const isNotFound = (e: unknown) => e instanceof Error && e.name === "NotFoundError";

// ---------- sinks

export function webSerialSink(serial: SerialLike | undefined, baudRate = 9600): ByteSink {
  return {
    async ready() {
      return Boolean(serial && (await serial.getPorts()).length);
    },
    async write(bytes) {
      if (!serial) throw new PrinterError("not_supported", "webserial");
      const [port] = await serial.getPorts();
      if (!port) throw new PrinterError("not_configured", "webserial");
      try {
        await port.open({ baudRate });
      } catch (e) {
        // already open (InvalidStateError) is fine; anything else is a device error
        if (!(e instanceof Error && e.name === "InvalidStateError"))
          throw new PrinterError("device_not_found", "webserial", e);
      }
      const writer = port.writable?.getWriter();
      if (!writer) throw new PrinterError("write_failed", "webserial");
      try {
        for (const chunk of chunks(bytes, 1024)) await writer.write(chunk);
      } catch (e) {
        throw new PrinterError("write_failed", "webserial", e);
      } finally {
        writer.releaseLock();
        await port.close().catch(() => undefined);
      }
    },
  };
}

function usbPrinterInterface(device: UsbDeviceLike): { iface: number; endpoint: number } | null {
  for (const i of device.configuration?.interfaces ?? []) {
    if (i.alternate.interfaceClass !== USB_PRINTER_CLASS) continue;
    const out = i.alternate.endpoints.find((e) => e.direction === "out" && e.type === "bulk");
    if (out) return { iface: i.interfaceNumber, endpoint: out.endpointNumber };
  }
  return null;
}

async function firstUsbPrinter(usb: UsbLike): Promise<UsbDeviceLike | null> {
  const devices = await usb.getDevices();
  return devices.find((d) => !d.configuration || usbPrinterInterface(d) !== null) ?? null;
}

export function webUsbSink(usb: UsbLike | undefined): ByteSink {
  return {
    async ready() {
      return Boolean(usb && (await firstUsbPrinter(usb)));
    },
    async write(bytes) {
      if (!usb) throw new PrinterError("not_supported", "webusb");
      const device = await firstUsbPrinter(usb);
      if (!device) throw new PrinterError("not_configured", "webusb");
      try {
        if (!device.opened) await device.open();
        if (!device.configuration) await device.selectConfiguration(1);
      } catch (e) {
        throw new PrinterError("device_not_found", "webusb", e);
      }
      const target = usbPrinterInterface(device);
      if (!target) throw new PrinterError("device_not_found", "webusb");
      try {
        await device.claimInterface(target.iface);
      } catch (e) {
        // Windows: the usbprint driver owns the interface → Zadig/WinUSB or Web Serial (POS-16 error state).
        throw new PrinterError("webusb_claim_failed", "webusb", e);
      }
      try {
        for (const chunk of chunks(bytes, 4096)) {
          const result = await device.transferOut(target.endpoint, chunk);
          if (result.status !== "ok") throw new Error(`transferOut ${result.status}`);
        }
      } catch (e) {
        throw new PrinterError("write_failed", "webusb", e);
      } finally {
        await device.releaseInterface(target.iface).catch(() => undefined);
        await device.close().catch(() => undefined);
      }
    },
  };
}

/** The BLE device picked in this session (Web Bluetooth `getDevices` is not generally available). */
let bleDevice: BleDeviceLike | null = null;
export function rememberBleDevice(device: BleDeviceLike | null): void {
  bleDevice = device;
}

async function bleCharacteristic(server: BleServerLike): Promise<BleCharacteristicLike | null> {
  for (const uuid of BLE_PRINTER_SERVICES) {
    try {
      const service = await server.getPrimaryService(uuid);
      const chars = await service.getCharacteristics();
      const writable = chars.find((c) => c.properties.write || c.properties.writeWithoutResponse);
      if (writable) return writable;
    } catch {
      // service not present on this printer
    }
  }
  return null;
}

export function webBluetoothSink(bluetooth: BluetoothLike | undefined, chunkSize = 100): ByteSink {
  const device = async () => {
    if (bleDevice) return bleDevice;
    const known = (await bluetooth?.getDevices?.()) ?? [];
    return known[0] ?? null;
  };
  return {
    async ready() {
      return Boolean(bluetooth && (await device()));
    },
    async write(bytes) {
      if (!bluetooth) throw new PrinterError("not_supported", "webbluetooth");
      const d = await device();
      if (!d?.gatt) throw new PrinterError("not_configured", "webbluetooth");
      let server: BleServerLike;
      try {
        server = await d.gatt.connect();
      } catch (e) {
        throw new PrinterError("device_not_found", "webbluetooth", e);
      }
      const ch = await bleCharacteristic(server);
      if (!ch) {
        server.disconnect();
        throw new PrinterError("not_supported", "webbluetooth");
      }
      try {
        for (const chunk of chunks(bytes, chunkSize)) {
          if (ch.properties.writeWithoutResponse && ch.writeValueWithoutResponse)
            await ch.writeValueWithoutResponse(chunk);
          else if (ch.writeValueWithResponse) await ch.writeValueWithResponse(chunk);
          else if (ch.writeValue) await ch.writeValue(chunk);
        }
      } catch (e) {
        throw new PrinterError("write_failed", "webbluetooth", e);
      } finally {
        server.disconnect();
      }
    },
  };
}

/** Browser device pickers — must run inside a user gesture (POS-16 «PRINTERNI ANIQLASH»). */
export async function requestDevice(
  transport: "webserial" | "webusb" | "webbluetooth",
  env: { serial?: SerialLike | undefined; usb?: UsbLike | undefined; bluetooth?: BluetoothLike | undefined },
): Promise<void> {
  try {
    if (transport === "webserial") {
      if (!env.serial) throw new PrinterError("not_supported", transport);
      await env.serial.requestPort();
    } else if (transport === "webusb") {
      if (!env.usb) throw new PrinterError("not_supported", transport);
      await env.usb.requestDevice({ filters: [{ classCode: USB_PRINTER_CLASS }] });
    } else {
      if (!env.bluetooth) throw new PrinterError("not_supported", transport);
      const device = await env.bluetooth.requestDevice({
        acceptAllDevices: true,
        optionalServices: [...BLE_PRINTER_SERVICES],
      });
      rememberBleDevice(device);
    }
  } catch (e) {
    if (e instanceof PrinterError) throw e;
    if (isNotFound(e)) throw new PrinterError("cancelled", transport, e);
    if (isNotAllowed(e)) throw new PrinterError("permission_denied", transport, e);
    throw new PrinterError("device_not_found", transport, e);
  }
}

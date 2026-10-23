/**
 * Printer settings in erp-device `device_settings` (24 §6.1, 16 §1/§12 — survive logout, never synced).
 * Storage is injected — @shared/lib must not import @shared/offline; `deviceSettings` fits `DeviceSettingsProvider`.
 */
import { PRINTER_TRANSPORTS, type PrinterSettings, type PrinterTransport } from "./types.ts";

export interface DeviceSettingsProvider {
  get(key: string): Promise<unknown>;
  set(key: string, value: unknown): Promise<void>;
}

export const PRINTER_SETTING_KEYS = {
  transport: "printer.transport",
  paperWidth: "printer.paper_width",
  codepage: "printer.codepage",
  renderMode: "printer.render_mode",
  lanAddress: "printer.lan_address",
  cloudId: "printer.cloud_id",
} as const satisfies Record<keyof PrinterSettings, string>;

export const DEFAULT_PRINTER_SETTINGS: Readonly<PrinterSettings> = Object.freeze({
  transport: null,
  paperWidth: 58,
  codepage: "cp866",
  renderMode: "auto",
  lanAddress: null,
  cloudId: null,
});

const isTransport = (v: unknown): v is PrinterTransport =>
  typeof v === "string" && (PRINTER_TRANSPORTS as readonly string[]).includes(v);

function digitsToInt(s: string): number | null {
  if (!/^[0-9]{1,5}$/.test(s)) return null;
  let n = 0;
  for (const ch of s) n = n * 10 + "0123456789".indexOf(ch);
  return n;
}

export interface LanAddress {
  host: string;
  port: number;
}

/**
 * `IPv4[:port]` on a private LAN only (10/8, 172.16/12, 192.168/16) — POS-16 `printer.lan_address`, 32 chars max.
 * No hostnames (CSP connect-src and the agent allow-list work on literal addresses).
 */
export function parseLanAddress(value: unknown, defaultPort: number): LanAddress | null {
  if (typeof value !== "string" || value.length > 32) return null;
  const [host = "", portText, extra] = value.trim().split(":");
  if (extra !== undefined) return null;
  const octets = host.split(".").map(digitsToInt);
  if (octets.length !== 4 || octets.some((o) => o === null || o > 255)) return null;
  const [a = 0, b = 0] = octets as number[];
  const privateLan = a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168);
  if (!privateLan) return null;
  const port = portText === undefined || portText === "" ? defaultPort : digitsToInt(portText);
  if (port === null || port < 1 || port > 65535) return null;
  return { host: octets.join("."), port };
}

export async function loadPrinterSettings(provider: DeviceSettingsProvider): Promise<PrinterSettings> {
  const d = DEFAULT_PRINTER_SETTINGS;
  const read = async (key: string): Promise<unknown> => {
    try {
      return await provider.get(key);
    } catch {
      return undefined;
    }
  };
  const [transport, paperWidth, renderMode, lanAddress, cloudId] = await Promise.all([
    read(PRINTER_SETTING_KEYS.transport),
    read(PRINTER_SETTING_KEYS.paperWidth),
    read(PRINTER_SETTING_KEYS.renderMode),
    read(PRINTER_SETTING_KEYS.lanAddress),
    read(PRINTER_SETTING_KEYS.cloudId),
  ]);
  return {
    transport: isTransport(transport) ? transport : d.transport,
    paperWidth: paperWidth === 80 || paperWidth === "80" ? 80 : 58,
    codepage: "cp866",
    renderMode: renderMode === "text" || renderMode === "raster" ? renderMode : "auto",
    lanAddress: typeof lanAddress === "string" && lanAddress ? lanAddress : null,
    cloudId: typeof cloudId === "string" && cloudId ? cloudId : null,
  };
}

/** Saves the given fields (POS-16 «SAQLASH»). */
export async function savePrinterSettings(
  provider: DeviceSettingsProvider,
  patch: Partial<PrinterSettings>,
): Promise<void> {
  for (const [field, key] of Object.entries(PRINTER_SETTING_KEYS) as [keyof PrinterSettings, string][]) {
    if (field in patch) await provider.set(key, patch[field] ?? null);
  }
}

/**
 * PrinterPort — 24 §6.1 (transport matrix), 07 POS-16 (settings keys), 08 §13 (receipt template).
 * Contract: .claude-scratch/b3/contracts/hw-api.md §4.
 */
import type { PaperWidth, ReceiptDoc } from "#/receipt/index.ts";

export type PrinterTransport =
  | "agent_raw"
  | "webserial"
  | "webusb"
  | "webbluetooth"
  | "http_epos"
  | "http_webprnt"
  | "cloud"
  | "system_print";

export const PRINTER_TRANSPORTS: readonly PrinterTransport[] = [
  "agent_raw",
  "webserial",
  "webusb",
  "webbluetooth",
  "http_epos",
  "http_webprnt",
  "cloud",
  "system_print",
];

export type PrinterRenderMode = "auto" | "text" | "raster";

/** Device-local settings (erp-device `device_settings`, POS-16). */
export interface PrinterSettings {
  transport: PrinterTransport | null;
  paperWidth: PaperWidth;
  codepage: "cp866";
  renderMode: PrinterRenderMode;
  /** `IPv4:port` on a private LAN — agent_raw / http_epos / http_webprnt. */
  lanAddress: string | null;
  /** Registered cloud printer id — `cloud`. */
  cloudId: string | null;
}

export type PrinterErrorCode =
  | "not_configured"
  | "not_supported"
  | "permission_denied"
  | "device_not_found"
  | "webusb_claim_failed"
  | "write_failed"
  | "timeout"
  | "agent_unavailable"
  | "agent_unpaired"
  | "agent_print_disabled"
  | "printer_not_registered"
  | "printer_unreachable"
  | "lan_address_invalid"
  | "http_failed"
  | "cloud_unavailable"
  | "cloud_failed"
  | "cancelled";

/** i18n key prefix (namespace `pos`, uz + ru). */
export const PRINTER_ERROR_KEY_PREFIX = "pos:equipment.printer.errors.";

export class PrinterError extends Error {
  readonly code: PrinterErrorCode;
  readonly messageKey: string;
  readonly transport: PrinterTransport | null;

  constructor(code: PrinterErrorCode, transport: PrinterTransport | null = null, cause?: unknown) {
    super(`printer ${transport ?? "-"}: ${code}`, cause !== undefined ? { cause } : undefined);
    this.name = "PrinterError";
    this.code = code;
    this.transport = transport;
    this.messageKey = `${PRINTER_ERROR_KEY_PREFIX}${code}`;
  }
}

export interface PrinterStatus {
  transport: PrinterTransport | null;
  state: "ready" | "not_configured" | "unavailable" | "error";
  code?: PrinterErrorCode;
}

export interface PrintResult {
  transport: PrinterTransport;
  /** How the receipt went out: ESC/POS text / ESC/POS raster / OS print dialog / server queue. */
  mode: "text" | "raster" | "html" | "cloud";
}

export interface LabelDoc {
  /** Label DOM (built by the caller — bwip-js SVG etc., 24 §6.3). */
  element: HTMLElement;
  widthMm: number;
  heightMm: number;
}

export interface PrinterPort {
  readonly transport: PrinterTransport;
  printReceipt(doc: ReceiptDoc): Promise<PrintResult>;
  /** Labels always go through the OS driver (24 §6.3). */
  printLabel(doc: LabelDoc): Promise<void>;
  status(): Promise<PrinterStatus>;
}

/** Where an adapter sends ESC/POS bytes. */
export interface ByteSink {
  write(bytes: Uint8Array): Promise<void>;
  ready(): Promise<boolean>;
}

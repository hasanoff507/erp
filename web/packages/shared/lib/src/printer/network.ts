/**
 * Network transports without a browser device API (24 §6.1):
 * - `agent_raw` — raw TCP 9100 LAN printers through Do'kon agenti (`POST /v1/print/raw`, 21 §16.1);
 *   `printer_local_id` = `printer.lan_address` (`IPv4:port`).
 * - `http_epos` — Epson ePOS-Print (SOAP, `<command>` with the ESC/POS bytes as hex).
 * - `http_webprnt` — Star WebPRNT (`<bitimage>` raster; Star printers do not take ESC/POS text).
 * LAN HTTP printers additionally need their origin in CSP `connect-src` (deploy list, 24 §4.4) and Chrome's
 * Local Network Access permission. Real-hardware validation: 26 #139.
 */
import { AgentError } from "#/agent/index.ts";
import { type MonoBitmap } from "#/receipt/index.ts";

import { bitmapToBase64 } from "./bitmap.ts";
import { parseLanAddress } from "./settings.ts";
import { PrinterError } from "./types.ts";

export interface AgentPrintClient {
  printRaw(input: { printerLocalId: string; data: Uint8Array; encoding: "cp866" | "raster" }): Promise<void>;
}

export async function agentRawPrint(
  agent: AgentPrintClient | undefined,
  lanAddress: string | null,
  bytes: Uint8Array,
  encoding: "cp866" | "raster",
): Promise<void> {
  if (!agent) throw new PrinterError("agent_unavailable", "agent_raw");
  const address = parseLanAddress(lanAddress, 9100);
  if (!address) throw new PrinterError("lan_address_invalid", "agent_raw");
  try {
    await agent.printRaw({ printerLocalId: `${address.host}:${address.port}`, data: bytes, encoding });
  } catch (e) {
    if (e instanceof AgentError) {
      if (e.kind === "unpaired") throw new PrinterError("agent_unpaired", "agent_raw", e);
      if (e.kind === "timeout") throw new PrinterError("timeout", "agent_raw", e);
      if (e.kind === "http") throw new PrinterError("write_failed", "agent_raw", e);
    }
    throw new PrinterError("agent_unavailable", "agent_raw", e);
  }
}

const hex = (bytes: Uint8Array) => Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");

type FetchLike = (input: string, init: RequestInit & { targetAddressSpace?: string }) => Promise<Response>;

async function postLan(
  fetchFn: FetchLike,
  url: string,
  body: string,
  transport: "http_epos" | "http_webprnt",
  timeoutMs: number,
) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchFn(url, {
      method: "POST",
      headers: { "Content-Type": "text/xml; charset=utf-8" },
      body,
      signal: controller.signal,
      // Chrome Local Network Access: private-address request from the https PWA (24 §6.1).
      targetAddressSpace: "local",
    });
    const text = await response.text();
    if (!response.ok) throw new PrinterError("http_failed", transport);
    return text;
  } catch (e) {
    if (e instanceof PrinterError) throw e;
    if (controller.signal.aborted) throw new PrinterError("timeout", transport, e);
    throw new PrinterError("http_failed", transport, e);
  } finally {
    clearTimeout(timer);
  }
}

/** Epson ePOS-Print request carrying raw ESC/POS (TM-m30 family). */
export function eposRequestBody(bytes: Uint8Array): string {
  return (
    '<?xml version="1.0" encoding="utf-8"?>' +
    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>' +
    `<epos-print xmlns="http://www.epson-pos.com/schemas/2011/03/epos-print"><command>${hex(bytes)}</command></epos-print>` +
    "</s:Body></s:Envelope>"
  );
}

export async function eposPrint(
  fetchFn: FetchLike,
  lanAddress: string | null,
  bytes: Uint8Array,
): Promise<void> {
  const address = parseLanAddress(lanAddress, 80);
  if (!address) throw new PrinterError("lan_address_invalid", "http_epos");
  const url = `http://${address.host}:${address.port}/cgi-bin/epos/service.cgi?devid=local_printer&timeout=10000`;
  const text = await postLan(fetchFn, url, eposRequestBody(bytes), "http_epos", 15_000);
  if (!/success="true"/.test(text)) throw new PrinterError("write_failed", "http_epos");
}

/** Star WebPRNT request: 1-bit image + partial cut. */
export function webprntRequestBody(bitmap: MonoBitmap): string {
  const request =
    '<root xmlns="http://www.star-m.jp/2011/03/webprnt"><initialization/>' +
    `<bitimage width="${bitmap.width}" height="${bitmap.height}">${bitmapToBase64(bitmap)}</bitimage>` +
    '<cutpaper feed="true" type="partial"/></root>';
  const escaped = request.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return (
    '<StarWebPrint xmlns="http://www.star-m.jp" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">' +
    `<Request>${escaped}</Request></StarWebPrint>`
  );
}

export async function webprntPrint(
  fetchFn: FetchLike,
  lanAddress: string | null,
  bitmap: MonoBitmap,
): Promise<void> {
  const address = parseLanAddress(lanAddress, 80);
  if (!address) throw new PrinterError("lan_address_invalid", "http_webprnt");
  const url = `http://${address.host}:${address.port}/StarWebPRNT/SendMessage`;
  const text = await postLan(fetchFn, url, webprntRequestBody(bitmap), "http_webprnt", 15_000);
  if (/<success>false<\/success>/i.test(text)) throw new PrinterError("write_failed", "http_webprnt");
}

export type { FetchLike };

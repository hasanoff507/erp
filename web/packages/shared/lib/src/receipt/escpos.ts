/**
 * ESC/POS encoder — 24 §6.1 / 08 §13: CP866 (`ESC t 17`), automatic raster mode for Uzbek Cyrillic
 * (Қ/Ғ/Ҳ) or any other character outside CP866, U+02BB → `'`, native QR (`GS ( k`), feed + partial cut.
 */
import { canEncodeCp866, encodeCp866, normalizeReceiptText, UZBEK_CYRILLIC_EXTRA } from "./cp866.ts";
import { blockLines, columnsFor, layoutTexts, PRINT_DOTS } from "./layout.ts";
import { createCanvasRasterizer, type MonoBitmap, type Rasterizer } from "./raster.ts";
import type { ReceiptBlock, ReceiptLayout, TextBlock } from "./types.ts";

export type RenderMode = "auto" | "text" | "raster";

const ESC = 0x1b;
const GS = 0x1d;
const LF = 0x0a;

export const ESCPOS = {
  init: [ESC, 0x40],
  /** ESC t 17 — code page CP866. */
  codepageCp866: [ESC, 0x74, 17],
  align: (n: 0 | 1 | 2) => [ESC, 0x61, n],
  bold: (on: boolean) => [ESC, 0x45, on ? 1 : 0],
  /** GS ! — 0x00 normal, 0x11 double width + height. */
  size: (n: number) => [GS, 0x21, n],
  /** ESC M — 0 Font A, 1 Font B. */
  font: (n: 0 | 1) => [ESC, 0x4d, n],
  feed: (n: number) => [ESC, 0x64, n],
  /** GS V 66 0 — feed to the cutter and partial cut. */
  cut: [GS, 0x56, 66, 0],
} as const;

/** Native QR: model 2, module size, ECC level M, store + print (GS ( k). */
export function qrCommand(data: string, moduleSize = 8): number[] {
  const bytes = Array.from(new TextEncoder().encode(data));
  const storeLen = bytes.length + 3;
  return [
    ...[GS, 0x28, 0x6b, 4, 0, 0x31, 0x41, 0x32, 0x00],
    ...[GS, 0x28, 0x6b, 3, 0, 0x31, 0x43, moduleSize],
    ...[GS, 0x28, 0x6b, 3, 0, 0x31, 0x45, 0x31],
    ...[GS, 0x28, 0x6b, storeLen & 0xff, (storeLen >> 8) & 0xff, 0x31, 0x50, 0x30, ...bytes],
    ...[GS, 0x28, 0x6b, 3, 0, 0x31, 0x51, 0x30],
  ];
}

/** Rows per `GS v 0` command — small bands keep cheap printers' buffers safe. */
export const RASTER_BAND_ROWS = 96;

/** `GS v 0 m xL xH yL yH d…` bands for a mono bitmap. */
export function rasterCommand(bitmap: MonoBitmap, bandRows = RASTER_BAND_ROWS): number[] {
  const rowBytes = Math.ceil(bitmap.width / 8);
  const out: number[] = [];
  for (let y = 0; y < bitmap.height; y += bandRows) {
    const rows = Math.min(bandRows, bitmap.height - y);
    out.push(GS, 0x76, 0x30, 0, rowBytes & 0xff, (rowBytes >> 8) & 0xff, rows & 0xff, (rows >> 8) & 0xff);
    const slice = bitmap.data.subarray(y * rowBytes, (y + rows) * rowBytes);
    for (const b of slice) out.push(b);
  }
  return out;
}

/** Applies the printer text normalisation (ʻ → ' …) to every text block. */
export function normalizeLayout(layout: ReceiptLayout): ReceiptLayout {
  return {
    ...layout,
    blocks: layout.blocks.map((b) =>
      b.type === "text"
        ? {
            ...b,
            left: normalizeReceiptText(b.left),
            ...(b.right !== undefined ? { right: normalizeReceiptText(b.right) } : {}),
          }
        : b,
    ),
  };
}

/**
 * `auto` render mode decision (24 §6.1, QT-M01-22): raster when the receipt has Uzbek Cyrillic Қ/Ғ/Ҳ or any
 * other character CP866 cannot print (after normalisation); Latin/Russian-only receipts stay in text mode.
 */
export function needsRaster(layout: ReceiptLayout): boolean {
  return layoutTexts(normalizeLayout(layout)).some((t) => UZBEK_CYRILLIC_EXTRA.test(t) || !canEncodeCp866(t));
}

export interface EncodeOptions {
  renderMode: RenderMode;
  rasterizer?: Rasterizer;
}

export interface EncodedReceipt {
  bytes: Uint8Array;
  mode: "text" | "raster";
}

function textBlockBytes(block: TextBlock, layout: ReceiptLayout): number[] {
  const out: number[] = [];
  out.push(...ESCPOS.align(0));
  out.push(...ESCPOS.font(block.size === "small" ? 1 : 0));
  out.push(...ESCPOS.size(block.size === "large" ? 0x11 : 0x00));
  out.push(...ESCPOS.bold(Boolean(block.bold)));
  for (const line of blockLines(block, columnsFor(layout, block.size))) {
    out.push(...encodeCp866(line.trimEnd()), LF);
  }
  if (block.bold) out.push(...ESCPOS.bold(false));
  if (block.size !== "normal") out.push(...ESCPOS.size(0x00), ...ESCPOS.font(0));
  return out;
}

/** Layout → ESC/POS bytes. */
export function encodeEscPos(source: ReceiptLayout, options: EncodeOptions): EncodedReceipt {
  const layout = normalizeLayout(source);
  const raster = options.renderMode === "raster" || (options.renderMode === "auto" && needsRaster(layout));
  const out: number[] = [...ESCPOS.init, ...ESCPOS.codepageCp866];

  if (!raster) {
    for (const block of layout.blocks) out.push(...blockBytes(block, layout));
  } else {
    const rasterizer = options.rasterizer ?? createCanvasRasterizer();
    const width = PRINT_DOTS[layout.paperWidth];
    let pending: (TextBlock | null)[] = [];
    const flush = () => {
      if (!pending.length) return;
      const bitmap = rasterizer.rasterize({ blocks: pending, layout }, width);
      out.push(...ESCPOS.align(0), ...rasterCommand(bitmap));
      pending = [];
    };
    for (const block of layout.blocks) {
      if (block.type === "text") pending.push(block);
      else if (block.type === "rule") pending.push(null);
      else {
        flush();
        out.push(...blockBytes(block, layout));
      }
    }
    flush();
  }
  out.push(...ESCPOS.cut);
  return { bytes: Uint8Array.from(out), mode: raster ? "raster" : "text" };
}

function blockBytes(block: ReceiptBlock, layout: ReceiptLayout): number[] {
  switch (block.type) {
    case "text":
      return textBlockBytes(block, layout);
    case "rule":
      return [...ESCPOS.align(0), ...encodeCp866("-".repeat(layout.columns)), LF];
    case "qr":
      return [...ESCPOS.align(1), ...qrCommand(block.data), LF, ...ESCPOS.align(0)];
    case "feed":
      return ESCPOS.feed(block.lines);
  }
}

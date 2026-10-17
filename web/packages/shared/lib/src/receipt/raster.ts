/**
 * Raster mode (24 §6.1): a receipt containing Қ/Ғ/Ҳ (not in CP866) is drawn on a canvas and sent as a
 * 1-bit image (`GS v 0`). The rasterizer is injectable so the byte encoder stays testable in Node.
 */
import { blockLines, columnsFor } from "./layout.ts";
import type { ReceiptLayout, TextBlock } from "./types.ts";

/** 1 bit per pixel, rows of `ceil(width / 8)` bytes, MSB = leftmost pixel, 1 = black. */
export interface MonoBitmap {
  width: number;
  height: number;
  data: Uint8Array;
}

export interface RasterSegment {
  /** Text blocks (and rules as `null`) to draw, top to bottom. */
  blocks: readonly (TextBlock | null)[];
  layout: Pick<ReceiptLayout, "columns" | "smallColumns">;
}

export interface Rasterizer {
  rasterize(segment: RasterSegment, widthDots: number): MonoBitmap;
}

/** RGBA pixels → MonoBitmap (luminance < threshold = black). */
export function rgbaToMono(
  rgba: Uint8ClampedArray | Uint8Array,
  width: number,
  height: number,
  threshold = 160,
): MonoBitmap {
  const rowBytes = Math.ceil(width / 8);
  const data = new Uint8Array(rowBytes * height);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const i = (y * width + x) * 4;
      const alpha = (rgba[i + 3] ?? 255) / 255;
      const lum =
        255 -
        alpha *
          (255 - (0.299 * (rgba[i] ?? 255) + 0.587 * (rgba[i + 1] ?? 255) + 0.114 * (rgba[i + 2] ?? 255)));
      if (lum < threshold) {
        const idx = y * rowBytes + (x >> 3);
        data[idx] = (data[idx] ?? 0) | (0x80 >> (x & 7));
      }
    }
  }
  return { width, height, data };
}

type Canvas2D = CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D;

const FONT_STACK = "'Noto Sans Variable', 'Segoe UI', Arial, sans-serif";
const LINE_HEIGHT = { normal: 30, small: 24, large: 54 } as const;
const FONT_PX = { normal: 24, small: 19, large: 40 } as const;

/**
 * Browser rasterizer (canvas). Each wrapped line is drawn at the same column logic as text mode; the right
 * part of a row is right-aligned with `measureText`, so proportional fonts keep amounts aligned.
 */
export function createCanvasRasterizer(): Rasterizer {
  return {
    rasterize(segment, widthDots) {
      const rows: { line: string; right: string | null; block: TextBlock | null }[] = [];
      for (const block of segment.blocks) {
        if (!block) {
          rows.push({ line: "", right: null, block: null });
          continue;
        }
        const cols = columnsFor(segment.layout, block.size);
        if (block.right) {
          const lines = blockLines({ ...block, right: undefined }, cols);
          lines.forEach((line, i) =>
            rows.push({ line, right: i === lines.length - 1 ? (block.right ?? null) : null, block }),
          );
        } else {
          for (const line of blockLines(block, cols)) rows.push({ line: line.trim(), right: null, block });
        }
      }
      const height = rows.reduce((h, r) => h + (r.block ? LINE_HEIGHT[r.block.size] : 16), 0) || 1;
      const ctx = createContext(widthDots, height);
      ctx.fillStyle = "#fff";
      ctx.fillRect(0, 0, widthDots, height);
      ctx.fillStyle = "#000";
      ctx.textBaseline = "top";
      let y = 0;
      for (const row of rows) {
        if (!row.block) {
          ctx.fillRect(0, y + 7, widthDots, 2);
          y += 16;
          continue;
        }
        const { size, bold, align } = row.block;
        ctx.font = `${bold ? "700" : "400"} ${FONT_PX[size]}px ${FONT_STACK}`;
        const w = ctx.measureText(row.line).width;
        const x =
          row.right !== null || align === "left"
            ? 0
            : align === "center"
              ? (widthDots - w) / 2
              : widthDots - w;
        ctx.fillText(row.line, Math.max(0, x), y + 2);
        if (row.right !== null) {
          const rw = ctx.measureText(row.right).width;
          ctx.fillText(row.right, widthDots - rw, y + 2);
        }
        y += LINE_HEIGHT[size];
      }
      const image = ctx.getImageData(0, 0, widthDots, height);
      return rgbaToMono(image.data, widthDots, height);
    },
  };
}

function createContext(width: number, height: number): Canvas2D {
  if (typeof OffscreenCanvas !== "undefined") {
    const ctx = new OffscreenCanvas(width, height).getContext("2d");
    if (ctx) return ctx;
  }
  if (typeof document !== "undefined") {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (ctx) return ctx;
  }
  throw new Error("Canvas is not available for raster printing");
}

/** Stacks bitmaps vertically (same width). */
export function stackBitmaps(parts: readonly MonoBitmap[]): MonoBitmap {
  const width = parts[0]?.width ?? 0;
  const height = parts.reduce((h, p) => h + p.height, 0);
  const data = new Uint8Array(Math.ceil(width / 8) * height);
  let offset = 0;
  for (const part of parts) {
    data.set(part.data, offset);
    offset += part.data.length;
  }
  return { width, height, data };
}

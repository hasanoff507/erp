/**
 * Whole receipt as one 1-bit image (Star WebPRNT and the cloud queue take images, 24 §6.1):
 * text segments through the rasterizer, the OFD QR drawn from `encodeQr` (module 8 dots ≈ 1 mm, ≥ 30 mm).
 */
import {
  encodeQr,
  type MonoBitmap,
  normalizeLayout,
  PRINT_DOTS,
  type Rasterizer,
  type ReceiptLayout,
  stackBitmaps,
  type TextBlock,
} from "#/receipt/index.ts";

export function qrBitmap(data: string, width: number, moduleDots = 8): MonoBitmap {
  const qr = encodeQr(data);
  const side = (qr.size + 8) * moduleDots;
  const scale = side > width ? Math.max(1, Math.floor(width / (qr.size + 8))) : moduleDots;
  const total = (qr.size + 8) * scale;
  const rowBytes = Math.ceil(width / 8);
  const data8 = new Uint8Array(rowBytes * total);
  const left = Math.floor((width - total) / 2) + 4 * scale;
  for (let y = 0; y < qr.size; y += 1) {
    for (let x = 0; x < qr.size; x += 1) {
      if (!qr.isDark(x, y)) continue;
      for (let dy = 0; dy < scale; dy += 1) {
        const row = (4 * scale + y * scale + dy) * rowBytes;
        for (let dx = 0; dx < scale; dx += 1) {
          const px = left + x * scale + dx;
          const idx = row + (px >> 3);
          data8[idx] = (data8[idx] ?? 0) | (0x80 >> (px & 7));
        }
      }
    }
  }
  return { width, height: total, data: data8 };
}

export function layoutToBitmap(source: ReceiptLayout, rasterizer: Rasterizer): MonoBitmap {
  const layout = normalizeLayout(source);
  const width = PRINT_DOTS[layout.paperWidth];
  const parts: MonoBitmap[] = [];
  let pending: (TextBlock | null)[] = [];
  const flush = () => {
    if (pending.length) parts.push(rasterizer.rasterize({ blocks: pending, layout }, width));
    pending = [];
  };
  for (const block of layout.blocks) {
    if (block.type === "text") pending.push(block);
    else if (block.type === "rule") pending.push(null);
    else if (block.type === "qr") {
      flush();
      parts.push(qrBitmap(block.data, width));
    }
  }
  flush();
  return stackBitmaps(parts);
}

export function bitmapToBase64(bitmap: MonoBitmap): string {
  let binary = "";
  for (let i = 0; i < bitmap.data.length; i += 0x8000) {
    binary += String.fromCharCode(...bitmap.data.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

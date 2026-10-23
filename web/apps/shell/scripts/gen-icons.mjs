#!/usr/bin/env node
/**
 * Generates the PWA PNG icons (brand tile #0E7C66 with a white "E", same geometry as favicon.svg)
 * without any image dependency: raw RGBA → PNG via zlib. Run once: `pnpm --filter shell icons`.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";

const out = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "icons");
mkdirSync(out, { recursive: true });

const BRAND = [0x0e, 0x7c, 0x66, 0xff];
const WHITE = [0xff, 0xff, 0xff, 0xff];
const CLEAR = [0, 0, 0, 0];
// "E" on a 64-unit grid (favicon.svg path): spine + three arms.
const E_RECTS = [
  [22, 16, 30, 48],
  [22, 16, 43, 23],
  [30, 29, 41, 35],
  [30, 41, 43, 48],
];

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

function png(size, { radius, inset }) {
  const raw = Buffer.alloc(size * (size * 4 + 1));
  const scale = (size * (1 - 2 * inset)) / 64;
  const offset = size * inset;
  for (let y = 0; y < size; y += 1) {
    raw[y * (size * 4 + 1)] = 0;
    for (let x = 0; x < size; x += 1) {
      const cx = Math.min(x + 0.5, size - x - 0.5);
      const cy = Math.min(y + 0.5, size - y - 0.5);
      const outside = cx < radius && cy < radius && Math.hypot(radius - cx, radius - cy) > radius;
      const gx = (x + 0.5 - offset) / scale;
      const gy = (y + 0.5 - offset) / scale;
      const inE = E_RECTS.some(([x0, y0, x1, y1]) => gx >= x0 && gx < x1 && gy >= y0 && gy < y1);
      const px = outside ? CLEAR : inE ? WHITE : BRAND;
      raw.set(px, y * (size * 4 + 1) + 1 + x * 4);
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

const icons = {
  "icon-192.png": png(192, { radius: 54, inset: 0 }),
  "icon-512.png": png(512, { radius: 144, inset: 0 }),
  // Maskable: full-bleed background, glyph inside the 80% safe zone.
  "icon-maskable-512.png": png(512, { radius: 0, inset: 0.12 }),
  "apple-touch-icon.png": png(180, { radius: 0, inset: 0.04 }),
};
for (const [name, data] of Object.entries(icons)) {
  writeFileSync(join(out, name), data);
  process.stdout.write(`wrote public/icons/${name} (${data.length} B)\n`);
}

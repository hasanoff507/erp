/**
 * Minimal QR Code encoder (ISO/IEC 18004) — byte mode, error correction level M, versions 1–40,
 * automatic mask selection. Used for the OFD receipt QR (≥ 30×30 mm, 08 §13.1) in the HTML / system-print
 * receipt; ESC/POS printers draw the QR themselves (GS ( k). Algorithm after Project Nayuki's reference
 * implementation (MIT).
 */

const ECC_CODEWORDS_PER_BLOCK_M = [
  -1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28,
  28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28,
];
const NUM_BLOCKS_M = [
  -1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28,
  29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49,
];
/** Format bits for ECC level M (binary 00). */
const ECC_FORMAT_BITS_M = 0;

export interface QrMatrix {
  /** Modules per side (without the quiet zone). */
  size: number;
  version: number;
  isDark(x: number, y: number): boolean;
}

function numRawDataModules(ver: number): number {
  let result = (16 * ver + 128) * ver + 64;
  if (ver >= 2) {
    const numAlign = Math.floor(ver / 7) + 2;
    result -= (25 * numAlign - 10) * numAlign - 55;
    if (ver >= 7) result -= 36;
  }
  return result;
}

function numDataCodewords(ver: number): number {
  return (
    Math.floor(numRawDataModules(ver) / 8) - (ECC_CODEWORDS_PER_BLOCK_M[ver] ?? 0) * (NUM_BLOCKS_M[ver] ?? 0)
  );
}

function reedSolomonDivisor(degree: number): number[] {
  const result: number[] = new Array<number>(degree).fill(0);
  result[degree - 1] = 1;
  let root = 1;
  for (let i = 0; i < degree; i += 1) {
    for (let j = 0; j < result.length; j += 1) {
      result[j] = reedSolomonMultiply(result[j] ?? 0, root);
      if (j + 1 < result.length) result[j] = (result[j] ?? 0) ^ (result[j + 1] ?? 0);
    }
    root = reedSolomonMultiply(root, 0x02);
  }
  return result;
}

function reedSolomonRemainder(data: readonly number[], divisor: readonly number[]): number[] {
  const result: number[] = divisor.map(() => 0);
  for (const b of data) {
    const factor = b ^ (result.shift() ?? 0);
    result.push(0);
    divisor.forEach((coef, i) => {
      result[i] = (result[i] ?? 0) ^ reedSolomonMultiply(coef, factor);
    });
  }
  return result;
}

function reedSolomonMultiply(x: number, y: number): number {
  let z = 0;
  for (let i = 7; i >= 0; i -= 1) {
    z = (z << 1) ^ ((z >>> 7) * 0x11d);
    z ^= ((y >>> i) & 1) * x;
  }
  return z & 0xff;
}

function alignmentPatternPositions(ver: number, size: number): number[] {
  if (ver === 1) return [];
  const numAlign = Math.floor(ver / 7) + 2;
  const step = ver === 32 ? 26 : Math.ceil((ver * 4 + 4) / (numAlign * 2 - 2)) * 2;
  const result = [6];
  for (let pos = size - 7; result.length < numAlign; pos -= step) result.splice(1, 0, pos);
  return result;
}

function utf8Bytes(text: string): number[] {
  return Array.from(new TextEncoder().encode(text));
}

/** Encodes `text` (UTF-8, byte mode, ECC M). Throws when it does not fit version 40. */
export function encodeQr(text: string): QrMatrix {
  const data = utf8Bytes(text);
  let version = 1;
  for (; ; version += 1) {
    if (version > 40) throw new Error("QR payload too long");
    const countBits = version <= 9 ? 8 : 16;
    if (4 + countBits + data.length * 8 <= numDataCodewords(version) * 8) break;
  }
  const countBits = version <= 9 ? 8 : 16;

  // --- data bit stream
  const bits: number[] = [];
  const append = (value: number, len: number) => {
    for (let i = len - 1; i >= 0; i -= 1) bits.push((value >>> i) & 1);
  };
  append(0b0100, 4);
  append(data.length, countBits);
  for (const b of data) append(b, 8);
  const capacityBits = numDataCodewords(version) * 8;
  append(0, Math.min(4, capacityBits - bits.length));
  append(0, (8 - (bits.length % 8)) % 8);
  for (let pad = 0xec; bits.length < capacityBits; pad ^= 0xec ^ 0x11) append(pad, 8);
  const dataCodewords: number[] = [];
  for (let i = 0; i < bits.length; i += 8) {
    let b = 0;
    for (let j = 0; j < 8; j += 1) b = (b << 1) | (bits[i + j] ?? 0);
    dataCodewords.push(b);
  }

  // --- error correction + interleaving
  const numBlocks = NUM_BLOCKS_M[version] ?? 1;
  const blockEccLen = ECC_CODEWORDS_PER_BLOCK_M[version] ?? 0;
  const rawCodewords = Math.floor(numRawDataModules(version) / 8);
  const numShortBlocks = numBlocks - (rawCodewords % numBlocks);
  const shortBlockLen = Math.floor(rawCodewords / numBlocks);
  const blocks: number[][] = [];
  const divisor = reedSolomonDivisor(blockEccLen);
  for (let i = 0, k = 0; i < numBlocks; i += 1) {
    const dat = dataCodewords.slice(k, k + shortBlockLen - blockEccLen + (i < numShortBlocks ? 0 : 1));
    k += dat.length;
    const ecc = reedSolomonRemainder(dat, divisor);
    if (i < numShortBlocks) dat.push(0);
    blocks.push(dat.concat(ecc));
  }
  const allCodewords: number[] = [];
  for (let i = 0; i < (blocks[0]?.length ?? 0); i += 1) {
    blocks.forEach((block, j) => {
      if (i !== shortBlockLen - blockEccLen || j >= numShortBlocks) allCodewords.push(block[i] ?? 0);
    });
  }

  // --- module grid
  const size = version * 4 + 17;
  const modules: boolean[][] = Array.from({ length: size }, () => new Array<boolean>(size).fill(false));
  const isFunction: boolean[][] = Array.from({ length: size }, () => new Array<boolean>(size).fill(false));
  const setFunction = (x: number, y: number, dark: boolean) => {
    const row = modules[y];
    const frow = isFunction[y];
    if (!row || !frow) return;
    row[x] = dark;
    frow[x] = true;
  };

  for (let i = 0; i < size; i += 1) {
    setFunction(6, i, i % 2 === 0);
    setFunction(i, 6, i % 2 === 0);
  }
  const drawFinder = (x: number, y: number) => {
    for (let dy = -4; dy <= 4; dy += 1) {
      for (let dx = -4; dx <= 4; dx += 1) {
        const dist = Math.max(Math.abs(dx), Math.abs(dy));
        const xx = x + dx;
        const yy = y + dy;
        if (xx >= 0 && xx < size && yy >= 0 && yy < size) setFunction(xx, yy, dist !== 2 && dist !== 4);
      }
    }
  };
  drawFinder(3, 3);
  drawFinder(size - 4, 3);
  drawFinder(3, size - 4);
  const align = alignmentPatternPositions(version, size);
  const numAlign = align.length;
  for (let i = 0; i < numAlign; i += 1) {
    for (let j = 0; j < numAlign; j += 1) {
      if ((i === 0 && j === 0) || (i === 0 && j === numAlign - 1) || (i === numAlign - 1 && j === 0))
        continue;
      const cx = align[i] ?? 0;
      const cy = align[j] ?? 0;
      for (let dy = -2; dy <= 2; dy += 1) {
        for (let dx = -2; dx <= 2; dx += 1)
          setFunction(cx + dx, cy + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
      }
    }
  }

  const drawFormatBits = (mask: number) => {
    const fmt = (ECC_FORMAT_BITS_M << 3) | mask;
    let rem = fmt;
    for (let i = 0; i < 10; i += 1) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
    const fbits = ((fmt << 10) | rem) ^ 0x5412;
    const bit = (i: number) => ((fbits >>> i) & 1) !== 0;
    for (let i = 0; i <= 5; i += 1) setFunction(8, i, bit(i));
    setFunction(8, 7, bit(6));
    setFunction(8, 8, bit(7));
    setFunction(7, 8, bit(8));
    for (let i = 9; i < 15; i += 1) setFunction(14 - i, 8, bit(i));
    for (let i = 0; i < 8; i += 1) setFunction(size - 1 - i, 8, bit(i));
    for (let i = 8; i < 15; i += 1) setFunction(8, size - 15 + i, bit(i));
    setFunction(8, size - 8, true);
  };
  drawFormatBits(0); // reserve the area

  if (version >= 7) {
    let rem = version;
    for (let i = 0; i < 12; i += 1) rem = (rem << 1) ^ ((rem >>> 11) * 0x1f25);
    const vbits = (version << 12) | rem;
    for (let i = 0; i < 18; i += 1) {
      const dark = ((vbits >>> i) & 1) !== 0;
      const a = size - 11 + (i % 3);
      const b = Math.floor(i / 3);
      setFunction(a, b, dark);
      setFunction(b, a, dark);
    }
  }

  // --- codewords in zigzag
  let bitIndex = 0;
  const totalBits = allCodewords.length * 8;
  for (let right = size - 1; right >= 1; right -= 2) {
    if (right === 6) right = 5;
    for (let vert = 0; vert < size; vert += 1) {
      for (let j = 0; j < 2; j += 1) {
        const x = right - j;
        const upward = ((right + 1) & 2) === 0;
        const y = upward ? size - 1 - vert : vert;
        const row = modules[y];
        if (!row || isFunction[y]?.[x] || bitIndex >= totalBits) continue;
        row[x] = (((allCodewords[bitIndex >>> 3] ?? 0) >>> (7 - (bitIndex & 7))) & 1) !== 0;
        bitIndex += 1;
      }
    }
  }

  // --- masks
  const applyMask = (mask: number) => {
    for (let y = 0; y < size; y += 1) {
      for (let x = 0; x < size; x += 1) {
        let invert: boolean;
        switch (mask) {
          case 0:
            invert = (x + y) % 2 === 0;
            break;
          case 1:
            invert = y % 2 === 0;
            break;
          case 2:
            invert = x % 3 === 0;
            break;
          case 3:
            invert = (x + y) % 3 === 0;
            break;
          case 4:
            invert = (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0;
            break;
          case 5:
            invert = ((x * y) % 2) + ((x * y) % 3) === 0;
            break;
          case 6:
            invert = (((x * y) % 2) + ((x * y) % 3)) % 2 === 0;
            break;
          default:
            invert = (((x + y) % 2) + ((x * y) % 3)) % 2 === 0;
        }
        const row = modules[y];
        if (row && !isFunction[y]?.[x] && invert) row[x] = !row[x];
      }
    }
  };

  const penalty = (): number => {
    const dark = (x: number, y: number) => modules[y]?.[x] === true;
    let result = 0;
    const finderLike = (run: boolean[]) =>
      run.length === 11 &&
      (run.join() === [true, false, true, true, true, false, true, false, false, false, false].join() ||
        run.join() === [false, false, false, false, true, false, true, true, true, false, true].join());
    for (let pass = 0; pass < 2; pass += 1) {
      for (let a = 0; a < size; a += 1) {
        let runColor = false;
        let runLen = 0;
        for (let b = 0; b < size; b += 1) {
          const c = pass === 0 ? dark(b, a) : dark(a, b);
          if (b > 0 && c === runColor) {
            runLen += 1;
            if (runLen === 5) result += 3;
            else if (runLen > 5) result += 1;
          } else {
            runColor = c;
            runLen = 1;
          }
          if (b >= 10) {
            const run: boolean[] = [];
            for (let k = b - 10; k <= b; k += 1) run.push(pass === 0 ? dark(k, a) : dark(a, k));
            if (finderLike(run)) result += 40;
          }
        }
      }
    }
    for (let y = 0; y < size - 1; y += 1) {
      for (let x = 0; x < size - 1; x += 1) {
        const c = dark(x, y);
        if (c === dark(x + 1, y) && c === dark(x, y + 1) && c === dark(x + 1, y + 1)) result += 3;
      }
    }
    let darkCount = 0;
    for (let y = 0; y < size; y += 1) for (let x = 0; x < size; x += 1) if (dark(x, y)) darkCount += 1;
    const total = size * size;
    const k = Math.ceil(Math.abs(darkCount * 20 - total * 10) / total) - 1;
    result += Math.max(0, k) * 10;
    return result;
  };

  let bestMask = 0;
  let minPenalty = Number.POSITIVE_INFINITY;
  for (let mask = 0; mask < 8; mask += 1) {
    applyMask(mask);
    drawFormatBits(mask);
    const p = penalty();
    if (p < minPenalty) {
      bestMask = mask;
      minPenalty = p;
    }
    applyMask(mask); // undo (XOR)
  }
  applyMask(bestMask);
  drawFormatBits(bestMask);

  return {
    size,
    version,
    isDark: (x: number, y: number) => modules[y]?.[x] === true,
  };
}

/** QR as a standalone SVG string (`viewBox` in modules, 4-module quiet zone, crisp edges). */
export function qrSvg(text: string, sizeMm = 32): string {
  const qr = encodeQr(text);
  const border = 4;
  const dim = qr.size + border * 2;
  const parts: string[] = [];
  for (let y = 0; y < qr.size; y += 1) {
    for (let x = 0; x < qr.size; x += 1) {
      if (qr.isDark(x, y)) parts.push(`M${x + border},${y + border}h1v1h-1z`);
    }
  }
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${dim} ${dim}" width="${sizeMm}mm" height="${sizeMm}mm" ` +
    `shape-rendering="crispEdges"><rect width="100%" height="100%" fill="#fff"/>` +
    `<path d="${parts.join("")}" fill="#000"/></svg>`
  );
}

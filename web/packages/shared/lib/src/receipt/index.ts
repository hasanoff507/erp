/**
 * @shared/lib/receipt — receipt document model, layout (08 §13.1), ESC/POS (CP866 / raster, 24 §6.1),
 * HTML/DOM rendering and the QR encoder. Contract: .claude-scratch/b3/contracts/hw-api.md §3.
 */
export * from "./types.ts";
export {
  blockLines,
  COLUMNS,
  columnsFor,
  layoutReceipt,
  layoutTexts,
  PRINT_DOTS,
  RECEIPT_LABELS,
  SMALL_COLUMNS,
  TEST_RECEIPT_TEXT,
  testReceiptDoc,
  wrapText,
  type LayoutOptions,
  type TestReceiptOptions,
} from "./layout.ts";
export {
  canEncodeCp866,
  cp866Byte,
  encodeCp866,
  normalizeReceiptText,
  UZBEK_CYRILLIC_EXTRA,
} from "./cp866.ts";
export {
  encodeEscPos,
  ESCPOS,
  needsRaster,
  normalizeLayout,
  qrCommand,
  RASTER_BAND_ROWS,
  rasterCommand,
  type EncodedReceipt,
  type EncodeOptions,
  type RenderMode,
} from "./escpos.ts";
export {
  createCanvasRasterizer,
  rgbaToMono,
  stackBitmaps,
  type MonoBitmap,
  type Rasterizer,
  type RasterSegment,
} from "./raster.ts";
export { renderReceiptElement, renderReceiptHtml } from "./html.ts";
export { encodeQr, qrSvg, type QrMatrix } from "./qr.ts";

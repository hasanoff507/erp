/**
 * Warehouse scanning toolkit of POS-08 / POS-09 / POS-10 (and the POS-16 scanner test): scan → local product
 * (weight labels, pack barcodes, DataMatrix), decimal-string qty helpers, device-local caches, the screen frame,
 * the scan field and the qty stepper. Owner: b3-pos-wh.
 */
export { classifyCode, gtinOfMarkingCode, isMarkingCode, normalizeScan, type CodeKind } from "./lib/codes.ts";
export {
  addQty,
  compareQty,
  decrementQty,
  isPositiveQty,
  isQty,
  qty3,
  subtractQty,
  sumQty,
  trimQty,
} from "./lib/qty.ts";
export {
  WH_CACHE_KEYS,
  loadWarehouses,
  readCache,
  toWarehouseRef,
  writeCache,
  type KeyValueStore,
  type WarehouseRef,
} from "./lib/cache.ts";
export {
  defaultScanDeps,
  resolveScan,
  type ScanDeps,
  type ScanResult,
  type ScannedProduct,
} from "./model/resolve.ts";
export { WhScreen, type WhScreenProps } from "./ui/WhScreen.tsx";
export { ScanField, type ScanFieldProps } from "./ui/ScanField.tsx";
export { QtyStepper, type QtyStepperProps } from "./ui/QtyStepper.tsx";
export { ProductSearch, type ProductSearchProps } from "./ui/ProductSearch.tsx";

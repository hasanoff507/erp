/**
 * @shared/lib/printer — PrinterPort and transport adapters (24 §6.1). Contract: .claude-scratch/b3/contracts/hw-api.md §4.
 */
export * from "./types.ts";
export {
  DEFAULT_PRINTER_SETTINGS,
  type DeviceSettingsProvider,
  type LanAddress,
  loadPrinterSettings,
  parseLanAddress,
  PRINTER_SETTING_KEYS,
  savePrinterSettings,
} from "./settings.ts";
export {
  type AgentPrintState,
  availableTransports,
  browserPrinterEnvironment,
  createPrinterPort,
  detectPrinterTransport,
  type PrinterDeps,
  type PrinterEnvironment,
  requestPrinterDevice,
} from "./port.ts";
export { type CloudPrintApi, type CloudPrintJob, type PrintWindow, systemPrint } from "./cloud-system.ts";
export { type AgentPrintClient, eposRequestBody, webprntRequestBody } from "./network.ts";
export { layoutToBitmap, qrBitmap } from "./bitmap.ts";
export {
  BLE_PRINTER_SERVICES,
  type BluetoothLike,
  rememberBleDevice,
  type SerialLike,
  USB_PRINTER_CLASS,
  type UsbLike,
} from "./web-devices.ts";

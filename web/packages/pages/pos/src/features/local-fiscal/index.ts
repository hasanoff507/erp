/**
 * Local-bridge fiscalisation (B5; 21 §16, 24 §6.4): register binding, `$localFiscal` readiness, the signing
 * orchestration (`signFiscalReceipt`) and the POS-02/POS-03 banners.
 */
export {
  $fiscalBinding,
  $localFiscal,
  closeFiscalShift,
  configureLocalFiscal,
  fiscalBindingOf,
  fiscalBindingRefreshed,
  fiscalErrorOf,
  fiscalSigned,
  signFiscalReceipt,
  type FiscalBinding,
  type LocalFiscalDeps,
  type SignInput,
  type Signed,
} from "./model/index.ts";
export { FiscalBridgeBanner, FiscalNotConnected } from "./ui/FiscalBridgeBanner.tsx";

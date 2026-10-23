/** UX-INSTALL platform detection lives in `@shared/lib/platform` (the shell's iOS gate uses it too). */
export {
  currentPlatform,
  detectPlatform,
  INSTALL_PLATFORMS,
  IOS_INSTALL_PATH,
  isInstallPlatform,
  isIosNotInstalled,
  isStandalone,
  type InstallPlatform,
  type PlatformProbe,
} from "@shared/lib/platform";

export const CLOUD_PRINT_ANCHOR = "cloud-print";

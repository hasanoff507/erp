/**
 * ios-install-gate — UX-INSTALL (b) (07, 24 §6.2): on iPhone/iPad in a Safari tab (not the installed
 * Home Screen app) ITP may wipe IndexedDB, so
 *   - `/pos/*` is blocked → `/install?platform=ios`;
 *   - the back-office stays usable with a top banner linking to the same guide.
 */
import { Smartphone } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, Navigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { IOS_INSTALL_PATH, isIosNotInstalled } from "@shared/lib/platform";
import { Banner, Button } from "@shared/ui";

export function IosPosGate({ children }: { children: ReactNode }) {
  const [blocked] = useState(isIosNotInstalled);
  return blocked ? <Navigate to={IOS_INSTALL_PATH} replace /> : <>{children}</>;
}

export function IosInstallBanner() {
  const { t } = useTranslation("onboarding");
  const [visible] = useState(isIosNotInstalled);
  if (!visible) return null;
  return (
    <Banner
      tone="warning"
      icon={Smartphone}
      className="rounded-none border-x-0 border-t-0"
      action={
        <Button asChild size="sm" variant="warning">
          <Link to={IOS_INSTALL_PATH}>{t("iosBanner.action")}</Link>
        </Button>
      }
    >
      {t("iosBanner.text")}
    </Banner>
  );
}

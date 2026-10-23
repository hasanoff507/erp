/**
 * UX-INSTALL — `/install` (07): public, no session needed (also before login). `?platform=ios` comes
 * from the iOS rule (POS blocked when not installed), `#cloud-print` from POS-04.
 */
import { useEffect } from "react";
import { useLocation, useSearchParams } from "react-router-dom";

import { loginStartUrl } from "@shared/api";
import { useTranslation } from "@shared/i18n";

import { CLOUD_PRINT_ANCHOR } from "#/features/install-guide/lib/platform.ts";
import { InstallGuide } from "#/features/install-guide/ui/InstallGuide.tsx";
import { PublicFrame } from "#/shared/ui/PublicFrame.tsx";

function InstallPage() {
  const { t } = useTranslation("onboarding");
  const [params] = useSearchParams();
  const { hash } = useLocation();

  // The SPA renders after the browser's own hash scroll — repeat it for #cloud-print.
  useEffect(() => {
    if (hash === `#${CLOUD_PRINT_ANCHOR}`) document.getElementById(CLOUD_PRINT_ANCHOR)?.scrollIntoView();
  }, [hash]);

  return (
    <PublicFrame title={t("install.pageTitle")} width="wide">
      <h1 className="text-[28px] font-extrabold leading-tight">{t("install.pageTitle")}</h1>
      <InstallGuide requestedPlatform={params.get("platform")} />
      <p className="text-[14px]">
        <a href={loginStartUrl({ returnTo: "/" })}>{t("install.back")}</a>
      </p>
    </PublicFrame>
  );
}

export const Install = {
  route: "/install",
  titleKey: "onboarding:install.pageTitle",
  Page: InstallPage,
} as const;

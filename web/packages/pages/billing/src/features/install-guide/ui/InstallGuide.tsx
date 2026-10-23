/**
 * UX-INSTALL (07): `<InstallGuide />` on `/install` and `<InstallGuide embedded />` in BO-21 ⑥ — one
 * component, no copy. Platform auto-detected with a manual switch; iOS 3 steps + data-loss warning;
 * Android/Chrome install button from `beforeinstallprompt`; Windows store agent; cloud printer section
 * (`#cloud-print`, linked from POS-04). All text ships in the JS bundle, which the service worker
 * precaches, so the guide also opens offline (24 §6).
 */
import { useUnit } from "effector-react";
import {
  CircleCheck,
  Download,
  MonitorSmartphone,
  Printer,
  Share,
  SquarePlus,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import { useEffect } from "react";

import { useTranslation } from "@shared/i18n";
import { Banner, Button, Card, CardTitle, Icon, SegmentedControl, StatusChip } from "@shared/ui";

import { CLOUD_PRINT_ANCHOR, INSTALL_PLATFORMS, type InstallPlatform } from "../lib/platform.ts";
import {
  $detected,
  $installed,
  $installOutcome,
  $installPrompt,
  $platform,
  $standalone,
  guideMounted,
  installClicked,
  platformSelected,
} from "../model/index.ts";

export interface InstallGuideProps {
  /** Inside BO-21 ⑥ (no page title, compact spacing). */
  embedded?: boolean;
  /** `?platform=` (ios | android | windows); anything else → auto-detect. */
  requestedPlatform?: string | null;
}

function NumberedSteps({ items }: { items: readonly { key: string; icon: LucideIcon; text: string }[] }) {
  return (
    <ol className="flex flex-col gap-2.5">
      {items.map((item, index) => (
        <li key={item.key} className="flex items-start gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[13px] font-extrabold text-primary-strong">
            {index + 1}
          </span>
          <span className="flex items-center gap-2 pt-0.5 text-[14px]">
            <Icon as={item.icon} size="md" className="shrink-0 text-foreground-secondary" />
            {item.text}
          </span>
        </li>
      ))}
    </ol>
  );
}

function PlatformSection({ platform }: { platform: InstallPlatform }) {
  const { t } = useTranslation("onboarding");
  const [prompt, outcome, onInstall] = useUnit([$installPrompt, $installOutcome, installClicked]);

  if (platform === "ios") {
    return (
      <Card className="flex flex-col gap-3.5" data-testid="install-ios">
        <CardTitle>{t("install.ios.title")}</CardTitle>
        <NumberedSteps
          items={[
            { key: "safari", icon: MonitorSmartphone, text: t("install.ios.steps.safari") },
            { key: "share", icon: Share, text: t("install.ios.steps.share") },
            { key: "add", icon: SquarePlus, text: t("install.ios.steps.add") },
          ]}
        />
        <Banner tone="warning" icon={TriangleAlert}>
          {t("install.ios.warning")}
        </Banner>
        <p className="text-[13px] text-foreground-secondary">{t("install.ios.posNote")}</p>
      </Card>
    );
  }

  if (platform === "android") {
    return (
      <Card className="flex flex-col gap-3.5" data-testid="install-android">
        <CardTitle>{t("install.android.title")}</CardTitle>
        {prompt ? (
          <Button className="self-start" onClick={() => onInstall()}>
            <Icon as={Download} size="md" />
            {t("install.android.installButton")}
          </Button>
        ) : (
          <p className="text-[14px]">{t("install.android.manual")}</p>
        )}
        {outcome ? (
          <p role="status" className="text-[13px] text-foreground-secondary">
            {t(`install.android.${outcome}`)}
          </p>
        ) : null}
        <p className="text-[13px] text-foreground-secondary">{t("install.android.printers")}</p>
      </Card>
    );
  }

  return (
    <Card className="flex flex-col gap-3.5" data-testid="install-windows">
      <CardTitle>{t("install.windows.title")}</CardTitle>
      {prompt ? (
        <Button className="self-start" onClick={() => onInstall()}>
          <Icon as={Download} size="md" />
          {t("install.android.installButton")}
        </Button>
      ) : (
        <p className="text-[14px]">{t("install.windows.installApp")}</p>
      )}
      <div className="flex flex-col gap-1 rounded-lg bg-accent px-3.5 py-3">
        <span className="text-[14px] font-bold">{t("install.windows.agentTitle")}</span>
        <span className="text-[13px] text-foreground-secondary">{t("install.windows.agentText")}</span>
      </div>
      <p className="text-[13px] text-foreground-secondary">{t("install.windows.labelPrinter")}</p>
    </Card>
  );
}

function CloudPrinterSection() {
  const { t } = useTranslation("onboarding");
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  return (
    <Card id={CLOUD_PRINT_ANCHOR} className="flex scroll-mt-4 flex-col gap-3.5">
      <div className="flex items-center gap-2">
        <Icon as={Printer} size="lg" className="text-primary" />
        <CardTitle>{t("install.cloud.title")}</CardTitle>
      </div>
      <p className="text-[14px] text-foreground-secondary">{t("install.cloud.text")}</p>
      <ol className="flex list-decimal flex-col gap-1.5 pl-5 text-[14px]">
        <li>{t("install.cloud.steps.network")}</li>
        <li>
          {t("install.cloud.steps.url")}
          <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[13px]">
            <dt className="font-bold">{t("install.cloud.starUrl")}</dt>
            <dd className="break-all font-mono">{`${origin}/print/cloudprnt`}</dd>
            <dt className="font-bold">{t("install.cloud.epsonUrl")}</dt>
            <dd className="break-all font-mono">{`${origin}/print/epson-sdp`}</dd>
          </dl>
        </li>
        <li>{t("install.cloud.steps.interval")}</li>
      </ol>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" disabled>
          {t("install.cloud.testPrint")}
        </Button>
        <span className="text-[12px] text-muted-foreground">{t("install.cloud.testPrintLater")}</span>
      </div>
      <p className="text-[13px] text-foreground-secondary">{t("install.cloud.fallback")}</p>
    </Card>
  );
}

export function InstallGuide({ embedded = false, requestedPlatform = null }: InstallGuideProps) {
  const { t } = useTranslation("onboarding");
  const [platform, detected, standalone, installed, select, mounted] = useUnit([
    $platform,
    $detected,
    $standalone,
    $installed,
    platformSelected,
    guideMounted,
  ]);

  useEffect(() => {
    mounted({ requested: requestedPlatform, embedded });
  }, [mounted, requestedPlatform, embedded]);

  return (
    <section className="flex flex-col gap-3.5" aria-label={t("install.pageTitle")}>
      {embedded ? null : <p className="text-[15px] text-foreground-secondary">{t("install.intro")}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <SegmentedControl<InstallPlatform>
          label={t("install.platformLabel")}
          value={platform}
          onChange={select}
          options={INSTALL_PLATFORMS.map((p) => ({
            value: p,
            label: p === detected ? `${t(`install.platforms.${p}`)} ✓` : t(`install.platforms.${p}`),
            ariaLabel:
              p === detected
                ? `${t(`install.platforms.${p}`)} — ${t("install.detected")}`
                : t(`install.platforms.${p}`),
          }))}
        />
        {standalone || installed ? (
          <StatusChip tone="success" icon={CircleCheck}>
            {t("install.installedChip")}
          </StatusChip>
        ) : null}
      </div>
      <PlatformSection platform={platform} />
      <CloudPrinterSection />
    </section>
  );
}

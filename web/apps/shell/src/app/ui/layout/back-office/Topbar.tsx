/**
 * Back-office topbar — 06 §1.9 / 08 §6.2, mockup Bo02Dashboard.dc.html: white, bottom border,
 * px-7 py-4; page title (text-h1); search — the `Ctrl+K` command palette trigger (cmdk, 08 §9: screens
 * by permission, products, counterparties); branch select; notifications bell (only with
 * reports.sales.view — the BO-02 alerts, WEB-12); «UZ · RU» on the far right. The pending-approvals
 * badge is on the «Tasdiqlash navbati» sidebar item (06 §1.9). The user is NOT shown here (sidebar
 * card only).
 */
import { Menu } from "lucide-react";
import { useMemo } from "react";

import { useTranslation } from "@shared/i18n";
import { SETTINGS_TABS } from "@shared/lib/settings-tabs";
import { Can, hasPermissions, useGrantedAccess } from "@shared/state/permissions";
import { Button, Icon } from "@shared/ui";

import { CommandPalette, PaletteTrigger, type PaletteScreen } from "#/features/command-palette/index.ts";
import { LanguageSwitcher } from "#/features/language-switcher/index.ts";
import { NotificationsBell } from "#/features/notifications-bell/index.ts";
import { BranchSelect } from "#/features/tenant-switcher/index.ts";

import { NAV_GROUPS, navItemTarget, paletteSearchRights } from "../../sidebar/nav-items.ts";
import { usePageTitle } from "./use-page-title.ts";

function usePaletteScreens(): PaletteScreen[] {
  const { t } = useTranslation();
  const { t: ts } = useTranslation("settings");
  const granted = useGrantedAccess();
  return useMemo(() => {
    const screens: PaletteScreen[] = NAV_GROUPS.flatMap((g) =>
      g.items
        .filter((item) => item.key !== "settings" && hasPermissions(granted, item.requires))
        .map((item) => ({
          key: item.key,
          label: t(`nav.items.${item.key}`),
          to: navItemTarget(item, granted),
          icon: item.icon,
          keywords: t(`nav.groups.${g.key}`),
        })),
    );
    const settingsIcon = NAV_GROUPS.flatMap((g) => g.items).find((i) => i.key === "settings")?.icon;
    if (settingsIcon) {
      for (const tab of SETTINGS_TABS) {
        if (!hasPermissions(granted, tab.requires)) continue;
        screens.push({
          key: `settings-${tab.key}`,
          label: `${t("nav.items.settings")} · ${ts(`nav.${tab.key}`)}`,
          to: tab.to,
          icon: settingsIcon,
        });
      }
    }
    return screens;
  }, [t, ts, granted]);
}

export function Topbar({ onOpenMenu }: { onOpenMenu: () => void }) {
  const { t } = useTranslation();
  const title = usePageTitle();
  const granted = useGrantedAccess();
  const screens = usePaletteScreens();
  const { products, counterparties } = paletteSearchRights(granted);
  const rights = useMemo(() => ({ products, counterparties }), [products, counterparties]);

  return (
    <header className="sticky top-0 z-sticky-header flex flex-wrap items-center gap-3 border-b border-border bg-card px-4 py-4 md:px-7">
      <Button
        variant="outline"
        size="icon"
        className="h-[42px] w-[42px] md:hidden"
        aria-label={t("topbar.openMenu")}
        onClick={onOpenMenu}
      >
        <Icon as={Menu} size="lg" />
      </Button>
      <h1 className="min-w-0 truncate text-h1">{title}</h1>
      <div className="grow" />
      <PaletteTrigger rights={rights} />
      <CommandPalette screens={screens} />
      <BranchSelect />
      <Can permission="reports.sales.view">
        <NotificationsBell />
      </Can>
      <LanguageSwitcher />
    </header>
  );
}

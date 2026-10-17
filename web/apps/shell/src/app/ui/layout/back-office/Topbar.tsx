/**
 * Back-office topbar — 06 §1.9 / 08 §6.2, mockup Bo02Dashboard.dc.html: white, bottom border,
 * px-7 py-4; page title (text-h1); search (min 240px, muted background; Ctrl+K focuses it — the cmdk
 * palette arrives later, 08 §9); branch select; notifications bell (only with reports.sales.view) — its
 * list (BO-02 alerts / M18) is Bosqich 4, so the bell opens a «Tez orada» panel (WEB-12; the Bosqich 3
 * part — the pending-approvals badge — is on the «Tasdiqlash navbati» sidebar item, 06 §1.9);
 * «UZ · RU» on the far right. The user is NOT shown here (sidebar card only).
 */
import { Bell, BellOff, Menu, Search } from "lucide-react";
import { useEffect, useRef } from "react";

import { useTranslation } from "@shared/i18n";
import { Can } from "@shared/state/permissions";
import { Button, Icon, Popover, PopoverContent, PopoverTrigger } from "@shared/ui";

import { LanguageSwitcher } from "#/features/language-switcher/index.ts";
import { BranchSelect } from "#/features/tenant-switcher/index.ts";

import { usePageTitle } from "./use-page-title.ts";

export function Topbar({ onOpenMenu }: { onOpenMenu: () => void }) {
  const { t } = useTranslation();
  const title = usePageTitle();
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

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
      <label className="hidden h-[42px] min-w-[240px] items-center gap-2 rounded-lg border border-input bg-muted px-3 focus-within:border-primary focus-within:shadow-focus-soft sm:flex">
        <Icon as={Search} size="md" className="shrink-0 text-muted-foreground" />
        <span className="sr-only">{t("topbar.searchLabel")}</span>
        <input
          ref={searchRef}
          type="search"
          placeholder={t("topbar.searchPlaceholder")}
          className="min-w-0 flex-1 bg-transparent text-[14px] text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-0 focus-visible:ring-offset-0"
        />
      </label>
      <BranchSelect />
      <Can permission="reports.sales.view">
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              className="h-[42px] w-[42px]"
              aria-label={t("topbar.notifications")}
            >
              <Icon as={Bell} size="lg" />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-72" aria-label={t("topbar.notifications")}>
            <div className="flex flex-col items-center gap-2 py-3 text-center">
              <Icon as={BellOff} size="lg" className="text-muted-foreground" />
              <p className="text-[14px] font-bold">{t("notificationsPanel.title")}</p>
              <p className="text-small text-foreground-secondary">{t("notificationsPanel.soon")}</p>
            </div>
          </PopoverContent>
        </Popover>
      </Can>
      <LanguageSwitcher />
    </header>
  );
}

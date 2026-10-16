import { NavLink } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { SETTINGS_TABS } from "@shared/lib/settings-tabs";
import { useGrantedAccess, hasPermissions } from "@shared/state/permissions";
import { cn } from "@shared/ui";

export function SettingsNav() {
  const { t } = useTranslation("settings");
  const granted = useGrantedAccess();
  // 06 §1.9 — the shared tab list (order + permissions), the same one the shell sidebar links to.
  const tabs = SETTINGS_TABS.filter((tab) => hasPermissions(granted, tab.requires));
  if (tabs.length < 2) return null;

  return (
    <nav aria-label={t("nav.label")} className="-mx-1 overflow-x-auto">
      <ul className="flex w-max gap-1 px-1">
        {tabs.map((tab) => (
          <li key={tab.key}>
            <NavLink
              to={tab.to}
              className={({ isActive }) =>
                cn(
                  "inline-flex h-9 items-center rounded-full px-4 text-[13px] font-bold transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  isActive
                    ? "bg-foreground text-background"
                    : "text-foreground-secondary hover:bg-accent hover:text-foreground",
                )
              }
            >
              {t(`nav.${tab.key}`)}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

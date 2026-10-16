/**
 * Back-office sidebar — 08 §6.2 / §7.4 "Sidebar", 06 §1.9, mockup Bo02Dashboard.dc.html:
 * dark (sidebar tokens), logo tile + «ERP» + store name, overline group titles, 18px icons,
 * active item = sidebar-accent background + white text (no left stripe), user card at the bottom.
 *
 * `variant="rail"`: ≥1024px full width (260px), 768–1023px icon-only (w-16). `variant="drawer"`:
 * full labels inside the <768px off-canvas menu.
 */
import { useUnit } from "effector-react";
import { NavLink, useLocation } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { hasPermissions, useGrantedAccess } from "@shared/state/permissions";
import { $tenant } from "@shared/state/session";
import { cn, Icon, LogoMark } from "@shared/ui";

import { NAV_GROUPS, navItemForPath } from "./nav-items.ts";
import { UserCard } from "./UserCard.tsx";

export interface SidebarProps {
  variant: "rail" | "drawer";
  onNavigate?: () => void;
}

export function Sidebar({ variant, onNavigate }: SidebarProps) {
  const { t } = useTranslation();
  const granted = useGrantedAccess();
  const tenant = useUnit($tenant);
  const { pathname } = useLocation();
  const activeKey = navItemForPath(pathname)?.key;
  const rail = variant === "rail";
  // In the rail, text is hidden between md and lg (icon-only); in the drawer it is always shown.
  const label = rail ? "md:sr-only lg:not-sr-only" : "";

  const groups = NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => hasPermissions(granted, item.requires)),
  })).filter((group) => group.items.length > 0);

  return (
    <nav
      aria-label={t("nav.label")}
      className={cn(
        "flex h-full flex-col gap-1 bg-sidebar py-5 text-sidebar-foreground",
        rail ? "w-16 px-2 lg:w-[260px] lg:px-3.5" : "w-[280px] px-3.5",
      )}
    >
      <div
        className={cn(
          "flex items-center gap-2.5 pb-[18px]",
          rail ? "justify-center lg:justify-start lg:px-2" : "px-2",
        )}
      >
        <LogoMark />
        <div className={cn("min-w-0", label)}>
          <div className="text-[15px] font-extrabold text-sidebar-accent-foreground">{t("app.name")}</div>
          <div className="truncate text-[12px] text-sidebar-muted-foreground">
            {tenant?.name ?? t("app.storePlaceholder")}
          </div>
        </div>
      </div>

      <div className="-mx-1 flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-1">
        {groups.map((group) => (
          <div key={group.key} className="flex flex-col gap-1">
            <div
              className={cn(
                "px-2.5 pb-1.5 pt-3.5 text-overline text-sidebar-muted-foreground",
                rail && "md:hidden lg:block",
              )}
            >
              {t(`nav.groups.${group.key}`)}
            </div>
            {group.items.map((item) => {
              const active = item.key === activeKey;
              const text = t(`nav.items.${item.key}`);
              return (
                <NavLink
                  key={item.key}
                  to={item.to}
                  onClick={onNavigate}
                  title={rail ? text : undefined}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2.5 rounded-md px-3 py-2.5 text-[14px] font-semibold no-underline transition-colors",
                    "focus-visible:ring-sidebar-ring focus-visible:ring-offset-sidebar",
                    rail && "md:justify-center md:px-0 lg:justify-start lg:px-3",
                    active
                      ? "bg-sidebar-accent text-sidebar-accent-foreground hover:text-sidebar-accent-foreground"
                      : "text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                  )}
                >
                  <Icon as={item.icon} size="md" className="shrink-0" />
                  <span className={cn("flex-1 truncate", label)}>{text}</span>
                </NavLink>
              );
            })}
          </div>
        ))}
      </div>

      <UserCard compact={rail} />
    </nav>
  );
}

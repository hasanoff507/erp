/**
 * Sidebar user card — 06 §1.9 / 08 §6.2: avatar + name + role at the bottom of the sidebar only
 * (never in the topbar); clicking opens a menu with «Chiqish» and «Barcha seanslarni tugatish»
 * (POST /auth/sessions/revoke-all, 14 §20). A modal Radix menu: its scroll-lock <style> carries the
 * CSP nonce (get-nonce, 24 §4.4). A failed logout keeps the user signed in and says so ($logoutError).
 * On a POS device browser both actions first apply the POS logout rules and wipe the POS cache
 * (SEC-07, features/device-logout).
 */
import { useUnit } from "effector-react";
import { LogOut, MonitorX, TriangleAlert } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { $logoutError, $roleCodes, $tenant, $user, LOGOUT_FAILED_KEY } from "@shared/state/session";
import {
  Avatar,
  Banner,
  cn,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Icon,
} from "@shared/ui";

import {
  $deviceBoundSession,
  DeviceLogoutDialog,
  deviceLogoutRequested,
} from "#/features/device-logout/index.ts";

const KNOWN_ROLES = ["owner", "manager", "accountant", "cashier", "storekeeper"] as const;
type KnownRole = (typeof KNOWN_ROLES)[number];
const isKnownRole = (code: string): code is KnownRole => (KNOWN_ROLES as readonly string[]).includes(code);

/** Translated label of the user's primary role (sidebar card, POS bar). */
export function useRoleLabel(): string | null {
  const { t } = useTranslation();
  const role = useUnit($roleCodes).find(isKnownRole);
  return role ? t(`user.roles.${role}`) : null;
}

export function UserCard({ compact }: { compact: boolean }) {
  const { t } = useTranslation();
  const [user, tenant, logoutError, requestLogout, deviceBound] = useUnit([
    $user,
    $tenant,
    $logoutError,
    deviceLogoutRequested,
    $deviceBoundSession,
  ]);
  const roleLabel = useRoleLabel();
  if (!user) return null;

  const label = compact ? "md:sr-only lg:not-sr-only" : "";

  return (
    <div className="mt-auto flex flex-col">
      {logoutError ? (
        <Banner
          tone="destructive"
          icon={TriangleAlert}
          live="assertive"
          className={cn(
            "mb-2 text-[12px]",
            // Icon rail (md): float next to the rail instead of squeezing into 64px.
            compact && "md:fixed md:bottom-4 md:left-20 md:z-overlay md:w-72 lg:static lg:w-auto",
          )}
        >
          {t(LOGOUT_FAILED_KEY)}
        </Banner>
      ) : null}
      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label={t("user.menuLabel")}
          className={cn(
            "flex w-full items-center gap-2.5 rounded-lg bg-sidebar-accent p-3 text-left",
            "focus-visible:ring-sidebar-ring focus-visible:ring-offset-sidebar",
            compact && "md:justify-center md:p-2 lg:justify-start lg:p-3",
          )}
        >
          <Avatar name={user.full_name} />
          <span className={cn("min-w-0 flex-1", label)}>
            <span className="block truncate text-[13px] font-bold text-sidebar-accent-foreground">
              {user.full_name}
            </span>
            {roleLabel ? (
              <span className="block truncate text-[12px] text-sidebar-muted-foreground">{roleLabel}</span>
            ) : null}
          </span>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="start" className="w-60">
          {tenant ? <DropdownMenuLabel>{tenant.name}</DropdownMenuLabel> : null}
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => requestLogout("logout")}>
            <Icon as={LogOut} size="md" />
            {t("actions.logout")}
          </DropdownMenuItem>
          {deviceBound ? null : (
            <DropdownMenuItem onSelect={() => requestLogout("revokeAll")}>
              <Icon as={MonitorX} size="md" />
              {t("user.revokeAll")}
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      <DeviceLogoutDialog />
    </div>
  );
}

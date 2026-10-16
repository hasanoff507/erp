/**
 * Web POS shell — placeholder (08 §6.1, 06 §1.3, mockup Main.dc.html top bar).
 * Full screen, kiosk-locked light theme and `touch` density (≥48px targets). 64px status bar:
 * logo · branch/register · shift │ online/offline chip (always visible, 06 §1.3) │ printer chip │
 * UZ · RU │ cashier. Screens (POS-01…16) render in the content area below.
 */
import { useUnit } from "effector-react";
import { Printer } from "lucide-react";
import { Outlet } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { $activeShift } from "@shared/state/device";
import { $isOnline } from "@shared/state/network";
import { $activeBranch, $user } from "@shared/state/session";
import { Avatar, LogoMark, StatusChip } from "@shared/ui";

import { LanguageSwitcher } from "#/features/language-switcher/index.ts";

import { useDocumentAttributes } from "../document-attributes.ts";

export function PosLayout() {
  useDocumentAttributes({ density: "touch", theme: "light" });
  const { t } = useTranslation("pos");
  const [online, branch, user, shift] = useUnit([$isOnline, $activeBranch, $user, $activeShift]);

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-background text-body-pos">
      <header className="z-pos-statusbar flex h-16 shrink-0 items-center gap-3.5 border-b border-border bg-card px-5">
        <LogoMark />
        <div className="flex min-w-0 flex-col">
          <span className="truncate text-[15px] font-extrabold">
            {branch ? `${branch.name} · ` : ""}
            {t("shell.register", { number: 1 })}
          </span>
          <span className="truncate text-[12px] text-muted-foreground">
            {shift ? `#${shift.number}` : t("shell.shiftClosed")}
          </span>
        </div>
        <div className="grow" />
        <span aria-live="polite">
          <StatusChip tone={online ? "success" : "warning"} dot>
            {online ? t("shell.onlineSynced") : t("shell.offline")}
          </StatusChip>
        </span>
        <StatusChip tone="neutral" icon={Printer} className="hidden lg:inline-flex">
          {t("shell.printerNotConfigured")}
        </StatusChip>
        <LanguageSwitcher density="touch" />
        {user ? (
          <div className="flex items-center gap-2.5 pl-1.5">
            <Avatar name={user.full_name} size={36} />
            <span className="hidden text-[13px] font-bold sm:inline">{user.full_name}</span>
          </div>
        ) : null}
      </header>
      <main className="min-h-0 flex-1 p-4">
        <Outlet />
      </main>
    </div>
  );
}

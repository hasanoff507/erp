/**
 * Web POS shell (08 §6.1, 06 §1.3, mockup Main.dc.html top bar). Full screen, kiosk-locked light theme and
 * `touch` density (≥48px targets). 64px status bar: logo · branch · register · shift (#n · since hh:mm) │
 * online/offline + sync chip (always visible, 06 §1.3; opens POS-12) │ 48 h ladder chip (24 h 🟡, 40 h 🔴,
 * 48 h ⛔ — qaror #43) │ printer chip (device printer settings + Do'kon agenti) │ UZ · RU │ cashier menu.
 * `PosBootstrap` (@pages/pos) starts the offline engine / agent and guards the routes (POS-01 redirect).
 */
import { useUnit } from "effector-react";
import { CircleAlert, Lock, Printer, RefreshCw, WifiOff } from "lucide-react";
import { useState } from "react";
import { Link, Outlet } from "react-router-dom";

import { PosBootstrap, PosCashierMenu, usePosHeader, type PrinterChip } from "@pages/pos";
import { useTranslation } from "@shared/i18n";
import { $fiscalLadder, type FiscalLadderLevel } from "@shared/offline";
import { $syncState } from "@shared/state/sync";
import { Avatar, LogoMark, Popover, PopoverContent, PopoverTrigger, StatusChip, type Tone } from "@shared/ui";

import { LanguageSwitcher } from "#/features/language-switcher/index.ts";

import { useDocumentAttributes } from "../document-attributes.ts";

const TASHKENT_TIME = new Intl.DateTimeFormat("ru-RU", {
  timeZone: "Asia/Tashkent",
  hour: "2-digit",
  minute: "2-digit",
});

const PRINTER_TONE: Record<PrinterChip, Tone> = {
  ready: "success",
  not_configured: "neutral",
  unavailable: "warning",
  error: "destructive",
  unknown: "neutral",
};

const LADDER_TONE: Record<FiscalLadderLevel, Tone> = {
  ok: "success",
  warn24: "warning",
  red40: "destructive",
  modal46: "destructive",
  blocked48: "destructive",
};

function SyncChip() {
  const { t } = useTranslation("pos");
  const sync = useUnit($syncState);
  const unsynced = sync.pending + sync.rejected;
  let text: string;
  let tone: Tone;
  if (!sync.online) {
    text = unsynced ? t("shell.offlineCount", { n: unsynced }) : t("shell.offline");
    tone = "warning";
  } else if (sync.rejected) {
    text = t("shell.syncRejected", { n: sync.rejected });
    tone = "destructive";
  } else if (sync.pending) {
    text = t("shell.syncPending", { n: sync.pending });
    tone = "info";
  } else {
    text = t("shell.onlineSynced");
    tone = "success";
  }
  return (
    <Link
      to="/pos/sync"
      aria-live="polite"
      data-testid="sync-chip"
      className="rounded-full focus-visible:ring-2"
    >
      <StatusChip
        tone={tone}
        size={sync.online ? "sm" : "md"}
        className="min-h-12"
        dot={sync.online}
        icon={sync.online ? (unsynced ? RefreshCw : undefined) : WifiOff}
      >
        {text}
      </StatusChip>
    </Link>
  );
}

function LadderChip() {
  const { t } = useTranslation("pos");
  const ladder = useUnit($fiscalLadder);
  if (ladder.level === "ok") return null;
  const hours = Math.floor(ladder.hours);
  return (
    <Link to="/pos/sync" data-testid="ladder-chip">
      <StatusChip
        tone={LADDER_TONE[ladder.level]}
        size="md"
        className="min-h-12"
        icon={ladder.level === "blocked48" ? Lock : CircleAlert}
      >
        {ladder.level === "blocked48" ? t("shell.ladderBlocked") : t("shell.ladderHours", { hours })}
      </StatusChip>
    </Link>
  );
}

function StatusBar() {
  const { t } = useTranslation("pos");
  const header = usePosHeader();
  const [menu, setMenu] = useState(false);
  const register = header.registerName ?? t("shell.noRegister");
  return (
    <header className="z-pos-statusbar flex h-16 shrink-0 items-center gap-3.5 border-b border-border bg-card px-5">
      <LogoMark />
      <div className="flex min-w-0 flex-col">
        <span className="truncate text-[15px] font-extrabold" data-testid="pos-register">
          {header.branchName ? `${header.branchName} · ` : ""}
          {register}
        </span>
        <span className="truncate text-[12px] text-muted-foreground" data-testid="pos-shift">
          {header.shiftNo !== null
            ? t("shell.shiftSince", {
                number: header.shiftNo,
                time: header.shiftOpenedAt ? TASHKENT_TIME.format(new Date(header.shiftOpenedAt)) : "",
              })
            : t("shell.shiftClosed")}
        </span>
      </div>
      <div className="grow" />
      <SyncChip />
      <LadderChip />
      <Link to="/pos/settings/devices" className="hidden lg:inline-flex" data-testid="printer-chip">
        <StatusChip tone={PRINTER_TONE[header.printer]} icon={Printer} className="min-h-12">
          {t(`shell.printer.${header.printer}`)}
        </StatusChip>
      </Link>
      <LanguageSwitcher density="touch" />
      {header.cashierName ? (
        <Popover open={menu} onOpenChange={setMenu}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="flex h-12 items-center gap-2.5 rounded-xl pl-1.5 pr-2 hover:bg-accent"
              data-testid="cashier-menu"
            >
              <Avatar name={header.cashierName} size={36} />
              <span className="hidden text-[13px] font-bold sm:inline">{header.cashierName}</span>
            </button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-72">
            <PosCashierMenu onNavigate={() => setMenu(false)} />
          </PopoverContent>
        </Popover>
      ) : null}
    </header>
  );
}

export function PosLayout() {
  useDocumentAttributes({ density: "touch", theme: "light" });
  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-background text-body-pos">
      <StatusBar />
      <main className="min-h-0 flex-1 p-4">
        <PosBootstrap>
          <Outlet />
        </PosBootstrap>
      </main>
    </div>
  );
}

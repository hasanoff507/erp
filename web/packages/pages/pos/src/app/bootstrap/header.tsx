/**
 * Data of the POS status bar (06 §1.3, 08, mockup Main.dc.html top bar) for the shell layout: branch · register
 * · shift, the cashier, the printer state (device printer settings + $agentStatus, re-checked every 30 s) and
 * the cashier menu («Bloklash» / «Chiqish» — b3-pos-ops `CashierActions`).
 */
import { useUnit } from "effector-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { Kbd } from "@shared/ui";

import { $agentStatus } from "@shared/state/device";

import { $posCashier, $posDevice, $posShift, cashierLocked } from "#/entities/pos-session/index.ts";
import { cardRecoveryRequested } from "#/features/card-payment/index.ts";
import { CashierActions } from "#/features/cashier-session/index.ts";
import { posPrinter, refreshPrinter } from "#/shared/lib/device-runtime.ts";

export type PrinterChip = "ready" | "not_configured" | "unavailable" | "error" | "unknown";

export interface PosHeader {
  branchName: string | null;
  registerName: string | null;
  shiftNo: number | null;
  shiftOpenedAt: string | null;
  cashierName: string | null;
  printer: PrinterChip;
}

const PRINTER_POLL_MS = 30_000;

export function usePosHeader(): PosHeader {
  const [device, shift, cashier, agent] = useUnit([$posDevice, $posShift, $posCashier, $agentStatus]);
  const [printer, setPrinter] = useState<PrinterChip>("unknown");
  useEffect(() => {
    let alive = true;
    const check = () => {
      refreshPrinter();
      void posPrinter()
        .then((port) => port.status())
        .then((s) => alive && setPrinter(s.state))
        .catch(() => alive && setPrinter("error"));
    };
    check();
    const timer = setInterval(check, PRINTER_POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [agent.status]);
  return {
    branchName: device?.branchName ?? null,
    registerName: device?.cashRegisterName ?? null,
    shiftNo: shift?.shift_no ?? null,
    shiftOpenedAt: shift?.opened_at ?? null,
    cashierName: cashier?.fullName ?? null,
    printer,
  };
}

/** Screen shortcuts of the cashier menu (07: F6 returns, F8 shift close — global keys; cash in/out; POS-16). */
export const MENU_LINKS = [
  { to: "/pos/returns", key: "returns", kbd: "F6" },
  { to: "/pos/cash-movement", key: "cashMovement", kbd: null },
  { to: "/pos/shift/close", key: "shiftClose", kbd: "F8" },
  { to: "/pos/sync", key: "sync", kbd: "F12" },
  { to: "/pos/settings/devices", key: "equipment", kbd: null },
] as const;

/** Status bar cashier menu: screen links + «Bloklash» / «Chiqish» (b3-pos-ops `CashierActions`, 16 §12). */
export function PosCashierMenu({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation("pos");
  const device = useUnit($posDevice);
  return (
    <div className="flex flex-col gap-1">
      <nav className="flex flex-col" aria-label={t("shell.menu.title")}>
        {MENU_LINKS.map((l) => (
          <Link
            key={l.to}
            to={l.to}
            onClick={onNavigate}
            className="flex h-12 items-center justify-between rounded-lg px-3 text-[14px] font-bold hover:bg-accent"
          >
            {t(`shell.menu.${l.key}`)}
            {l.kbd ? <Kbd keys={l.kbd} /> : null}
          </Link>
        ))}
      </nav>
      <CashierActions
        onLock={() => cashierLocked()}
        deviceId={device?.deviceId ?? null}
        onCardBlocked={() => cardRecoveryRequested()}
      />
    </div>
  );
}

/**
 * POS startup wiring (24 §5, 16 §1/§3/§9/§12; reports b3-offline, b3-hw, b3-card) — rendered once by the shell
 * POS layout around every /pos/* screen:
 * - @shared/offline: `configureOffline({transport})`, persistent storage, sync engine, catalog warm-up;
 * - Do'kon agenti: `agentProbeConfigured` + `agentPollingStarted` ($agentStatus, 10 s);
 * - POS session (b3-pos-ops entity) and `cardPaymentRestored` (unresolved card attempts keep blocking);
 * - route guard: no device / no PIN-verified cashier → `/pos/login?next=…` (POS-01; POS-16 `/pos/settings/devices`
 *   stays reachable);
 *   a cashier with `shift.open` but no open shift → POS-01 (step 2 opens it);
 * - `authRequired` → re-login overlay (the outbox is kept, never logout); `deviceRevoked` → export offer, then
 *   `wipeAfterRevoke()` (16 §12).
 */
import { createEvent, createStore, sample } from "effector";
import { useUnit } from "effector-react";
import { CircleAlert, Download, LogIn, ShieldX, Trash2 } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { loginStartUrl } from "@shared/api";
import { getRuntimeConfig } from "@shared/lib/runtime-config";
import { useTranslation } from "@shared/i18n";
import {
  authRequired,
  cardAttempts,
  catalog,
  configureOffline,
  createHttpSyncTransport,
  deviceRevoked,
  getSyncStatus,
  requestPersistentStorage,
  startSyncEngine,
  syncNow,
  wipeAfterRevoke,
} from "@shared/offline";
import { agentPollingStarted, agentProbeConfigured } from "@shared/state/device";
import {
  Banner,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Icon,
} from "@shared/ui";

import {
  $posCashier,
  $posDevice,
  $posKeysLocked,
  $posSessionStatus,
  $posShift,
  ActorPinPrompt,
  cashierCan,
  posSessionStarted,
} from "#/entities/pos-session/index.ts";
import {
  CardRecoveryDialog,
  cardPaymentRestored,
  cardRecoveryRequested,
} from "#/features/card-payment/index.ts";
import { fiscalBindingRefreshed } from "#/features/local-fiscal/index.ts";
import { downloadOutboxExport } from "#/pages/sync-status/ui/page/Page.tsx";
import { posAgentClient } from "#/shared/lib/device-runtime.ts";
import { recordPosPath } from "#/shared/lib/pos-history.ts";
import { isFKey, useHotkeys } from "#/shared/lib/use-hotkeys.ts";

export const LOGIN_PATH = "/pos/login";
/** Routes reachable without a PIN session (POS-01 itself, POS-16 equipment). */
const OPEN_PATHS = ["/pos/login", "/pos/settings/devices"];
/** Routes that need an open shift (sale flow). */
const SHIFT_PATHS = ["/pos/sale"];

let started = false;

/** One-time runtime start (idempotent — StrictMode / remounts). */
export function startPosRuntime(): void {
  if (started) return;
  started = true;
  configureOffline({ transport: createHttpSyncTransport() });
  void requestPersistentStorage().catch(() => undefined);
  posSessionStarted();
  startSyncEngine();
  void catalog.warmUp().catch(() => undefined);
  agentProbeConfigured(() => posAgentClient().probe());
  agentPollingStarted();
  fiscalBindingRefreshed(); // B5: local-bridge mode from the register's BO-12 binding (21 §16)
  if (getSyncStatus().deviceRevoked) revokedShown();
}

const reloginShown = createEvent();
const reloginDone = createEvent();
const revokedShown = createEvent();
export const $relogin = createStore(false)
  .on(reloginShown, () => true)
  .reset(reloginDone);
export const $revoked = createStore(false).on(revokedShown, () => true);

sample({ clock: authRequired, target: reloginShown });
sample({ clock: deviceRevoked, target: revokedShown });

// unresolved card attempts of this register come back after a reload (24 §6.5, b3-card)
sample({
  clock: $posSessionStatus,
  source: { device: $posDevice, shift: $posShift },
  filter: (_, status) => status === "ready",
  fn: ({ device, shift }) => ({ cashRegisterId: device?.cashRegisterId ?? null, shiftId: shift?.id ?? null }),
  target: cardPaymentRestored,
});

/** Where the guard sends the current path (null = stay). Pure — unit-tested. */
export function guardTarget(input: {
  pathname: string;
  search: string;
  status: "loading" | "no_device" | "locked" | "ready";
  hasShift: boolean;
  canOpenShift: boolean;
}): string | null {
  const { pathname, status } = input;
  if (status === "loading") return null;
  if (OPEN_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))) return null;
  const next = encodeURIComponent(`${pathname}${input.search}`);
  if (status !== "ready") return `${LOGIN_PATH}?next=${next}`;
  if (!input.hasShift && input.canOpenShift && SHIFT_PATHS.some((p) => pathname.startsWith(p))) {
    return `${LOGIN_PATH}?next=${next}`;
  }
  return null;
}

function ReloginOverlay() {
  const { t } = useTranslation("pos");
  const location = useLocation();
  return (
    <Dialog open>
      <DialogContent
        size="sm"
        hideClose
        onEscapeKeyDown={(e) => e.preventDefault()}
        data-testid="relogin-overlay"
      >
        <DialogHeader>
          <DialogTitle>{t("shell.reloginTitle")}</DialogTitle>
          <DialogDescription>{t("shell.reloginText")}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            size="pos"
            variant="secondary"
            onClick={() => {
              reloginDone();
              void syncNow({ push: true, pull: true });
            }}
          >
            {t("shell.reloginRetry")}
          </Button>
          <Button asChild size="pos">
            <a href={loginStartUrl({ returnTo: `${location.pathname}${location.search}` })}>
              <Icon as={LogIn} size="lg" />
              {t("shell.reloginAction")}
            </a>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function RevokedOverlay() {
  const { t } = useTranslation("pos");
  const [exported, setExported] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [confirmNoExport, setConfirmNoExport] = useState(false);
  const [cardBlocked, setCardBlocked] = useState(false);
  const wipe = async () => {
    setBusy(true);
    try {
      await wipeAfterRevoke();
      window.location.assign(LOGIN_PATH);
    } catch {
      setError(true);
      setBusy(false);
    }
  };
  return (
    <Dialog open>
      <DialogContent
        size="sm"
        hideClose
        onEscapeKeyDown={(e) => e.preventDefault()}
        data-testid="revoked-overlay"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icon as={ShieldX} size="xl" className="text-destructive" />
            {t("shell.revokedTitle")}
          </DialogTitle>
          <DialogDescription>{t("shell.revokedText")}</DialogDescription>
        </DialogHeader>
        {cardBlocked ? (
          <Banner tone="warning" icon={CircleAlert}>
            {t("shell.revokedCardBlocked")}
          </Banner>
        ) : null}
        {confirmNoExport && !exported ? (
          <Banner tone="warning" icon={CircleAlert}>
            {t("shell.revokedWipeConfirm")}
          </Banner>
        ) : null}
        {error ? (
          <Banner tone="destructive" icon={CircleAlert}>
            {t("shell.revokedWipeFailed")}
          </Banner>
        ) : null}
        <DialogFooter>
          <Button
            size="pos"
            variant="secondary"
            onClick={() =>
              void downloadOutboxExport()
                .then(() => setExported(true))
                .catch(() => setError(true))
            }
          >
            <Icon as={Download} size="lg" />
            {t("shell.revokedExport")}
          </Button>
          <Button
            size="pos"
            variant="destructive"
            disabled={busy}
            onClick={() => {
              if (!exported && !confirmNoExport) {
                setConfirmNoExport(true);
                return;
              }
              // 16 §12: a card attempt still on this device is money that may have moved — resolve it first
              if (!cardBlocked) {
                void cardAttempts.count().then((n) => {
                  if (n > 0) {
                    setCardBlocked(true);
                    cardRecoveryRequested();
                  } else void wipe();
                });
                return;
              }
              void wipe();
            }}
          >
            <Icon as={Trash2} size="lg" />
            {t("shell.revokedWipe")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Global POS screen keys (07 "(global)"): F6 returns, F7 debt book (B4), F8 shift close, F9 lookup, F12 sync. */
export const GLOBAL_KEYS: Readonly<Record<string, string>> = {
  F6: "/pos/returns",
  F7: "/pos/debts",
  F8: "/pos/shift/close",
  F9: "/pos/lookup",
  F12: "/pos/sync",
};

/**
 * Global keys active on `pathname`: none while a payment / receipt overlay owns the keyboard; the warehouse
 * screens keep F9 for «finish / submit» (contracts/pos-wh-routes.md), so the global F9 is off there.
 */
export function globalKeysFor(pathname: string): [string, string][] {
  if (/^\/pos\/sale\/(payment|receipt|credit)/.test(pathname)) return [];
  const warehouse = pathname === "/pos/warehouse" || pathname.startsWith("/pos/warehouse/");
  return Object.entries(GLOBAL_KEYS).filter(([key]) => !(warehouse && key === "F9"));
}

function GlobalHotkeys() {
  const navigate = useNavigate();
  const location = useLocation();
  const locked = useUnit($posKeysLocked);
  // UX-04: no browser default for F1–F12 on /pos/* (F1 help, F5 reload, F3 find…); F12 stays for dev builds
  useEffect(() => {
    const guard = (event: KeyboardEvent) => {
      if (!isFKey(event.key)) return;
      if (event.key === "F12" && getRuntimeConfig().environment === "dev") return;
      event.preventDefault();
    };
    window.addEventListener("keydown", guard, { capture: true });
    // readiness marker for kiosk monitoring / e2e: the global POS keys are live
    document.documentElement.dataset.posKeys = "on";
    return () => {
      window.removeEventListener("keydown", guard, { capture: true });
      delete document.documentElement.dataset.posKeys;
    };
  }, []);
  useHotkeys(
    globalKeysFor(location.pathname).map(([key, to]) => ({
      key,
      handler: () => {
        // UX-03: never navigate under an open dialog or while a screen holds the keyboard (POS-05 card refund)
        if (locked || document.querySelector('[role="dialog"]')) return false;
        void navigate(to);
        return true;
      },
    })),
  );
  return null;
}

export function PosBootstrap({ children }: { children: ReactNode }) {
  useEffect(() => startPosRuntime(), []);
  const location = useLocation();
  useEffect(() => recordPosPath(location.pathname), [location.pathname]);
  const [status, cashier, shift, relogin, revoked] = useUnit([
    $posSessionStatus,
    $posCashier,
    $posShift,
    $relogin,
    $revoked,
  ]);
  const target = guardTarget({
    pathname: location.pathname,
    search: location.search,
    status,
    hasShift: shift !== null,
    canOpenShift: cashierCan(cashier, "shift.open"),
  });
  if (target) return <Navigate to={target} replace />;
  return (
    <>
      {children}
      {status === "ready" ? <GlobalHotkeys /> : null}
      {/* online PIN re-prompt for 403 actor_not_verified (device-auth.md §4, b3-pos-ops) */}
      <ActorPinPrompt />
      {/* unresolved / dangling card attempts after a reload (SYNC-03, b3-card) */}
      {status === "ready" ? <CardRecoveryDialog /> : null}
      {relogin ? <ReloginOverlay /> : null}
      {revoked ? <RevokedOverlay /> : null}
    </>
  );
}

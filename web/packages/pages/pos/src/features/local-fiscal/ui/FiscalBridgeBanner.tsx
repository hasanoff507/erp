/**
 * B5-SCR-POS-02/03 fiscal banners of the local-bridge mode (07 POS-02/POS-03 «fiscal-blocked», 21 §16
 * «Fiskal modul ulanmagan», 24 §6.4): the agent / FM does not answer → the receipt is NOT closed, the cart is
 * kept and the cashier sees how to bring the agent back; the FM is locked → `FISCAL_DEVICE_LOCKED`. Local
 * states, not server codes. Nothing is shown in the server-fiscalisation mode.
 */
import { useUnit } from "effector-react";
import { CircleAlert, PlugZap, RefreshCw } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import type { LocalFiscalReadiness } from "@shared/lib/fiscal";
import { agentStatusRefreshRequested } from "@shared/state/device";
import { Banner, Button, Icon } from "@shared/ui";

import { $localFiscal } from "../model/index.ts";

const STEPS = ["step1", "step2", "step3"] as const;

/** «Fiskal modul ulanmagan» text + restart instructions (also used under a failed «TASDIQLASH»). */
type Reason = Extract<LocalFiscalReadiness, { state: "not_connected" }>["reason"];
const REASONS: ReadonlySet<string> = new Set<Reason>([
  "agent_offline",
  "agent_not_installed",
  "agent_unpaired",
  "capability_off",
  "device_missing",
  "fm_unknown",
]);

export function FiscalNotConnected({ reason }: { reason?: string | null }) {
  const { t } = useTranslation("pos");
  const why: Reason = reason && REASONS.has(reason) ? (reason as Reason) : "agent_offline";
  return (
    <div data-testid="fiscal-not-connected">
      <p className="font-extrabold">{t("fiscal.notConnected.title")}</p>
      <p className="font-normal">
        {t(`fiscal.notConnected.reason.${why}`)}
      </p>
      <ol className="mt-1 list-decimal pl-5 font-normal">
        {STEPS.map((s) => (
          <li key={s}>{t(`fiscal.notConnected.${s}`)}</li>
        ))}
      </ol>
    </div>
  );
}

export function FiscalBridgeBanner({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation("pos");
  const [state, refresh] = useUnit([$localFiscal, agentStatusRefreshRequested]);
  if (!state || state.state === "ready") return null;
  if (state.state === "locked") {
    return (
      <Banner tone="destructive" icon={CircleAlert} live="assertive">
        <span data-testid="fiscal-locked">{t("fiscal.locked", { state: state.fmState })}</span>
      </Banner>
    );
  }
  return (
    <Banner
      tone="destructive"
      icon={PlugZap}
      live="assertive"
      action={
        <Button size="sm" variant="secondary" onClick={() => refresh()} data-testid="fiscal-recheck">
          <Icon as={RefreshCw} size="sm" />
          {t("fiscal.recheck")}
        </Button>
      }
    >
      {compact ? (
        <span data-testid="fiscal-not-connected">{t("fiscal.notConnected.title")}</span>
      ) : (
        <FiscalNotConnected reason={state.reason} />
      )}
    </Banner>
  );
}

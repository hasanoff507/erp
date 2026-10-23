/**
 * POS-16 «Karta terminali» block (07 POS-16; qaror #71): terminals bound to this register (from the local
 * `settings` scope), «Aloqani tekshirish» (`health`, never a paid transaction), «Terminalni aniqlash»
 * (agent `GET /v1/card/terminals`) and «Bu kassaga bog'lash» (`cash_register.manage`). An agent terminal needs
 * the Do'kon agenti registry (`card_terminals.agent_id`, Bosqich 5) — it is bound in BO-12; the sinov (fake)
 * terminal can be bound here on dev/test/staging.
 */
import { CircleAlert, CreditCard, RefreshCw, Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api, toApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import {
  createCardTerminalClient,
  pickTerminal,
  terminalRef,
  type AgentCardTerminal,
  type TerminalInfo,
} from "@shared/lib/card-terminal";
import { formatDateTime } from "@shared/lib/date";
import { Banner, Button, Card, ConfirmDialog, EmptyState, Icon, toast } from "@shared/ui";

import { cardAgentClient, defaultCardPaymentDeps } from "../model/lib/deps.ts";
import type { TerminalChipStatus } from "../model/types/index.ts";
import { TerminalStatusChip } from "./TerminalStatusChip.tsx";
import { dyn } from "./i18n.ts";

export interface TerminalPairingSectionProps {
  cashRegisterId: string;
  branchId: string;
  canManage: boolean;
  /** tests / storybook override */
  loadTerminals?: (cashRegisterId: string) => Promise<TerminalInfo[]>;
}

interface Health {
  status: TerminalChipStatus;
  at: string;
  ms: number;
  error: boolean;
}

/** `health` of one terminal with the response time (never a paid transaction — 07 POS-16). */
async function probeHealth(terminal: TerminalInfo): Promise<Health> {
  const client = createCardTerminalClient(terminal, { agent: cardAgentClient() });
  const started = performance.now();
  const at = new Date().toISOString();
  try {
    if (!client) throw new Error("unreachable");
    const res = await client.health(terminalRef(terminal));
    return { status: res.status, at, ms: Math.round(performance.now() - started), error: false };
  } catch {
    return { status: "offline", at, ms: Math.round(performance.now() - started), error: true };
  }
}

export function TerminalPairingSection({
  cashRegisterId,
  branchId,
  canManage,
  loadTerminals,
}: TerminalPairingSectionProps) {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const [terminals, setTerminals] = useState<TerminalInfo[]>([]);
  const [health, setHealth] = useState<Record<string, Health>>({});
  const [found, setFound] = useState<AgentCardTerminal[] | null>(null);
  const [agentError, setAgentError] = useState(false);
  const [binding, setBinding] = useState<AgentCardTerminal | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const rows = await (loadTerminals ?? ((id: string) => defaultCardPaymentDeps().terminals(id)))(
      cashRegisterId,
    );
    setTerminals(rows);
  }, [cashRegisterId, loadTerminals]);

  useEffect(() => {
    let alive = true;
    const load = loadTerminals ?? ((id: string) => defaultCardPaymentDeps().terminals(id));
    load(cashRegisterId).then(
      (rows) => {
        if (alive) setTerminals(rows);
      },
      () => undefined,
    );
    return () => {
      alive = false;
    };
  }, [cashRegisterId, loadTerminals]);

  const check = async (terminal: TerminalInfo) => {
    const next = await probeHealth(terminal);
    setHealth((h) => ({ ...h, [terminal.id]: next }));
  };

  const discover = async () => {
    setAgentError(false);
    try {
      const client = createCardTerminalClient({ adapter: "agent_ecr" }, { agent: cardAgentClient() });
      setFound(client ? await client.listTerminals() : []);
    } catch {
      setFound(null);
      setAgentError(true);
    }
  };

  const bind = async (row: AgentCardTerminal) => {
    setError(null);
    try {
      await api.cardTerminals.createTerminal({
        branch_id: branchId,
        cash_register_id: cashRegisterId,
        name: row.local_id,
        vendor: "fake",
        adapter: "fake",
        driver: "fake",
        is_default: !pickTerminal(terminals),
      });
      toast.success(t("cardPayment.pairing.bound"));
      await reload();
    } catch (e) {
      setError(toApiError(e).code);
      throw e;
    }
  };

  const defaultTerminal = pickTerminal(terminals);

  return (
    <Card className="flex flex-col gap-3" data-testid="terminal-pairing">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex items-center gap-2 text-[15px] font-bold">
          <Icon as={CreditCard} size="sm" />
          {t("cardPayment.pairing.title")}
        </h2>
        <div className="grow" />
        <Button variant="secondary" size="lg" onClick={() => void discover()}>
          <Icon as={Search} size="sm" />
          {t("cardPayment.pairing.discover")}
        </Button>
      </div>

      {terminals.length === 0 ? (
        <EmptyState icon={CreditCard} title={t("cardPayment.pairing.none")} />
      ) : (
        <ul className="flex flex-col gap-2">
          {terminals.map((term) => {
            const h = health[term.id];
            return (
              <li
                key={term.id}
                className="flex flex-wrap items-center gap-3 rounded-lg border border-border p-3"
              >
                <div className="min-w-0 grow">
                  <p className="text-[14px] font-bold">
                    {t("cardPayment.terminalLine", { name: term.name, tid: term.tid ?? "—" })}
                    {term.id === defaultTerminal?.id ? " ★" : ""}
                  </p>
                  <p className="text-[12px] text-muted-foreground">
                    {t(`cardPayment.transport.${term.adapter}`)}
                    {term.host ? ` · ${term.host}` : ""}
                  </p>
                  {h ? (
                    <p className="text-[12px] text-muted-foreground">
                      {t("cardPayment.pairing.lastCheck", { time: formatDateTime(h.at) })} ·{" "}
                      {h.error
                        ? t("cardPayment.pairing.healthError")
                        : t("cardPayment.pairing.responseMs", { ms: h.ms })}
                    </p>
                  ) : null}
                </div>
                <TerminalStatusChip status={h?.status ?? "unknown"} />
                <Button variant="secondary" size="lg" onClick={() => void check(term)}>
                  <Icon as={RefreshCw} size="sm" />
                  {t("cardPayment.pairing.check")}
                </Button>
              </li>
            );
          })}
        </ul>
      )}

      {agentError ? (
        <Banner tone="warning" icon={CircleAlert}>
          {t("cardPayment.pairing.noAgent")}
        </Banner>
      ) : null}
      {found !== null ? (
        <div className="flex flex-col gap-2">
          <h3 className="text-[13px] font-bold">{t("cardPayment.pairing.found")}</h3>
          {found.length === 0 ? (
            <p className="text-[13px] text-muted-foreground">{t("cardPayment.pairing.noneFound")}</p>
          ) : null}
          {found.map((row) => (
            <div
              key={row.local_id}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-dashed border-input p-3"
            >
              <span className="grow text-[13px]">
                {row.local_id} · {row.driver} · TID {row.tid ?? "—"}
                {row.host ? ` · ${row.host}` : ""}
              </span>
              <TerminalStatusChip status={row.status} />
              {row.driver === "fake" && canManage ? (
                <Button size="lg" onClick={() => setBinding(row)}>
                  {t("cardPayment.pairing.bind")}
                </Button>
              ) : (
                <span className="text-[12px] text-muted-foreground">
                  {canManage ? t("cardPayment.pairing.agentBindLater") : t("cardPayment.pairing.needsManage")}
                </span>
              )}
            </div>
          ))}
        </div>
      ) : null}
      {binding ? (
        <ConfirmDialog
          open
          onOpenChange={(o) => (o ? undefined : setBinding(null))}
          title={t("cardPayment.pairing.bindTitle", { name: binding.local_id })}
          confirmLabel={t("cardPayment.pairing.bind")}
          error={error}
          onConfirm={() => bind(binding)}
        />
      ) : null}
    </Card>
  );
}

/**
 * Agent → device picker (07 BO-12 «Fiskal agent» and `cardTerminal.agentDevice`): the tenant's active agents
 * that report `family` enabled, then one of that agent's `capabilities.<family>.devices[]`. The parent owns the
 * values; `onChange` hands back the chosen agent and device (to prefill `local_id`, `host`, `tid`, `driver`).
 */
import { useUnit } from "effector-react";

import { useTranslation } from "@shared/i18n";
import { FormField, NativeSelect } from "@shared/ui";

import {
  $agents,
  agentsFor,
  deviceLabel,
  devicesOf,
  type AgentDevice,
  type CapabilityFamily,
  type StoreAgent,
} from "../model/index.ts";

const NONE = "";

export interface AgentDeviceChoice {
  agent: StoreAgent | null;
  device: AgentDevice | null;
}

export function AgentDevicePicker({
  family,
  agentId,
  localId,
  onChange,
  disabled,
  agentError,
  deviceError,
}: {
  family: CapabilityFamily;
  agentId: string;
  localId: string;
  onChange: (choice: AgentDeviceChoice) => void;
  disabled?: boolean;
  agentError?: string | null;
  deviceError?: string | null;
}) {
  const { t } = useTranslation("settings");
  const agents = agentsFor(useUnit($agents), family);
  const agent = agents.find((a) => a.id === agentId) ?? null;
  const devices = agent ? devicesOf(agent, family) : [];
  // A stored binding whose device the agent no longer reports is still shown (server re-validates).
  const deviceOptions =
    localId && !devices.some((d) => d.local_id === localId)
      ? [{ value: localId, label: localId }, ...devices.map((d) => ({ value: d.local_id, label: deviceLabel(d) }))]
      : devices.map((d) => ({ value: d.local_id, label: deviceLabel(d) }));
  const agentOptions =
    agentId && !agent
      ? [{ value: agentId, label: t("agents.unknownAgent") }, ...agents.map((a) => ({ value: a.id, label: a.name }))]
      : agents.map((a) => ({ value: a.id, label: `${a.name}${a.online ? "" : ` · ${t("agents.offline")}`}` }));

  return (
    <>
      <FormField label={t("agents.picker.agent")} error={agentError ?? null}>
        <NativeSelect
          value={agentId}
          disabled={disabled}
          onChange={(e) => {
            const next = agents.find((a) => a.id === e.target.value) ?? null;
            const first = next ? (devicesOf(next, family)[0] ?? null) : null;
            onChange({ agent: next, device: first });
          }}
          options={[{ value: NONE, label: t("agents.picker.chooseAgent") }, ...agentOptions]}
        />
      </FormField>
      <FormField label={t("agents.picker.device")} error={deviceError ?? null}>
        <NativeSelect
          value={localId}
          disabled={disabled || !agentId}
          onChange={(e) =>
            onChange({ agent, device: devices.find((d) => d.local_id === e.target.value) ?? null })
          }
          options={[{ value: NONE, label: t("agents.picker.chooseDevice") }, ...deviceOptions]}
        />
      </FormField>
      {agents.length === 0 ? (
        <p className="text-[12px] text-muted-foreground sm:col-span-2">{t(`agents.picker.none.${family}`)}</p>
      ) : null}
    </>
  );
}

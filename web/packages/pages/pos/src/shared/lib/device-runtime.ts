/**
 * POS device runtime shared by the screens (24 §6): one Do'kon agenti client (token in erp-device) and the
 * receipt `PrinterPort` built from the device printer settings (POS-16). The printer port is rebuilt on
 * demand (`refreshPrinter()` after POS-16 saves), so a changed transport is picked up without a reload.
 */
import { AGENT_TOKEN_KEY, createAgentClient, type AgentClient } from "@shared/lib/agent";
import { newAttemptId as newId } from "@shared/lib/card-terminal";
import { createPrinterPort, loadPrinterSettings, type PrinterPort } from "@shared/lib/printer";
import { deviceSettings } from "@shared/offline";
import { $agentStatus } from "@shared/state/device";

let agent: AgentClient | null = null;
let printer: Promise<PrinterPort> | null = null;

export function posAgentClient(): AgentClient {
  agent ??= createAgentClient({
    tokenStore: {
      get: () => deviceSettings.get<string>(AGENT_TOKEN_KEY).then((t) => t ?? null),
      set: (t) => (t ? deviceSettings.set(AGENT_TOKEN_KEY, t) : deviceSettings.remove(AGENT_TOKEN_KEY)),
    },
  });
  return agent;
}

export function posPrinter(): Promise<PrinterPort> {
  printer ??= loadPrinterSettings(deviceSettings).then((settings) =>
    createPrinterPort(settings, {
      agent: posAgentClient(),
      agentState: () => $agentStatus.getState(),
      newId: () => newId(),
    }),
  );
  return printer;
}

export function refreshPrinter(): void {
  printer = null;
}

const TEMP_SEQ_KEY = "pos.temp_seq";

/**
 * `temp_number = {device_id}-{local_seq}` (18 §4.1, 11 §6): a per-device counter in erp-device (survives
 * logout), incremented under a Web Lock so two tabs never hand out the same number.
 */
export async function nextTempNumber(deviceId: string): Promise<string> {
  const bump = async () => {
    const last = (await deviceSettings.get<number>(TEMP_SEQ_KEY)) ?? 0;
    const next = last + 1;
    await deviceSettings.set(TEMP_SEQ_KEY, next);
    return next;
  };
  const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
  const seq = locks ? await locks.request("erp-pos-temp-number", bump) : await bump();
  return `${deviceId}-${seq}`;
}

/**
 * Printing for the POS operation screens (Z-report on POS-07, return receipt on POS-05) through the
 * PrinterPort of 24 §6.1 (@shared/lib/printer): settings from erp-device, the Do'kon agenti client with its
 * token in erp-device, `$agentStatus` for the agent transport. Any PrinterError → the screen offers the
 * equipment settings (POS-16); nothing is lost — the document is in the outbox / on the server.
 */
import { AGENT_TOKEN_KEY, createAgentClient, type AgentClient } from "@shared/lib/agent";
import { createPrinterPort, loadPrinterSettings, PrinterError } from "@shared/lib/printer";
import type { ReceiptDoc } from "@shared/lib/receipt";
import { deviceSettings } from "@shared/offline";
import { $agentStatus } from "@shared/state/device";

let agent: AgentClient | null = null;

function agentClient(): AgentClient {
  agent ??= createAgentClient({
    tokenStore: {
      get: () => deviceSettings.get<string>(AGENT_TOKEN_KEY).then((t) => t ?? null),
      set: (t) => (t ? deviceSettings.set(AGENT_TOKEN_KEY, t) : deviceSettings.remove(AGENT_TOKEN_KEY)),
    },
  });
  return agent;
}

export type PrintOutcome = { ok: true } | { ok: false; code: string };

export async function printDoc(doc: ReceiptDoc): Promise<PrintOutcome> {
  try {
    const port = createPrinterPort(await loadPrinterSettings(deviceSettings), {
      agent: agentClient(),
      agentState: () => $agentStatus.getState(),
    });
    await port.printReceipt(doc);
    return { ok: true };
  } catch (e) {
    return { ok: false, code: e instanceof PrinterError ? e.code : "write_failed" };
  }
}

/**
 * Printing for the POS operation screens (Z-report on POS-07, return receipt on POS-05) through the
 * PrinterPort of 24 §6.1 (@shared/lib/printer): settings from erp-device, the Do'kon agenti client with its
 * token in erp-device, `$agentStatus` for the agent transport. Any PrinterError → the screen offers the
 * equipment settings (POS-16); nothing is lost — the document is in the outbox / on the server.
 */
import { createPrinterPort, loadPrinterSettings, PrinterError } from "@shared/lib/printer";
import type { ReceiptDoc } from "@shared/lib/receipt";
import { deviceSettings } from "@shared/offline";
import { $agentStatus } from "@shared/state/device";

import { posAgentClient, posCloudPrint } from "#/shared/lib/device-runtime.ts";

export type PrintOutcome = { ok: true } | { ok: false; code: string };

export async function printDoc(doc: ReceiptDoc): Promise<PrintOutcome> {
  try {
    const port = createPrinterPort(await loadPrinterSettings(deviceSettings), {
      agent: posAgentClient(),
      agentState: () => $agentStatus.getState(),
      cloud: posCloudPrint,
    });
    await port.printReceipt(doc);
    return { ok: true };
  } catch (e) {
    return { ok: false, code: e instanceof PrinterError ? e.code : "write_failed" };
  }
}

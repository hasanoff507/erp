import type { Tone } from "@shared/ui";

import type { CashRegister } from "../model/index.ts";

/** OFD registration status chip (20 #38 `ofd_status`). */
export function ofdTone(status: CashRegister["ofd_status"]): Tone {
  if (status === "active" || status === "registered") return "success";
  if (status === "pending") return "warning";
  return "destructive";
}

/** Fiscal module state chip (`fm_state` ≠ ok stops POS sales — 20 #38). */
export function fmTone(state: CashRegister["fm_state"]): Tone {
  if (state === "ok") return "success";
  if (state === "unknown") return "neutral";
  return "destructive";
}

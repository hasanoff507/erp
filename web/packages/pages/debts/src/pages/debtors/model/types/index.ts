import type { DebtorTab, Direction } from "#/entities/debtor/index.ts";

export type LoadStatus = "idle" | "loading" | "error";

export interface DebtorsMountParams {
  today: string;
  /** `?direction=payable` → «Men qarzdorman» (US-M08-11). */
  direction: Direction;
  tab: DebtorTab;
  /** `?counterparty=<id>` (Ctrl+K palette) — selected after the first load when it is among the rows. */
  counterparty?: string | null;
}

export interface AgingRequest {
  direction: Direction;
  branchId: string | null;
}

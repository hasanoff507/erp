/**
 * «Shubhali deb belgilash» / «Belgini olib tashlash» — Owner only (`debts.forgive`; 18 §12.6): a flag
 * without any posting (`POST /debt-doubtful-flags {counterparty_id, reason}`, `POST /{id}/unflag`).
 * The system never flags by itself — the 60+ list is only a reminder (US-M08-10, QT-M08-12).
 */
import { api } from "@shared/api";
import type { DoubtfulFlagOut } from "@shared/models";

import { apiFx } from "#/shared/lib/effect.ts";

export const flagDoubtfulFx = apiFx<{ counterpartyId: string; reason: string }, DoubtfulFlagOut>(
  ({ counterpartyId, reason }) =>
    api.debts.createDebtDoubtfulFlag({ counterparty_id: counterpartyId, reason: reason.trim() }),
);

export const unflagDoubtfulFx = apiFx<string, DoubtfulFlagOut>((flagId) =>
  api.debts.unflagDebtDoubtfulFlag(flagId),
);

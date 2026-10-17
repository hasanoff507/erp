/**
 * Local card terminal attempts — 16 §2.1 (qaror #71), 15 §9.3: written BEFORE the amount is sent to the
 * terminal, survive reloads, never auto-deleted while `pending`/`unknown`; an approved attempt leaves
 * this table in the same transaction its event enters the outbox (`enqueueEvent({removeCardAttemptIds})`).
 * PAN-free by construction: keys that could carry card data are refused and `card_mask` must be
 * `^[0-9]{4}\*+[0-9]{4}$` (`OfflineError("CARD_DATA_FORBIDDEN")`).
 */
import { OfflineError } from "../lib/errors.ts";
import { posDb } from "../runtime.ts";
import type { CardAttempt } from "../types.ts";

const FORBIDDEN_KEY =
  /^(pan|card_?number|full_?pan|track[0-9]?(_data)?|cvv[0-9]?|cvc[0-9]?|pin_?block|expiry|exp_date|emv.*|cryptogram|bin)$/i;
const CARD_MASK = /^[0-9]{4}\*+[0-9]{4}$/;
const UNRESOLVED = new Set(["pending", "unknown"]);

function assertPanFree(value: unknown, path: string): void {
  if (Array.isArray(value)) {
    value.forEach((v, i) => assertPanFree(v, `${path}[${i}]`));
    return;
  }
  if (typeof value !== "object" || value === null) return;
  for (const [key, inner] of Object.entries(value)) {
    if (FORBIDDEN_KEY.test(key)) throw new OfflineError("CARD_DATA_FORBIDDEN", { field: `${path}.${key}` });
    if (
      key === "card_mask" &&
      inner !== null &&
      inner !== undefined &&
      (typeof inner !== "string" || !CARD_MASK.test(inner))
    ) {
      throw new OfflineError("CARD_DATA_FORBIDDEN", { field: `${path}.${key}` });
    }
    assertPanFree(inner, `${path}.${key}`);
  }
}

/** Copy without any deny-listed card-data key (defence in depth for the export, SYNC-12). */
export function stripCardData<T>(value: T): T {
  if (Array.isArray(value)) return value.map((v: unknown) => stripCardData(v)) as T;
  if (typeof value !== "object" || value === null) return value;
  const out: Record<string, unknown> = {};
  for (const [key, inner] of Object.entries(value)) {
    if (FORBIDDEN_KEY.test(key)) continue;
    if (
      key === "card_mask" &&
      inner !== null &&
      inner !== undefined &&
      (typeof inner !== "string" || !CARD_MASK.test(inner))
    )
      continue;
    out[key] = stripCardData(inner);
  }
  return out as T;
}

export const cardAttempts = {
  async put(attempt: CardAttempt): Promise<void> {
    assertPanFree(attempt, "attempt");
    await posDb().card_attempts.put(attempt);
  },
  get(attemptId: string): Promise<CardAttempt | undefined> {
    return posDb().card_attempts.get(attemptId);
  },
  list(): Promise<CardAttempt[]> {
    return posDb().card_attempts.orderBy("attempt_id").toArray();
  },
  /** `pending` / `unknown` attempts (optionally of one terminal) — they block a new purchase there. */
  async unresolved(cardTerminalId?: string): Promise<CardAttempt[]> {
    const rows = cardTerminalId
      ? await posDb().card_attempts.where("card_terminal_id").equals(cardTerminalId).toArray()
      : await posDb().card_attempts.toArray();
    return rows.filter((r) => UNRESOLVED.has(r.status));
  },
  async update(attemptId: string, patch: Partial<CardAttempt>): Promise<CardAttempt> {
    assertPanFree(patch, "patch");
    const db = posDb();
    return db.transaction("rw", db.card_attempts, async () => {
      const current = await db.card_attempts.get(attemptId);
      if (!current)
        throw new OfflineError("VALIDATION_ERROR", { field: "attempt_id", attempt_id: attemptId });
      const next = { ...current, ...patch, attempt_id: attemptId };
      await db.card_attempts.put(next);
      return next;
    });
  },
  /**
   * Explicit removal (declined shown, voided/orphan sent to the server — 16 §2.1). `pending`/`unknown`
   * rows cannot be removed here: resolve them first (status query or manager resolution).
   */
  async remove(attemptId: string): Promise<void> {
    const db = posDb();
    await db.transaction("rw", db.card_attempts, async () => {
      const current = await db.card_attempts.get(attemptId);
      if (!current) return;
      if (UNRESOLVED.has(current.status))
        throw new OfflineError("CARD_OUTCOME_UNKNOWN", { attempt_id: attemptId });
      await db.card_attempts.delete(attemptId);
    });
  },
  count(): Promise<number> {
    return posDb().card_attempts.count();
  },
};

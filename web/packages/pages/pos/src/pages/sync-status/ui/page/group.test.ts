import { describe, expect, it } from "vitest";

import type { OutboxRow } from "@shared/offline";

import { groupOutbox } from "./Page.tsx";

const row = (id: string, status: OutboxRow["status"], retryable: boolean | null): OutboxRow =>
  ({ client_event_id: id, status, retryable }) as OutboxRow;

describe("POS-12 escalated documents (SYNC-02)", () => {
  it("non-retryable rejections go to «Eskalatsiya», the rest stay in the queue", () => {
    const g = groupOutbox([
      row("a", "pending", null),
      row("b", "rejected", false),
      row("c", "rejected", true),
    ]);
    expect(g.escalated.map((r) => r.client_event_id)).toEqual(["b"]);
    expect(g.queue.map((r) => r.client_event_id)).toEqual(["a", "c"]);
  });
});

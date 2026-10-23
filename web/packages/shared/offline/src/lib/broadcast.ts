/**
 * BroadcastChannel "erp-sync" (16 §11): tells the other tabs about outbox changes, push results, pull
 * results, revocation and wipes. A BroadcastChannel never delivers to its own sender: the local tab
 * reacts directly, listeners only see the OTHER tabs.
 */
import type { PullScope, PushResultEntry } from "../types.ts";

export const SYNC_CHANNEL = "erp-sync";

export type SyncMessage =
  | { type: "outbox-changed" }
  | { type: "event-results"; results: PushResultEntry[] }
  | { type: "pull-applied"; scopes: PullScope[] }
  | { type: "device-revoked" }
  | { type: "wiped"; scope: "pos" | "all" };

type Listener = (message: SyncMessage) => void;

const listeners = new Set<Listener>();
let channel: BroadcastChannel | null = null;

function ensureChannel(): BroadcastChannel | null {
  if (channel || typeof BroadcastChannel === "undefined") return channel;
  channel = new BroadcastChannel(SYNC_CHANNEL);
  channel.onmessage = (event: MessageEvent<SyncMessage>) => {
    for (const listener of listeners) listener(event.data);
  };
  return channel;
}

export function broadcast(message: SyncMessage): void {
  ensureChannel()?.postMessage(message);
}

export function onSyncMessage(listener: Listener): () => void {
  ensureChannel();
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Tests / teardown: close the channel so Node can exit. */
export function closeSyncChannel(): void {
  channel?.close();
  channel = null;
  listeners.clear();
}

/**
 * In-tab memory copies of the searchable tables (catalog, customers) — QT-NFR-01: typed search must
 * stay instant on 10k+ products, and IndexedDB multiEntry prefix cursors are too slow for "every word
 * must match" queries. The copy is rebuilt lazily after a pull touched the table (this tab or another
 * tab via BroadcastChannel) and whenever the database instance changes (logout, tests).
 */
import type { Table } from "dexie";

import { posDb } from "../runtime.ts";

interface Entry {
  db: unknown;
  version: number;
  rows: Promise<unknown[]>;
}

const entries = new Map<string, Entry>();
const versions = new Map<string, number>();

export function invalidateMemoryIndex(table: string): void {
  versions.set(table, (versions.get(table) ?? 0) + 1);
}

export function memoryRows<T>(table: string, load: (t: Table<T>) => Promise<T[]>): Promise<T[]> {
  const db = posDb();
  const version = versions.get(table) ?? 0;
  const cached = entries.get(table);
  if (cached && cached.db === db && cached.version === version) return cached.rows as Promise<T[]>;
  const rows = load(db.table<T>(table));
  entries.set(table, { db, version, rows });
  rows.catch(() => entries.delete(table));
  return rows;
}

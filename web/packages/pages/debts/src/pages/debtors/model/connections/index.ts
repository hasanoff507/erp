/** BO-06 wiring — sample() only (24 §2). */
import { combine, sample } from "effector";

import type { DebtorTab } from "#/entities/debtor/index.ts";

import { submitBankPaymentFx } from "#/features/bank-payment/index.ts";
import { saveCardFx } from "#/features/customer-card/index.ts";
import { ledgerReloadRequested } from "#/features/debt-ledger/index.ts";
import { submitOpeningFx } from "#/features/debt-opening/index.ts";
import { submitWriteoffFx } from "#/features/debt-writeoff/index.ts";
import { flagDoubtfulFx, unflagDoubtfulFx } from "#/features/doubtful-flag/index.ts";

import { loadAgingFx } from "../effects/index.ts";
import {
  directionChanged,
  pageChanged,
  pageMounted,
  reloadRequested,
  rowSelected,
  searchChanged,
  tabChanged,
} from "../events/index.ts";
import { filterRows, pageOf, tabCounts, totalOf } from "../lib/index.ts";
import {
  $asOf,
  $branchId,
  $direction,
  $error,
  $mounted,
  $page,
  $pendingCounterparty,
  $rows,
  $search,
  $selectedId,
  $status,
  $summary,
  $tab,
  $today,
  $version,
} from "../stores/index.ts";

export const $visible = combine($rows, $tab, $search, $today, (rows, tab, search, today) =>
  filterRows(rows, tab, search, today),
);
export const $counts = combine($rows, $today, (rows, today) => tabCounts(rows, today));
export const $pageRows = combine($visible, $page, (rows, page) => pageOf(rows, page));
export const $visibleTotal = $visible.map(totalOf);
export const $selected = combine(
  $rows,
  $selectedId,
  (rows, id) => rows.find((r) => r.counterparty_id === id) ?? null,
);
export const $names = $rows.map((rows) => Object.fromEntries(rows.map((r) => [r.counterparty_id, r.name])));

$mounted.on(pageMounted, () => true);
$today.on(pageMounted, (_, p) => p.today);
$direction.on(pageMounted, (_, p) => p.direction).on(directionChanged, (_, d) => d);
$tab.on(pageMounted, (_, p) => p.tab).on(tabChanged, (_, tab) => tab);
$search.on(searchChanged, (_, s) => s.slice(0, 64));
$page
  .on(pageChanged, (_, p) => Math.max(1, p))
  .reset(tabChanged, searchChanged, directionChanged, pageMounted);
$selectedId.on(rowSelected, (_, id) => id).reset(directionChanged, pageMounted);

const writeDone = [
  submitBankPaymentFx.done,
  submitOpeningFx.done,
  submitWriteoffFx.done,
  flagDoubtfulFx.done,
  unflagDoubtfulFx.done,
  saveCardFx.done,
];

sample({
  clock: [
    pageMounted,
    directionChanged,
    reloadRequested,
    sample({ clock: $branchId.updates, source: $mounted, filter: (m) => m }),
    ...writeDone,
  ],
  source: { direction: $direction, branchId: $branchId, mounted: $mounted },
  filter: ({ mounted }) => mounted,
  fn: ({ direction, branchId }) => ({ direction, branchId }),
  target: loadAgingFx,
});
// an open ledger shows the write too
sample({ clock: writeDone, target: ledgerReloadRequested });

/** An answer for another direction / branch is dropped. */
const loaded = sample({
  clock: loadAgingFx.done,
  source: { direction: $direction, branchId: $branchId },
  filter: (current, { params }) =>
    current.direction === params.direction && current.branchId === params.branchId,
  fn: (_, { result }) => result,
});
$rows.on(loaded, (_, r) => r.rows).reset(directionChanged);
$summary.on(loaded, (_, r) => r.summary).reset(directionChanged);
$asOf.on(loaded, (_, r) => r.as_of);
$version.on(loaded, (n) => n + 1);
$status
  .on(loadAgingFx, () => "loading")
  .on(loaded, () => "idle")
  .on(loadAgingFx.fail, () => "error");
$error.on(loadAgingFx.failData, (_, e) => e).reset(loadAgingFx);
// a selected customer whose debt was closed leaves the list → the panel closes
$selectedId.on(loaded, (id, r) => (id && r.rows.some((x) => x.counterparty_id === id) ? id : null));

// WEB-06: `?counterparty=<id>` (Ctrl+K) → after the first load, «Barchasi» + that row; unknown ids are ignored
$pendingCounterparty.on(pageMounted, (_, p) => p.counterparty ?? null).reset(directionChanged);
const firstLoad = sample({
  clock: loaded,
  source: $pendingCounterparty,
  filter: (id) => id !== null,
  fn: (id, r) => ({ id: id ?? "", known: r.rows.some((x) => x.counterparty_id === id) }),
});
$pendingCounterparty.reset(firstLoad);
const deepLinked = sample({ clock: firstLoad, filter: ({ known }) => known, fn: ({ id }) => id });
sample({ clock: deepLinked, fn: (): DebtorTab => "all", target: tabChanged });
sample({ clock: deepLinked, target: rowSelected });

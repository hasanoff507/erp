/** BO-15 wiring — sample() only (24 §2). */
import { combine, createStore, sample, type Effect, type Event, type StoreWritable } from "effector";

import type { ApiError } from "@shared/api";

import {
  cancelOutFx,
  createOutFx,
  ettnRespondFx,
  fromReceiptFx,
  getDetailFx,
  listEttnFx,
  listInboundFx,
  listOutboundFx,
  listPoaFx,
  loadKeysFx,
  loadKpiFx,
  loadWarehousesFx,
  poaCancelFx,
  poaSignFx,
  rejectFx,
  searchCompaniesFx,
  searchSalesFx,
  setRiskFx,
  signAcceptFx,
  signSendFx,
} from "../effects/index.ts";
import {
  actionErrorDismissed,
  cancelOutSubmitted,
  companiesSearched,
  createOutSubmitted,
  dialogOpened,
  einvoiceSelected,
  ettnRespondRequested,
  fromReceiptSubmitted,
  keyChosen,
  moreRequested,
  noticeDismissed,
  pageMounted,
  poaCancelSubmitted,
  poaSignRequested,
  receiptDialogOpened,
  rejectSubmitted,
  reloadRequested,
  riskFilterChanged,
  riskFlagSubmitted,
  salesSearched,
  signAcceptRequested,
  signSendRequested,
  statusFilterChanged,
  tabChanged,
} from "../events/index.ts";
import { computeKpis } from "../lib/index.ts";
import {
  $actionError,
  $canOutbound,
  $companies,
  $detail,
  $detailStatus,
  $dialog,
  $ettnCursor,
  $ettnError,
  $ettnStatus,
  $ettns,
  $inFilters,
  $inbound,
  $inboundCursor,
  $inboundError,
  $inboundStatus,
  $keyId,
  $keys,
  $keysError,
  $kpis,
  $notice,
  $outbound,
  $outboundCursor,
  $outboundError,
  $outboundStatus,
  $poaCursor,
  $poaError,
  $poaStatus,
  $poas,
  $sales,
  $selectedId,
  $tab,
  $today,
  $warehouses,
} from "../stores/index.ts";
import type {
  EimzoKey,
  EInvoice,
  EInvoiceDetail,
  InFilters,
  ListRequest,
  LoadStatus,
  Notice,
  Tab,
} from "../types/index.ts";

interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

/** One cursor list: reload → first page; more → next page; answers for other filters are dropped. */
function wireList<T, F>(cfg: {
  tab: Tab;
  fx: Effect<ListRequest<F>, Page<T>, ApiError>;
  filters: StoreWritable<F>;
  items: StoreWritable<T[]>;
  cursor: StoreWritable<string | null>;
  status: StoreWritable<LoadStatus>;
  error: StoreWritable<ApiError | null>;
  reload: Event<unknown>;
}) {
  sample({
    clock: cfg.reload,
    source: cfg.filters,
    fn: (filters): ListRequest<F> => ({ filters, cursor: null }),
    target: cfg.fx,
  });
  sample({
    clock: moreRequested,
    source: { filters: cfg.filters, cursor: cfg.cursor, pending: cfg.fx.pending },
    filter: ({ cursor, pending }, tab) => tab === cfg.tab && cursor !== null && !pending,
    fn: ({ filters, cursor }): ListRequest<F> => ({ filters, cursor }),
    target: cfg.fx,
  });
  const loaded = sample({
    clock: cfg.fx.done,
    source: cfg.filters,
    filter: (filters, { params }) => JSON.stringify(filters) === JSON.stringify(params.filters),
    fn: (_, payload) => payload,
  });
  cfg.items.on(loaded, (list, { params, result }) =>
    params.cursor === null ? result.items : [...list, ...result.items],
  );
  cfg.cursor.on(loaded, (_, { result }) => result.next_cursor);
  cfg.status
    .on(cfg.fx, (s, p) => (p.cursor === null ? "loading" : s))
    .on(loaded, () => "idle")
    .on(cfg.fx.fail, (s, { params }) => (params.cursor === null ? "error" : s));
  cfg.error.on(cfg.fx.failData, (_, e) => e).reset(cfg.fx);
}

/** Lists without filters share one constant filter store. */
const $noFilters = createStore<null>(null, { skipVoid: false });

// --- mount / tabs ----------------------------------------------------------------------------------------
$today.on(pageMounted, (_, { today }) => today);
$canOutbound.on(pageMounted, (_, { canOutbound }) => canOutbound);
$tab.on(tabChanged, (_, tab) => tab);
$inFilters
  .on(riskFilterChanged, (f, risk) => ({ ...f, risk }))
  .on(statusFilterChanged, (f, status) => ({ ...f, status }));

const reloadIn = sample({
  clock: [pageMounted, $inFilters.updates, sample({ clock: reloadRequested, filter: (t) => t === "in" })],
  fn: () => null,
});
const reloadOut = sample({
  clock: [
    sample({ clock: pageMounted, filter: ({ canOutbound }) => canOutbound }),
    sample({ clock: reloadRequested, filter: (t) => t === "out" }),
  ],
  fn: () => null,
});
const reloadEttn = sample({
  clock: [pageMounted, sample({ clock: reloadRequested, filter: (t) => t === "ettn" })],
  fn: () => null,
});
const reloadPoa = sample({
  clock: [pageMounted, sample({ clock: reloadRequested, filter: (t) => t === "poa" })],
  fn: () => null,
});

wireList<EInvoice, InFilters>({
  tab: "in", fx: listInboundFx, filters: $inFilters, items: $inbound, cursor: $inboundCursor,
  status: $inboundStatus, error: $inboundError, reload: reloadIn,
}); // prettier-ignore
wireList({
  tab: "out", fx: listOutboundFx, filters: $noFilters, items: $outbound,
  cursor: $outboundCursor, status: $outboundStatus, error: $outboundError, reload: reloadOut,
}); // prettier-ignore
wireList({
  tab: "ettn", fx: listEttnFx, filters: $noFilters, items: $ettns,
  cursor: $ettnCursor, status: $ettnStatus, error: $ettnError, reload: reloadEttn,
}); // prettier-ignore
wireList({
  tab: "poa", fx: listPoaFx, filters: $noFilters, items: $poas,
  cursor: $poaCursor, status: $poaStatus, error: $poaError, reload: reloadPoa,
}); // prettier-ignore

// --- dialogs: closed by a successful create --------------------------------------------------------------
$dialog.on(dialogOpened, (_, d) => d).reset([fromReceiptFx.done, createOutFx.done]);
$actionError.reset(dialogOpened);

sample({ clock: receiptDialogOpened, target: loadWarehousesFx });
$warehouses.on(loadWarehousesFx.doneData, (_, items) => items);

// --- KPI cards + E-IMZO keys --------------------------------------------------------------------------
const kpiRefresh = sample({
  clock: [pageMounted, reloadIn, reloadOut],
  source: $canOutbound,
  fn: (outbound) => ({ outbound }),
});
sample({ clock: kpiRefresh, target: loadKpiFx });
$kpis.on(
  sample({ clock: loadKpiFx.doneData, source: $today, fn: (today, r) => ({ today, r }) }),
  (_, { today, r }) => computeKpis(r.inbound.items, r.outbound.items, today.slice(0, 7)),
);

sample({ clock: pageMounted, target: loadKeysFx });
$keys.on(loadKeysFx.doneData, (_, keys) => keys);
$keysError.on(loadKeysFx.failData, (_, e) => e).reset(loadKeysFx.done);
$keyId
  .on(loadKeysFx.doneData, (current, keys) => current ?? keys[0]?.id ?? null)
  .on(keyChosen, (_, id) => id);
const $key = combine($keys, $keyId, (keys, id) => keys.find((k) => k.id === id) ?? null);

// --- detail panel -------------------------------------------------------------------------------------
$selectedId.on(einvoiceSelected, (_, id) => id).reset(tabChanged);
sample({ clock: einvoiceSelected, filter: (id): id is string => id !== null, target: getDetailFx });
$detail
  .on(
    sample({
      clock: getDetailFx.done,
      source: $selectedId,
      filter: (id, { params }) => id === params,
      fn: (_, { result }) => result,
    }),
    (_, d) => d,
  )
  .reset(einvoiceSelected);
$detailStatus
  .on(getDetailFx, () => "loading")
  .on(getDetailFx.done, () => "idle")
  .on(getDetailFx.fail, () => "error");

// --- actions ------------------------------------------------------------------------------------------
const $detailRef = combine($detail, $key, (detail, key) => ({ detail, key }));
type Ready = { detail: EInvoiceDetail; key: EimzoKey };
const isReady = (r: { detail: EInvoiceDetail | null; key: EimzoKey | null }): r is Ready =>
  r.detail !== null && r.key !== null;
const withSigned = ({ detail, key }: Ready) => ({ id: detail.id, key, signed: detail.status === "signed" });

sample({
  clock: riskFlagSubmitted,
  source: $selectedId,
  filter: (id): id is string => id !== null,
  fn: (id, { flag, note }) => ({ id: id ?? "", flag, note }),
  target: setRiskFx,
});
sample({
  clock: signAcceptRequested,
  source: $detailRef,
  filter: isReady,
  fn: withSigned,
  target: signAcceptFx,
});
sample({
  clock: rejectSubmitted,
  source: $selectedId,
  filter: (id): id is string => id !== null,
  fn: (id, reason) => ({ id: id ?? "", reason }),
  target: rejectFx,
});
sample({
  clock: signSendRequested,
  source: $detailRef,
  filter: isReady,
  fn: withSigned,
  target: signSendFx,
});
sample({
  clock: cancelOutSubmitted,
  source: $selectedId,
  filter: (id): id is string => id !== null,
  fn: (id, reason) => ({ id: id ?? "", reason }),
  target: cancelOutFx,
});
sample({ clock: fromReceiptSubmitted, target: fromReceiptFx });
sample({ clock: createOutSubmitted, target: createOutFx });
sample({
  clock: salesSearched,
  filter: (q) => q.trim().length > 0,
  fn: (q) => q.trim(),
  target: searchSalesFx,
});
sample({
  clock: companiesSearched,
  filter: (q) => q.trim().length > 0,
  fn: (q) => q.trim(),
  target: searchCompaniesFx,
});
$sales.on(searchSalesFx.doneData, (_, items) => items);
$companies.on(searchCompaniesFx.doneData, (_, items) => items);
sample({
  clock: ettnRespondRequested,
  source: $key,
  filter: (key: EimzoKey | null): key is EimzoKey => key !== null,
  fn: (key, req) => ({ ...req, key }),
  target: ettnRespondFx,
});
sample({
  clock: poaSignRequested,
  source: $key,
  filter: (key: EimzoKey | null): key is EimzoKey => key !== null,
  fn: (key, id) => ({ id, key }),
  target: poaSignFx,
});
sample({ clock: poaCancelSubmitted, target: poaCancelFx });

// results → notice + reload of the affected list (and the open detail)
const ACTIONS = [
  { fx: setRiskFx, kind: "risk", key: "notices.risk", tab: "in" },
  { fx: signAcceptFx, kind: "signAccept", key: "notices.accepted", tab: "in" },
  { fx: rejectFx, kind: "reject", key: "notices.rejected", tab: "in" },
  { fx: signSendFx, kind: "signSend", key: "notices.sent", tab: "out" },
  { fx: cancelOutFx, kind: "cancelOut", key: "notices.cancelled", tab: "out" },
  { fx: fromReceiptFx, kind: "fromReceipt", key: "notices.created", tab: "out" },
  { fx: createOutFx, kind: "createOut", key: "notices.created", tab: "out" },
  { fx: ettnRespondFx, kind: "ettnAccept", key: "notices.ettnQueued", tab: "ettn" },
  { fx: poaSignFx, kind: "poaSign", key: "notices.poaSent", tab: "poa" },
  { fx: poaCancelFx, kind: "poaCancel", key: "notices.poaCancelled", tab: "poa" },
] as const;

for (const action of ACTIONS) {
  const fx = action.fx as unknown as Effect<unknown, unknown, ApiError>;
  $notice.on(fx.done, (): Notice => ({ kind: action.kind, key: action.key }));
  sample({ clock: fx.done, fn: () => action.tab, target: reloadRequested });
  $actionError.on(fx.failData, (_, e) => e).reset(fx);
}
$notice.reset([noticeDismissed, actionErrorDismissed]);
$actionError.reset([actionErrorDismissed, einvoiceSelected, tabChanged]);
// the open e-invoice is re-read after an action on it
sample({
  clock: [setRiskFx.done, signAcceptFx.done, rejectFx.done, signSendFx.done, cancelOutFx.done],
  source: $selectedId,
  filter: (id): id is string => id !== null,
  target: getDetailFx,
});
// a new outgoing e-invoice opens in the panel
sample({
  clock: [fromReceiptFx.doneData, createOutFx.doneData],
  fn: () => "out" as const,
  target: tabChanged,
});
sample({
  clock: [fromReceiptFx.doneData, createOutFx.doneData],
  fn: (d) => d.id,
  target: einvoiceSelected,
});

export const $busy = combine(
  [setRiskFx.pending, signAcceptFx.pending, rejectFx.pending, signSendFx.pending, cancelOutFx.pending,
    fromReceiptFx.pending, createOutFx.pending, ettnRespondFx.pending, poaSignFx.pending, poaCancelFx.pending],
  (flags) => flags.some(Boolean),
); // prettier-ignore
export const $key$ = $key;
export const $tabCounts = combine($inbound, $outbound, $ettns, $poas, (a, b, c, d) => ({
  in: a.length,
  out: b.length,
  ettn: c.length,
  poa: d.length,
}));
export const $hasMore = combine(
  $inboundCursor,
  $outboundCursor,
  $ettnCursor,
  $poaCursor,
  (inC, outC, ettnC, poaC): Record<Tab, boolean> => ({
    in: inC !== null,
    out: outC !== null,
    ettn: ettnC !== null,
    poa: poaC !== null,
  }),
);

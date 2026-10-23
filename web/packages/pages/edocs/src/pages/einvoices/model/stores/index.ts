import { createStore } from "effector";

import type { ApiError } from "@shared/api";

import type {
  Counterparty,
  EimzoKey,
  EInvoice,
  EInvoiceDetail,
  Ettn,
  InFilters,
  Kpis,
  LoadStatus,
  Notice,
  Poa,
  Sale,
  Tab,
  Warehouse,
} from "../types/index.ts";

export const $today = createStore("1970-01-01");
export const $canOutbound = createStore(false);
export const $tab = createStore<Tab>("in");
export const $inFilters = createStore<InFilters>({ risk: "all", status: "all" });

export const $inbound = createStore<EInvoice[]>([]);
export const $inboundCursor = createStore<string | null>(null, { skipVoid: false });
export const $inboundStatus = createStore<LoadStatus>("idle");
export const $inboundError = createStore<ApiError | null>(null, { skipVoid: false });

export const $outbound = createStore<EInvoice[]>([]);
export const $outboundCursor = createStore<string | null>(null, { skipVoid: false });
export const $outboundStatus = createStore<LoadStatus>("idle");
export const $outboundError = createStore<ApiError | null>(null, { skipVoid: false });

export const $ettns = createStore<Ettn[]>([]);
export const $ettnCursor = createStore<string | null>(null, { skipVoid: false });
export const $ettnStatus = createStore<LoadStatus>("idle");
export const $ettnError = createStore<ApiError | null>(null, { skipVoid: false });

export const $poas = createStore<Poa[]>([]);
export const $poaCursor = createStore<string | null>(null, { skipVoid: false });
export const $poaStatus = createStore<LoadStatus>("idle");
export const $poaError = createStore<ApiError | null>(null, { skipVoid: false });

export const $kpis = createStore<Kpis | null>(null, { skipVoid: false });

export const $selectedId = createStore<string | null>(null, { skipVoid: false });
export const $detail = createStore<EInvoiceDetail | null>(null, { skipVoid: false });
export const $detailStatus = createStore<LoadStatus>("idle");

export const $keys = createStore<EimzoKey[]>([]);
export const $keysError = createStore<ApiError | null>(null, { skipVoid: false });
export const $keyId = createStore<string | null>(null, { skipVoid: false });

export const $sales = createStore<Sale[]>([]);
export const $companies = createStore<Counterparty[]>([]);

export const $notice = createStore<Notice | null>(null, { skipVoid: false });
export const $actionError = createStore<ApiError | null>(null, { skipVoid: false });
export const $dialog = createStore<"fromReceipt" | "createOut" | null>(null, { skipVoid: false });
export const $warehouses = createStore<Warehouse[]>([]);

/**
 * BO-15 effects — generated `api.purchasing.*` (19 §19 incoming, §8a powers of attorney), `api.sales.*`
 * (18 §14a outgoing), `api.transfers.*` (19 §20 e-TTN) and the E-IMZO signer (`@shared/lib/eimzo`, 21 §5).
 * Signing is always challenge → sign the `document_hash` → submit; the key never leaves the browser.
 */
import { api } from "@shared/api";
import { getEimzoSigner, signDocument, type EimzoKey } from "@shared/lib/eimzo";

import { apiFx, todayIso } from "#/shared/lib/effect.ts";

import { inboundParams } from "../lib/index.ts";
import {
  KPI_LIMIT,
  PAGE_LIMIT,
  type Counterparty,
  type EInvoiceCreate,
  type EInvoiceDetail,
  type EInvoicePage,
  type EttnPage,
  type InFilters,
  type ListRequest,
  type PoaPage,
  type Product,
  type Sale,
  type Warehouse,
} from "../types/index.ts";

export const listInboundFx = apiFx<ListRequest<InFilters>, EInvoicePage>((req) =>
  api.purchasing.listEinvoices(inboundParams(req)),
);
export const listOutboundFx = apiFx<ListRequest, EInvoicePage>((req) =>
  api.purchasing.listEinvoices({
    direction: "out",
    ...(req.cursor ? { cursor: req.cursor } : {}),
    limit: PAGE_LIMIT,
  }),
);
/** «Kiruvchi e-TTN» (07 BO-15): `GET /ettn-documents?direction=in`. */
export const listEttnFx = apiFx<ListRequest, EttnPage>((req) =>
  api.transfers.listEttnDocuments({
    direction: "in",
    ...(req.cursor ? { cursor: req.cursor } : {}),
    limit: PAGE_LIMIT,
  }),
);
export const listPoaFx = apiFx<ListRequest, PoaPage>((req) =>
  api.purchasing.listPowersOfAttorney({ ...(req.cursor ? { cursor: req.cursor } : {}), limit: PAGE_LIMIT }),
);
/** KPI cards: one unfiltered page of each direction (outgoing only when the user may read it). */
export const loadKpiFx = apiFx<{ outbound: boolean }, { inbound: EInvoicePage; outbound: EInvoicePage }>(
  async ({ outbound }) => {
    const [inbound, out] = await Promise.all([
      api.purchasing.listEinvoices({ direction: "in", limit: KPI_LIMIT }),
      outbound
        ? api.purchasing.listEinvoices({ direction: "out", limit: KPI_LIMIT })
        : Promise.resolve({ items: [], next_cursor: null }),
    ]);
    return { inbound, outbound: out };
  },
);
export const getDetailFx = apiFx<string, EInvoiceDetail>((id) => api.purchasing.getEinvoice(id));
export const loadKeysFx = apiFx<void, EimzoKey[]>(() => getEimzoSigner().listKeys());

// --- incoming (19 §19) --------------------------------------------------------------------------------
export const setRiskFx = apiFx<{ id: string; flag: "green" | "red"; note: string }, unknown>(
  ({ id, flag, note }) => api.purchasing.setEinvoiceRiskFlag(id, { risk_flag: flag, note }),
);
/** «Imzolab qabul qilish»: sign (unless already `signed`) → `accept` (202, operator via outbox). */
export const signAcceptFx = apiFx<{ id: string; key: EimzoKey; signed: boolean }, unknown>(
  async ({ id, key, signed }) => {
    if (!signed) {
      await signDocument(
        getEimzoSigner(),
        key,
        {
          challenge: () => api.purchasing.einvoiceSignChallenge(id, null),
          submit: (body) => api.purchasing.einvoiceSubmitSigned(id, body),
        },
        todayIso(),
      );
    }
    return api.purchasing.acceptEinvoice(id, null);
  },
);
export const rejectFx = apiFx<{ id: string; reason: string }, unknown>(({ id, reason }) =>
  api.purchasing.rejectEinvoice(id, { reason }),
);

// --- outgoing (18 §14a) -------------------------------------------------------------------------------
/** «E-IMZO imzo» (07 BO-15): sign (unless already `signed`) → `send` (202). */
export const signSendFx = apiFx<{ id: string; key: EimzoKey; signed: boolean }, unknown>(
  async ({ id, key, signed }) => {
    if (!signed) {
      await signDocument(
        getEimzoSigner(),
        key,
        {
          challenge: () => api.purchasing.einvoiceSignChallenge(id, null),
          submit: (body) => api.purchasing.einvoiceSubmitSigned(id, body),
        },
        todayIso(),
      );
    }
    return api.sales.sendEinvoice(id, null);
  },
);
export const cancelOutFx = apiFx<{ id: string; reason: string }, unknown>(({ id, reason }) =>
  api.sales.cancelEinvoice(id, { reason }),
);
export const fromReceiptFx = apiFx<{ saleId: string; counterpartyId: string }, EInvoiceDetail>(
  ({ saleId, counterpartyId }) =>
    api.sales.createEinvoiceFromReceipt({ sale_id: saleId, counterparty_id: counterpartyId }),
);
export const createOutFx = apiFx<EInvoiceCreate, EInvoiceDetail>((body) => api.sales.createEinvoice(body));
export const searchSalesFx = apiFx<string, Sale[]>(async (number) => {
  const page = await api.sales.listSales({ number, status: "posted", limit: 10 });
  return page.items;
});
export const searchCompaniesFx = apiFx<string, Counterparty[]>(async (search) => {
  const page = await api.debts.listCounterparties({ search, kind: "company", size: 10 });
  return page.items;
});

// --- incoming e-TTN (19 §20) --------------------------------------------------------------------------
export const ettnRespondFx = apiFx<
  { id: string; key: EimzoKey; action: "accept" | "reject"; reason: string | null },
  unknown
>(({ id, key, action, reason }) =>
  signDocument(
    getEimzoSigner(),
    key,
    {
      challenge: () => api.transfers.ettnSignChallenge(id, null, { action }),
      submit: (body) =>
        action === "accept"
          ? api.transfers.acceptEttn(id, body)
          : api.transfers.rejectEttn(id, { ...body, reason: reason ?? "" }),
    },
    todayIso(),
  ),
);

// --- powers of attorney (19 §8a) ----------------------------------------------------------------------
export const poaSignFx = apiFx<{ id: string; key: EimzoKey }, unknown>(({ id, key }) =>
  signDocument(
    getEimzoSigner(),
    key,
    {
      challenge: () => api.purchasing.poaSignChallenge(id, null),
      submit: (body) => api.purchasing.poaSubmitSigned(id, body),
    },
    todayIso(),
  ),
);
export const poaCancelFx = apiFx<{ id: string; reason: string }, unknown>(({ id, reason }) =>
  api.purchasing.cancelPowerOfAttorney(id, { reason }),
);

// --- «Kirim yaratish» from an accepted incoming e-invoice (19 §8 from-einvoice, ACC-07) ----------------
export const loadWarehousesFx = apiFx<void, Warehouse[]>(
  async () => (await api.branches.warehousesList()).items,
);
export const searchProductsFx = apiFx<string, Product[]>(async (search) => {
  const page = await api.pricing.listProducts({ search, size: 10 });
  return page.items;
});
export const receiptFromEinvoiceFx = apiFx<
  { einvoiceId: string; warehouseId: string; lines: { line_no: number; product_id: string }[] },
  { id: string }
>(({ einvoiceId, warehouseId, lines }) =>
  api.purchasing.createGoodsReceiptFromEinvoice(einvoiceId, { warehouse_id: warehouseId, lines }),
);

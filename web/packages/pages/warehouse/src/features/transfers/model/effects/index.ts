/**
 * Ko'chirishlar effects — generated `api.transfers.*` (19 §13). Writes carry Idempotency-Key + CSRF
 * from the API layer (17 §6).
 */
import { api, toApiError } from "@shared/api";

import { createProductSearch } from "#/entities/product/index.tsx";
import { apiFx } from "#/shared/lib/effect.ts";

import { toQuery } from "../lib/index.ts";
import type {
  CancelParams,
  CreateTransferParams,
  CreateTransferResult,
  ListRequest,
  ReceiveParams,
  Transfer,
  TransferPage,
} from "../types/index.ts";

export const listTransfersFx = apiFx<ListRequest, TransferPage>((req) =>
  api.transfers.listTransfers(toQuery(req)),
);

export const getTransferFx = apiFx<string, Transfer>((id) => api.transfers.getTransfer(id));

/**
 * «Ko'chirish» sheet: `POST /transfers` (draft) and, for «O'tkazish», `POST /transfers/{id}/post`.
 * A refused post keeps the created draft (returned with `postError`) — it is in the list to retry.
 */
export const createTransferFx = apiFx<CreateTransferParams, CreateTransferResult>(async ({ body, post }) => {
  const draft = await api.transfers.createTransfer(body);
  if (!post) return { transfer: draft, postError: null };
  try {
    return { transfer: await api.transfers.postTransfer(draft.id, {}), postError: null };
  } catch (e) {
    return { transfer: draft, postError: toApiError(e) };
  }
});

/** Balance of a product in the source warehouse (POS-09 «manbada qoldiq», overselling only warns). */
export const loadAvailableFx = apiFx<
  { warehouseId: string; productId: string },
  { productId: string; qty: string }
>(async ({ warehouseId, productId }) => {
  const page = await api.inventory.listStockBalances({
    warehouse_id: warehouseId,
    product_id: productId,
    limit: 1,
  });
  return { productId, qty: page.items[0]?.qty ?? "0.000" };
});

/** Product search of the «Ko'chirish» sheet. */
export const transferProductSearch = createProductSearch();

export const postTransferFx = apiFx<string, Transfer>((id) => api.transfers.postTransfer(id, {}));
export const sendTransferFx = apiFx<string, Transfer>((id) => api.transfers.sendTransfer(id, {}));
export const receiveTransferFx = apiFx<ReceiveParams, Transfer>(({ id, lines }) =>
  api.transfers.receiveTransfer(id, { lines }),
);
export const cancelTransferFx = apiFx<CancelParams, Transfer>(({ id, reason }) =>
  api.transfers.cancelTransfer(id, { reason }),
);

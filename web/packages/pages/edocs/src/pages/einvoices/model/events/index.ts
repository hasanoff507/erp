import { createEvent } from "effector";

import type { EInvoiceCreate, InStatusFilter, MountParams, RiskFilter, Tab } from "../types/index.ts";

export const pageMounted = createEvent<MountParams & { canOutbound: boolean }>();
export const tabChanged = createEvent<Tab>();
export const riskFilterChanged = createEvent<RiskFilter>();
export const statusFilterChanged = createEvent<InStatusFilter>();
export const moreRequested = createEvent<Tab>();
export const reloadRequested = createEvent<Tab>();

/** Row click (incoming / outgoing) → the detail panel; `null` closes it. */
export const einvoiceSelected = createEvent<string | null>();
export const keyChosen = createEvent<string>();

export const riskFlagSubmitted = createEvent<{ flag: "green" | "red"; note: string }>();
export const signAcceptRequested = createEvent();
export const rejectSubmitted = createEvent<string>();
export const signSendRequested = createEvent();
export const cancelOutSubmitted = createEvent<string>();

export const fromReceiptSubmitted = createEvent<{ saleId: string; counterpartyId: string }>();
export const createOutSubmitted = createEvent<EInvoiceCreate>();
export const salesSearched = createEvent<string>();
export const companiesSearched = createEvent<string>();

export const ettnRespondRequested = createEvent<{
  id: string;
  action: "accept" | "reject";
  reason: string | null;
}>();
export const poaSignRequested = createEvent<string>();
export const poaCancelSubmitted = createEvent<{ id: string; reason: string }>();

export const noticeDismissed = createEvent();
export const actionErrorDismissed = createEvent();

/** «Chek asosida e-faktura» / «Chiquvchi e-faktura» dialogs; `null` closes. */
export const dialogOpened = createEvent<"fromReceipt" | "createOut" | null>();

/** «Kirim yaratish» opened → the warehouses are (re)loaded. */
export const receiptDialogOpened = createEvent();

import type { EimzoKey } from "@shared/lib/eimzo";
import type {
  AppModulesIntegrationsEinvoiceApiEttnDocumentsEttnOut,
  CounterpartyListItem,
  EInvoiceCreate,
  EInvoiceDetail,
  EInvoiceOut,
  EInvoicePage,
  EttnPage,
  OutLineIn,
  PoaOut,
  PoaPage,
  ProductListItem,
  SaleListItem,
  WarehouseOut,
} from "@shared/models";

export type EInvoice = EInvoiceOut;
export type Ettn = AppModulesIntegrationsEinvoiceApiEttnDocumentsEttnOut;
export type Poa = PoaOut;
export type Sale = SaleListItem;
export type Counterparty = CounterpartyListItem;
export type Warehouse = WarehouseOut;
export type Product = ProductListItem;
export type { EInvoiceCreate, EInvoiceDetail, EInvoicePage, EimzoKey, EttnPage, OutLineIn, PoaPage };

/** 07 BO-15 tabs: Kiruvchi · Chiquvchi · E-TTN · E-ishonchnomalar. */
export const TABS = ["in", "out", "ettn", "poa"] as const;
export type Tab = (typeof TABS)[number];

export const RISK_FILTERS = ["all", "green", "red", "unknown"] as const;
export type RiskFilter = (typeof RISK_FILTERS)[number];
/** 07 BO-15 status filter: Barchasi / Imzo kutmoqda (received) / Qabul qilingan / Rad etilgan. */
export const IN_STATUS_FILTERS = ["all", "received", "accepted", "rejected"] as const;
export type InStatusFilter = (typeof IN_STATUS_FILTERS)[number];

export interface InFilters {
  risk: RiskFilter;
  status: InStatusFilter;
}

export type LoadStatus = "idle" | "loading" | "error";
export const PAGE_LIMIT = 50;
/** KPI window: one unfiltered page per direction (07 BO-15 KPI cards — the month's documents). */
export const KPI_LIMIT = 200;

export interface ListRequest<F = null> {
  filters: F;
  cursor: string | null;
}

export interface Kpis {
  inCount: number;
  inTotal: string;
  inVat: string;
  awaitingSignature: number;
  deferredVat: string;
  outUnsent: number;
}

/** `null` until the user picks — then the action dialogs remember the choice for the page. */
export type KeyChoice = string | null;

export type ActionKind =
  | "risk"
  | "signAccept"
  | "reject"
  | "signSend"
  | "send"
  | "cancelOut"
  | "fromReceipt"
  | "createOut"
  | "ettnAccept"
  | "ettnReject"
  | "poaSign"
  | "poaCancel";

export interface Notice {
  kind: ActionKind;
  /** i18n key in `edocs`. */
  key: string;
  params?: Record<string, string>;
}

export interface MountParams {
  today: string;
}

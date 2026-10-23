import type {
  BranchDetailOut,
  BranchListItemOut,
  CashRegisterOut,
  TaxSettingOut,
  WarehouseOut,
} from "@shared/models";

export type Branch = BranchListItemOut;
export type BranchDetail = BranchDetailOut;
export type TaxSetting = TaxSettingOut;
export type Warehouse = WarehouseOut;
export type CashRegister = CashRegisterOut;

/** Aholi punkti toifasi (US-M14-04, SK 467): retail turnover tax 4% / 2% / 1%. */
export type SettlementCategory = "city_100k_plus" | "other" | "remote_mountain";
export const SETTLEMENT_CATEGORIES: readonly SettlementCategory[] = [
  "city_100k_plus",
  "other",
  "remote_mountain",
];
/** The most conservative default (20 #31, US-M14-04). */
export const DEFAULT_SETTLEMENT_CATEGORY: SettlementCategory = "city_100k_plus";

export type ActivityType = "retail" | "other";
export type WarehouseType = "store" | "stock";
export type InventoryAccount = "2910" | "2920";
export type CashRegisterKind = "web" | "android";
export type CardManualFallback = "allow" | "manager_approval" | "forbid";

export interface CreateBranchInput {
  name: string;
  address: string;
  settlementCategory: SettlementCategory;
  /** false = the owner left the default → "please verify" hint (US-M14-04 negative). */
  categoryChosen: boolean;
  warehouseType: WarehouseType;
}

export interface UpdateBranchInput {
  branchId: string;
  version: number;
  name?: string;
  address?: string | null;
  settlementCategory?: SettlementCategory;
}

export interface CreateTaxSettingInput {
  branchId: string;
  validFrom: string;
  settlementCategory: SettlementCategory;
  activityType: ActivityType;
}

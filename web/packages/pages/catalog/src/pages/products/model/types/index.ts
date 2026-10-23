import type { ProductCreate, ProductListItem, ProductOut, ProductUpdate } from "@shared/models";

export interface ProductFilters {
  search: string;
  /** null = all categories. */
  categoryId: string | null;
  /** false = active products (default), true = archive. */
  archived: boolean;
}

export type ListStatus = "idle" | "loading" | "error";

export const PRODUCTS_PAGE_SIZE = 25;

/** VAT choice in the form: 12% / 0% / exemption code (19 §1: `vat_rate` or `vat_exemption_code`). */
export type VatMode = "12.00" | "0.00" | "exempt";

/** `platform.marking_product_groups.code` (19 §1, qaror #63). */
export const MARKING_GROUPS = ["general", "water_beverages", "medicines", "vegetable_oil"] as const;
export type MarkingGroup = (typeof MARKING_GROUPS)[number];

/** Product editor form values (strings for inputs; mapped to the API payload in lib). */
export interface ProductFormValues {
  name: string;
  name_ru: string;
  category_id: string;
  unit_code: string;
  mxik_code: string;
  vat_mode: VatMode;
  vat_exemption_code: string;
  is_marked: boolean;
  marking_group_code: string;
  is_weighed: boolean;
  min_stock: string;
  /** First barcode (create only — PATCH /products takes no barcode, 19 §1). */
  barcode: string;
}

export interface UpdateProductParams {
  id: string;
  body: ProductUpdate;
}

export type { ProductCreate, ProductListItem, ProductOut, ProductUpdate };

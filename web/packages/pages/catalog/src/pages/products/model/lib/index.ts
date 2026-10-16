import type { ListProductsParams } from "@shared/models";

import {
  PRODUCTS_PAGE_SIZE,
  type ProductCreate,
  type ProductFilters,
  type ProductFormValues,
  type ProductOut,
  type ProductUpdate,
  type VatMode,
} from "../types/index.ts";

export function listParams(filters: ProductFilters, page: number): ListProductsParams {
  return {
    search: filters.search || undefined,
    category_id: filters.categoryId ?? undefined,
    archived: filters.archived,
    page,
    size: PRODUCTS_PAGE_SIZE,
  };
}

const blankToNull = (value: string): string | null => (value.trim() === "" ? null : value.trim());

export function emptyProductForm(defaultUnit = "pcs"): ProductFormValues {
  return {
    name: "",
    name_ru: "",
    category_id: "",
    unit_code: defaultUnit,
    mxik_code: "",
    vat_mode: "12.00",
    vat_exemption_code: "",
    is_marked: false,
    marking_group_code: "",
    is_weighed: false,
    min_stock: "",
    barcode: "",
  };
}

function vatModeOf(product: ProductOut): VatMode {
  if (product.vat_rate === null) return "exempt";
  return product.vat_rate.startsWith("0") ? "0.00" : "12.00";
}

export function productToForm(product: ProductOut): ProductFormValues {
  return {
    name: product.name,
    name_ru: product.name_ru ?? "",
    category_id: product.category_id ?? "",
    unit_code: product.unit_code,
    mxik_code: product.mxik_code ?? "",
    vat_mode: vatModeOf(product),
    vat_exemption_code: product.vat_exemption_code ?? "",
    is_marked: product.is_marked,
    marking_group_code: product.marking_group_code ?? "",
    is_weighed: product.is_weighed,
    min_stock: product.min_stock ?? "",
    barcode: "",
  };
}

function common(values: ProductFormValues) {
  const exempt = values.vat_mode === "exempt";
  return {
    name: values.name.trim(),
    name_ru: blankToNull(values.name_ru),
    category_id: blankToNull(values.category_id),
    unit_code: values.unit_code,
    mxik_code: blankToNull(values.mxik_code),
    vat_rate: exempt ? null : values.vat_mode,
    vat_exemption_code: exempt ? blankToNull(values.vat_exemption_code) : null,
    is_marked: values.is_marked,
    marking_group_code: values.is_marked ? blankToNull(values.marking_group_code) : null,
    is_weighed: values.is_weighed,
    min_stock: blankToNull(values.min_stock),
  };
}

export function formToCreate(values: ProductFormValues): ProductCreate {
  return { ...common(values), barcode: blankToNull(values.barcode) };
}

export function formToUpdate(values: ProductFormValues, version: number): ProductUpdate {
  return { ...common(values), version };
}

/** Form field ← server `details[].field` (the form uses `vat_mode` for the VAT pair). */
export const PRODUCT_FIELD_MAP: Readonly<Record<string, keyof ProductFormValues>> = {
  vat_rate: "vat_mode",
};

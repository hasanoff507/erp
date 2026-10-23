/**
 * Product picker for document lines (transfer, count, write-off, purchase order, receipt):
 * `GET /products?search=` (name / barcode, 19 §1), active products only.
 */
import { Plus } from "lucide-react";

import { api } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import type { ProductListItem } from "@shared/models";

import { createSearch, type SearchModel } from "#/shared/lib/search.ts";
import { unitLabel } from "#/shared/lib/units.ts";
import { SearchPicker } from "#/shared/ui/SearchPicker.tsx";

export type PickedProduct = ProductListItem;

export const PRODUCT_SEARCH_LIMIT = 10;

export function createProductSearch(): SearchModel<PickedProduct> {
  return createSearch(async (search) => {
    const page = await api.pricing.listProducts({
      search,
      archived: false,
      page: 1,
      size: PRODUCT_SEARCH_LIMIT,
    });
    return page.items;
  });
}

export interface ProductPickerProps {
  model: SearchModel<PickedProduct>;
  onPick: (product: PickedProduct) => void;
  disabled?: boolean;
}

export function ProductPicker({ model, onPick, disabled }: ProductPickerProps) {
  const { t } = useTranslation("warehouse");
  return (
    <SearchPicker
      model={model}
      variant="dashed"
      trigger={t("picker.addProduct")}
      triggerIcon={Plus}
      searchLabel={t("picker.productSearch")}
      placeholder={t("picker.productPlaceholder")}
      getKey={(p) => p.id}
      renderItem={(p) => ({
        title: p.name,
        meta: [p.barcodes[0]?.barcode, unitLabel(p.unit_code)].filter(Boolean).join(" · "),
      })}
      onPick={onPick}
      disabled={disabled}
    />
  );
}

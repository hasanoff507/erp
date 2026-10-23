/**
 * Supplier picker (BO-04 «Yetkazib beruvchi» Combobox): `GET /counterparties?is_supplier=true&search=`
 * (19 §9 — one `counterparties` resource for customers and suppliers), active ones only.
 */
import { api } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import type { CounterpartyListItem } from "@shared/models";

import { createSearch, type SearchModel } from "#/shared/lib/search.ts";
import { SearchPicker } from "#/shared/ui/SearchPicker.tsx";

export type PickedSupplier = Pick<CounterpartyListItem, "id" | "name" | "stir">;

export function createSupplierSearch(): SearchModel<CounterpartyListItem> {
  return createSearch(async (search) => {
    const page = await api.debts.listCounterparties({
      search,
      is_supplier: true,
      archived: false,
      page: 1,
      size: 10,
    });
    return page.items;
  });
}

export interface SupplierPickerProps {
  model: SearchModel<CounterpartyListItem>;
  value: PickedSupplier | null;
  onPick: (supplier: CounterpartyListItem) => void;
  disabled?: boolean;
  id?: string;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
}

export function SupplierPicker({ model, value, onPick, disabled, ...control }: SupplierPickerProps) {
  const { t } = useTranslation("warehouse");
  return (
    <SearchPicker
      {...control}
      model={model}
      variant="outline"
      className="w-full justify-start font-semibold"
      trigger={value ? value.name : t("picker.chooseSupplier")}
      searchLabel={t("picker.supplierSearch")}
      placeholder={t("picker.supplierPlaceholder")}
      getKey={(s) => s.id}
      renderItem={(s) => ({
        title: s.name,
        meta: s.stir ? t("suppliers.stirValue", { stir: s.stir }) : undefined,
      })}
      onPick={onPick}
      disabled={disabled}
    />
  );
}

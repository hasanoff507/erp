import { useUnit } from "effector-react";
import { Lock } from "lucide-react";
import { useState } from "react";

import { toApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { Button, Card, ErrorState, Icon, NativeSelect, Skeleton, toast } from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $warehouses,
  $warehousesError,
  branchDataReloadRequested,
  fetchWarehousesFx,
  updateWarehouseFx,
  type InventoryAccount,
  type Warehouse,
} from "../../model/index.ts";

/**
 * «Omborlar va tovar hisobi» (07 BO-12 `warehouses[].inventoryAccount`): 2910 ombor / 2920 savdo zali,
 * saved with PATCH /warehouses/{id}; with stock movements the server answers WAREHOUSE_ACCOUNT_LOCKED.
 */
export function Warehouses({ canEdit }: { canEdit: boolean }) {
  const { t } = useTranslation("settings");
  const [warehouses, error, loading, reload] = useUnit([
    $warehouses,
    $warehousesError,
    fetchWarehousesFx.pending,
    branchDataReloadRequested,
  ]);

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="text-[15px] font-bold">{t("branches.warehouses.title")}</h2>
      {error ? (
        <ErrorState message={errorText(error)} onRetry={reload} className="py-6" />
      ) : loading && warehouses.length === 0 ? (
        <Skeleton className="h-12 w-full" />
      ) : (
        <ul className="flex flex-col divide-y divide-divider">
          {warehouses.map((w) => (
            <WarehouseRow key={`${w.id}:${w.version}`} warehouse={w} canEdit={canEdit} />
          ))}
        </ul>
      )}
    </Card>
  );
}

function WarehouseRow({ warehouse, canEdit }: { warehouse: Warehouse; canEdit: boolean }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const [update, saving] = useUnit([updateWarehouseFx, updateWarehouseFx.pending]);
  const online = useOnline();
  const [account, setAccount] = useState<InventoryAccount>(warehouse.inventory_account);
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectId = `wh-${warehouse.id}`;

  const save = async () => {
    setError(null);
    try {
      await update({ warehouseId: warehouse.id, inventoryAccount: account, version: warehouse.version });
      toast.success(t("branches.warehouses.saved"));
    } catch (e) {
      const apiError = toApiError(e);
      if (apiError.code === "WAREHOUSE_ACCOUNT_LOCKED") {
        setLocked(true);
        setAccount(warehouse.inventory_account);
      }
      setError(errorText(apiError));
    }
  };

  return (
    <li className="flex flex-wrap items-center gap-3 py-2.5">
      <div className="min-w-0 flex-1">
        <p className="text-[14px] font-bold">{warehouse.name}</p>
        <p className="text-[12px] text-muted-foreground">{t(`branches.warehouseType.${warehouse.type}`)}</p>
      </div>
      <label htmlFor={selectId} className="sr-only">
        {t("branches.warehouses.account", { name: warehouse.name })}
      </label>
      <NativeSelect
        id={selectId}
        options={[
          { value: "2920", label: t("branches.warehouses.account2920") },
          { value: "2910", label: t("branches.warehouses.account2910") },
        ]}
        value={account}
        disabled={!canEdit || locked || !online}
        onChange={(e) => setAccount(e.target.value === "2910" ? "2910" : "2920")}
      />
      {canEdit ? (
        <Button
          size="sm"
          variant="secondary"
          disabled={!online || saving || locked || account === warehouse.inventory_account}
          onClick={() => void save()}
        >
          {tc("actions.save")}
        </Button>
      ) : null}
      {error ? (
        <p
          role="alert"
          className="flex w-full items-center gap-1.5 text-small font-semibold text-destructive"
        >
          {locked ? <Icon as={Lock} size="sm" /> : null}
          {error}
        </p>
      ) : null}
    </li>
  );
}

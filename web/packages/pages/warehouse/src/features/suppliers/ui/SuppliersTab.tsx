/**
 * BO-04 «Yetkazib beruvchilar» (19 §9): list (qidiruv, arxivdagilar), card (rekvizitlar, «Joriy
 * qarzimiz» 6010), create / edit with STIR lookup, archive / unarchive (`purchases.create`).
 */
import { useUnit } from "effector-react";
import { Archive, ArchiveRestore, Pencil, Plus, Truck } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import {
  Button,
  DataTable,
  EmptyState,
  Icon,
  Label,
  SearchInput,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  Skeleton,
  StatusChip,
  Switch,
  toast,
  type DataTableColumn,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";

import {
  $acting,
  $debt,
  $detail,
  $error,
  $filters,
  $page,
  $rows,
  $selectedId,
  $status,
  $total,
  EMPTY_FORM,
  SUPPLIER_PAGE_SIZE,
  archiveSupplierFx,
  archivedToggled,
  createSupplierFx,
  formOf,
  pageChanged,
  reloadRequested,
  searchChanged,
  supplierSelected,
  updateSupplierFx,
  type SupplierRow,
} from "../model/index.ts";

import { SupplierForm } from "./SupplierForm.tsx";

export function SuppliersTab({ canManage, online }: { canManage: boolean; online: boolean }) {
  const { t } = useTranslation("warehouse");
  const [rows, total, page, status, error, filters] = useUnit([
    $rows,
    $total,
    $page,
    $status,
    $error,
    $filters,
  ]);
  const [onSearch, onArchived, onPage, reload, select] = useUnit([
    searchChanged,
    archivedToggled,
    pageChanged,
    reloadRequested,
    supplierSelected,
  ]);
  const [creating, setCreating] = useState(false);

  const columns: DataTableColumn<SupplierRow>[] = [
    {
      id: "name",
      header: t("suppliers.columns.name"),
      cell: (s) => (
        <span className="flex flex-col">
          <span className="font-semibold">{s.name}</span>
          <span className="text-[12px] text-muted-foreground">{t(`suppliers.kind.${s.kind}`)}</span>
        </span>
      ),
    },
    {
      id: "stir",
      header: t("suppliers.columns.stir"),
      width: "130px",
      cell: (s) => <span className="tabular-nums">{s.stir ?? "—"}</span>,
    },
    { id: "phone", header: t("suppliers.columns.phone"), width: "160px", cell: (s) => s.phone ?? "—" },
    {
      id: "vat",
      header: t("suppliers.columns.vat"),
      width: "130px",
      cell: (s) =>
        s.vat_payer === null ? (
          "—"
        ) : s.vat_payer ? (
          <StatusChip tone="info">{t("suppliers.vatYes")}</StatusChip>
        ) : (
          t("suppliers.vatNo")
        ),
    },
    {
      id: "payable",
      header: t("suppliers.columns.payable"),
      numeric: true,
      width: "150px",
      cell: (s) => formatMoney(s.payable_balance, { withCurrency: false }),
    },
  ];

  return (
    <section className="flex flex-col gap-3" aria-label={t("purchases.tabs.suppliers")}>
      <div className="flex flex-wrap items-center gap-4">
        <SearchInput
          className="w-72"
          value={filters.search}
          onSearch={onSearch}
          aria-label={t("suppliers.search")}
          placeholder={t("suppliers.searchPlaceholder")}
        />
        <span className="flex items-center gap-2">
          <Switch id="suppliers-archived" checked={filters.archived} onCheckedChange={onArchived} />
          <Label htmlFor="suppliers-archived">{t("suppliers.archived")}</Label>
        </span>
        <div className="grow" />
        {canManage ? (
          <Button disabled={!online} onClick={() => setCreating(true)}>
            <Icon as={Plus} size="sm" />
            {t("suppliers.create")}
          </Button>
        ) : null}
      </div>
      <DataTable
        label={t("suppliers.tableLabel")}
        columns={columns}
        data={rows}
        getRowId={(s) => s.id}
        status={status}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={reload}
        onRowClick={(s) => select(s.id)}
        minWidth={760}
        empty={
          <EmptyState
            icon={Truck}
            title={t("suppliers.empty.title")}
            description={t("suppliers.empty.description")}
          />
        }
        pagination={{ kind: "page", page, size: SUPPLIER_PAGE_SIZE, total, onPageChange: onPage }}
      />
      <CreateSupplierSheet
        open={creating}
        onClose={() => setCreating(false)}
        online={online}
        canLookup={canManage}
      />
      <SupplierDetailSheet canManage={canManage} online={online} />
    </section>
  );
}

function CreateSupplierSheet({
  open,
  onClose,
  online,
  canLookup,
}: {
  open: boolean;
  onClose: () => void;
  online: boolean;
  canLookup: boolean;
}) {
  const { t } = useTranslation("warehouse");
  const [create, pending, select] = useUnit([createSupplierFx, createSupplierFx.pending, supplierSelected]);
  return (
    <Sheet open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>{t("suppliers.createTitle")}</SheetTitle>
          <SheetDescription>{t("suppliers.createDescription")}</SheetDescription>
        </SheetHeader>
        <SheetBody>
          {open ? (
            <SupplierForm
              initial={EMPTY_FORM}
              submitLabel={t("actions.save")}
              pending={pending}
              online={online}
              canLookup={canLookup}
              onCancel={onClose}
              onOpenExisting={(id) => {
                onClose();
                select(id);
              }}
              onSubmit={async (values) => {
                const created = await create(values);
                toast.success(t("suppliers.toast.created", { name: created.name }));
                onClose();
              }}
            />
          ) : null}
        </SheetBody>
      </SheetContent>
    </Sheet>
  );
}

function SupplierDetailSheet({ canManage, online }: { canManage: boolean; online: boolean }) {
  const { t } = useTranslation("warehouse");
  const [selectedId, detail, debt, acting, select, update, archive] = useUnit([
    $selectedId,
    $detail,
    $debt,
    $acting,
    supplierSelected,
    updateSupplierFx,
    archiveSupplierFx,
  ]);
  const [editing, setEditing] = useState(false);
  const close = () => {
    setEditing(false);
    select(null);
  };

  return (
    <Sheet open={selectedId !== null} onOpenChange={(next) => (next ? undefined : close())}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>{detail?.name ?? t("suppliers.detailTitle")}</SheetTitle>
          {detail ? (
            <SheetDescription>
              {t(`suppliers.kind.${detail.kind}`)}
              {detail.stir ? ` · ${t("suppliers.stirValue", { stir: detail.stir })}` : ""}
            </SheetDescription>
          ) : null}
          {detail?.archived_at ? (
            <div className="pt-1">
              <StatusChip tone="neutral">{t("suppliers.archivedChip")}</StatusChip>
            </div>
          ) : null}
        </SheetHeader>
        <SheetBody>
          {!detail ? (
            <div className="flex flex-col gap-3" aria-busy="true">
              <Skeleton className="h-6 w-1/2" />
              <Skeleton className="h-32 w-full" />
            </div>
          ) : editing ? (
            <SupplierForm
              initial={formOf(detail)}
              submitLabel={t("actions.save")}
              pending={acting}
              online={online}
              canLookup={canManage}
              onCancel={() => setEditing(false)}
              onOpenExisting={(id) => {
                setEditing(false);
                select(id);
              }}
              onSubmit={async (values) => {
                await update({ id: detail.id, values, version: detail.version });
                toast.success(t("suppliers.toast.updated"));
                setEditing(false);
              }}
            />
          ) : (
            <>
              <div
                role="group"
                aria-label={t("suppliers.debt.label")}
                className="flex items-center justify-between rounded-lg border border-border bg-muted px-4 py-3"
              >
                <span className="text-[13px] font-semibold text-foreground-secondary">
                  {t("suppliers.debt.payable")}
                </span>
                <span className="text-[16px] font-extrabold tabular-nums" data-testid="supplier-payable">
                  {debt ? formatMoney(debt.payable) : "…"}
                </span>
              </div>
              <dl className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] gap-x-4 gap-y-2 text-[13px]">
                {(
                  [
                    ["phone", detail.phone],
                    ["legalAddress", detail.legal_address],
                    ["bankAccount", detail.bank_account],
                    ["bankMfo", detail.bank_mfo],
                    ["note", detail.note],
                  ] as const
                ).map(([key, value]) => (
                  <div key={key} className="contents">
                    <dt className="text-muted-foreground">{t(`suppliers.fields.${key}`)}</dt>
                    <dd className="font-semibold">{value ?? "—"}</dd>
                  </div>
                ))}
                <dt className="text-muted-foreground">{t("suppliers.fields.vatPayer")}</dt>
                <dd className="font-semibold">
                  {detail.vat_payer === null
                    ? "—"
                    : detail.vat_payer
                      ? t("suppliers.vatYes")
                      : t("suppliers.vatNo")}
                </dd>
              </dl>
              {canManage ? (
                <div className="flex flex-wrap justify-end gap-2">
                  <Button
                    variant="secondary"
                    disabled={!online || acting}
                    onClick={() =>
                      archive({ id: detail.id, archive: detail.archived_at === null })
                        .then((s) =>
                          toast.success(
                            t(s.archived_at ? "suppliers.toast.archived" : "suppliers.toast.unarchived"),
                          ),
                        )
                        .catch((e: unknown) => toast.error(errorText(e)))
                    }
                  >
                    <Icon as={detail.archived_at ? ArchiveRestore : Archive} size="sm" />
                    {t(detail.archived_at ? "suppliers.unarchive" : "suppliers.archive")}
                  </Button>
                  <Button disabled={!online} onClick={() => setEditing(true)}>
                    <Icon as={Pencil} size="sm" />
                    {t("actions.edit")}
                  </Button>
                </div>
              ) : null}
            </>
          )}
        </SheetBody>
      </SheetContent>
    </Sheet>
  );
}

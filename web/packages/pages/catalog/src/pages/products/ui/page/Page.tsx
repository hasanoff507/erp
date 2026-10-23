/**
 * Tovarlar katalogi — product list + product card (19 §1–§3). 07 names no separate route for the
 * product list, so it lives inside the BO-05 «Tovarlar va narxlar» area (proposed spec edit in the
 * W3 report): `/app/catalog/products`, `/app/catalog/products/new`, `/app/catalog/products/:productId`.
 * View: `stock.view`; create/edit/archive/barcodes/MXIK/categories: `catalog.manage`.
 * The «Joriy narx» column is `current_price` of the list (19 §1: X-Branch-Id branch → global price).
 */
import { Archive, ArchiveRestore, FolderTree, PackagePlus, Pencil, Upload, WifiOff } from "lucide-react";
import { useUnit } from "effector-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import type { ApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { formatMoney, formatPercent } from "@shared/lib/format";
import type { ProductListItem, ProductOut } from "@shared/models";
import { $isOnline } from "@shared/state/network";
import { useCan } from "@shared/state/permissions";
import {
  Banner,
  Button,
  ConfirmDialog,
  DataTable,
  EmptyState,
  Icon,
  NoPermissionState,
  SearchInput,
  SegmentedControl,
  Sheet,
  SheetContent,
  SimpleSelect,
  StatusChip,
  toast,
  type DataTableColumn,
} from "@shared/ui";

import { $categories, $categoryNames, unitLabel } from "#/entities/product/index.ts";
import { apiErrorText } from "#/shared/lib/messages.ts";

import {
  $editing,
  $editingError,
  $filters,
  $listError,
  $listStatus,
  $page,
  $products,
  $total,
  archivedChanged,
  archiveProductFx,
  categoryChanged,
  editorClosed,
  listRefreshRequested,
  pageChanged,
  pageMounted,
  PRODUCTS_PAGE_SIZE,
  productRequested,
  searchChanged,
  unarchiveProductFx,
} from "../../model/index.ts";
import { CategoriesDialog } from "../categories/CategoriesDialog.tsx";
import { ProductEditor, ProductEditorLoading } from "../editor/ProductEditor.tsx";

export const PRODUCTS_PATH = "/app/catalog/products";
const ALL = "all";

function ProductsPage() {
  const canView = useCan({ permission: "stock.view" });
  const canManage = useCan({ permission: "catalog.manage" });
  const mounted = useUnit(pageMounted);
  useEffect(() => {
    if (canView) mounted();
  }, [mounted, canView]);

  if (!canView) return <NoPermissionState />;
  return <ProductsScreen canManage={canManage} />;
}

function ProductsScreen({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation("catalog");
  const navigate = useNavigate();
  const online = useUnit($isOnline);
  // Same requirement as the BO-05 sidebar item (nav-items.ts).
  const canSeePrices = useCan({ anyOf: ["prices.edit", "discount.rule.manage", "prices.approve"] });
  const [categoriesOpen, setCategoriesOpen] = useState(false);

  return (
    <div className="flex flex-col gap-[18px]">
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="min-w-0">
          <p className="text-small text-foreground-secondary">{t("products.subtitle")}</p>
        </div>
        <div className="grow" />
        {canSeePrices ? (
          <Button variant="secondary" asChild>
            <Link to="/app/catalog/prices">{t("nav.prices")}</Link>
          </Button>
        ) : null}
        {canManage ? (
          <>
            <Button variant="secondary" onClick={() => setCategoriesOpen(true)} disabled={!online}>
              <Icon as={FolderTree} size="sm" />
              {t("categories.open")}
            </Button>
            <Button variant="secondary" asChild>
              <Link to={`${PRODUCTS_PATH}/import`}>
                <Icon as={Upload} size="sm" />
                {t("products.actions.import")}
              </Link>
            </Button>
            <Button onClick={() => void navigate(`${PRODUCTS_PATH}/new`)} disabled={!online}>
              <Icon as={PackagePlus} size="sm" />
              {t("products.actions.create")}
            </Button>
          </>
        ) : null}
      </div>

      {online ? null : (
        <Banner tone="warning" icon={WifiOff}>
          {t("products.offline")}
        </Banner>
      )}

      <Filters />
      <ProductsTable canManage={canManage && online} />
      <EditorSheet canManage={canManage && online} />
      {canManage ? <CategoriesDialog open={categoriesOpen} onOpenChange={setCategoriesOpen} /> : null}
    </div>
  );
}

function Filters() {
  const { t } = useTranslation("catalog");
  const [filters, categories, onSearch, onCategory, onArchived] = useUnit([
    $filters,
    $categories,
    searchChanged,
    categoryChanged,
    archivedChanged,
  ]);
  return (
    <div className="flex flex-wrap items-end gap-3">
      <SearchInput
        value={filters.search}
        onSearch={onSearch}
        className="max-w-md flex-[1_1_280px]"
        aria-label={t("products.filters.search")}
        placeholder={t("products.filters.searchPlaceholder")}
      />
      <SimpleSelect
        aria-label={t("products.filters.category")}
        className="w-56"
        options={[
          { value: ALL, label: t("products.filters.allCategories") },
          ...categories.map((c) => ({ value: c.id, label: c.name })),
        ]}
        value={filters.categoryId ?? ALL}
        onValueChange={(v) => onCategory(v === ALL ? null : v)}
      />
      <SegmentedControl
        label={t("products.filters.status")}
        value={filters.archived ? "archived" : "active"}
        onChange={(v) => onArchived(v === "archived")}
        options={[
          { value: "active", label: t("products.filters.active") },
          { value: "archived", label: t("products.filters.archived") },
        ]}
      />
    </div>
  );
}

function ProductsTable({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation("catalog");
  const navigate = useNavigate();
  const [products, total, page, status, error, names, filters, onPage, retry] = useUnit([
    $products,
    $total,
    $page,
    $listStatus,
    $listError,
    $categoryNames,
    $filters,
    pageChanged,
    listRefreshRequested,
  ]);
  const [archive, unarchive, archiving] = useUnit([
    archiveProductFx,
    unarchiveProductFx,
    archiveProductFx.pending,
  ]);
  const [toArchive, setToArchive] = useState<ProductOut | null>(null);
  const [archiveError, setArchiveError] = useState<string | null>(null);

  const columns: DataTableColumn<ProductListItem>[] = [
    {
      id: "name",
      header: t("products.columns.name"),
      cell: (p) => (
        <span className="flex min-w-0 flex-col">
          <span className="truncate font-semibold">{p.name}</span>
          <span className="truncate text-[12px] text-muted-foreground">
            {p.name_ru ?? t("products.noNameRu")}
            {p.category_id ? ` · ${names.get(p.category_id) ?? ""}` : ""}
          </span>
        </span>
      ),
    },
    {
      id: "barcode",
      header: t("products.columns.barcode"),
      width: "170px",
      cell: (p) =>
        p.barcodes.length === 0 ? (
          <StatusChip tone="warning">{t("products.noBarcode")}</StatusChip>
        ) : (
          <span className="tabular-nums">
            {p.barcodes[0]?.barcode}
            {p.barcodes.length > 1 ? (
              <span className="text-muted-foreground"> +{p.barcodes.length - 1}</span>
            ) : null}
          </span>
        ),
    },
    {
      id: "price",
      header: t("prices.columns.current"),
      width: "140px",
      numeric: true,
      cell: (p) =>
        p.current_price ? (
          formatMoney(p.current_price)
        ) : (
          <span className="font-normal text-muted-foreground">{t("prices.noPrice")}</span>
        ),
    },
    { id: "unit", header: t("products.columns.unit"), width: "90px", cell: (p) => unitLabel(p.unit_code) },
    {
      id: "mxik",
      header: t("products.columns.mxik"),
      width: "190px",
      cell: (p) =>
        p.mxik_code ? (
          <span className="tabular-nums">{p.mxik_code}</span>
        ) : (
          <StatusChip tone="warning">{t("products.noMxik")}</StatusChip>
        ),
    },
    {
      id: "vat",
      header: t("products.columns.vat"),
      width: "100px",
      cell: (p) => (p.vat_rate === null ? t("products.vat.exemptShort") : formatPercent(p.vat_rate)),
    },
    {
      id: "flags",
      header: t("products.columns.flags"),
      width: "180px",
      cell: (p) => (
        <span className="flex flex-wrap gap-1">
          {p.archived_at ? <StatusChip tone="neutral">{t("products.status.archived")}</StatusChip> : null}
          {p.is_marked ? <StatusChip tone="info">{t("products.status.marked")}</StatusChip> : null}
          {p.is_weighed ? <StatusChip tone="neutral">{t("products.status.weighed")}</StatusChip> : null}
        </span>
      ),
    },
  ];

  const filtered = filters.search !== "" || filters.categoryId !== null;
  return (
    <>
      <DataTable
        label={t("products.tableLabel")}
        columns={columns}
        data={products}
        getRowId={(p) => p.id}
        status={status}
        errorMessage={error ? apiErrorText(error) : undefined}
        onRetry={retry}
        minWidth={900}
        onRowClick={(p) => void navigate(`${PRODUCTS_PATH}/${p.id}`)}
        empty={
          <EmptyState
            icon={PackagePlus}
            title={filtered ? t("products.empty.filtered") : t("products.empty.title")}
            description={filtered ? undefined : t("products.empty.description")}
            action={
              !filtered && canManage ? (
                <div className="mt-1 flex flex-wrap justify-center gap-2">
                  <Button size="sm" onClick={() => void navigate(`${PRODUCTS_PATH}/new`)}>
                    {t("products.actions.create")}
                  </Button>
                  <Button size="sm" variant="secondary" asChild>
                    <Link to={`${PRODUCTS_PATH}/import`}>{t("products.actions.import")}</Link>
                  </Button>
                </div>
              ) : undefined
            }
          />
        }
        rowActions={(p) => [
          {
            id: "edit",
            label: canManage ? t("products.actions.edit") : t("products.actions.view"),
            icon: Pencil,
            onSelect: () => void navigate(`${PRODUCTS_PATH}/${p.id}`),
          },
          ...(canManage
            ? p.archived_at
              ? [
                  {
                    id: "unarchive",
                    label: t("products.actions.unarchive"),
                    icon: ArchiveRestore,
                    onSelect: () => {
                      unarchive(p.id)
                        .then(() => toast.success(t("products.editor.unarchived")))
                        .catch((e: ApiError) => toast.error(apiErrorText(e)));
                    },
                  },
                ]
              : [
                  {
                    id: "archive",
                    label: t("products.actions.archive"),
                    icon: Archive,
                    destructive: true,
                    onSelect: () => {
                      setArchiveError(null);
                      setToArchive(p);
                    },
                  },
                ]
            : []),
        ]}
        pagination={{ kind: "page", page, size: PRODUCTS_PAGE_SIZE, total, onPageChange: onPage }}
      />
      <ConfirmDialog
        open={toArchive !== null}
        onOpenChange={(open) => (open ? undefined : setToArchive(null))}
        title={t("products.archive.title")}
        description={toArchive ? t("products.archive.body", { name: toArchive.name }) : undefined}
        confirmLabel={t("products.actions.archive")}
        tone="destructive"
        pending={archiving}
        error={archiveError}
        onConfirm={() =>
          toArchive
            ? archive(toArchive.id)
                .then(() => toast.success(t("products.editor.archived")))
                .catch((e: ApiError) => {
                  setArchiveError(apiErrorText(e));
                  throw e;
                })
            : undefined
        }
      />
    </>
  );
}

/** Sheet bound to the route: `/new` → empty card, `/:productId` → loaded card. */
function EditorSheet({ canManage }: { canManage: boolean }) {
  const { productId } = useParams();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const isNew = pathname.endsWith("/products/new");
  const [editing, editingError, load, close] = useUnit([
    $editing,
    $editingError,
    productRequested,
    editorClosed,
  ]);

  useEffect(() => {
    if (productId) load(productId);
    else close();
  }, [productId, load, close]);

  const open = isNew || productId !== undefined;
  const onClose = () => {
    close();
    void navigate(PRODUCTS_PATH);
  };
  const loaded = editing && editing.id === productId ? editing : null;

  return (
    <Sheet open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <SheetContent wide>
        {isNew ? (
          <ProductEditor
            key="new"
            product={null}
            canManage={canManage}
            onClose={onClose}
            onCreated={(p) => void navigate(`${PRODUCTS_PATH}/${p.id}`, { replace: true })}
          />
        ) : loaded ? (
          <ProductEditor
            key={`${loaded.id}:${loaded.version}:${loaded.archived_at ?? ""}`}
            product={loaded}
            canManage={canManage}
            onClose={onClose}
            onCreated={() => undefined}
          />
        ) : productId ? (
          <ProductEditorLoading error={editingError} onRetry={() => load(productId)} />
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

export const Products = {
  route: "catalog/products",
  routes: ["catalog/products", "catalog/products/new", "catalog/products/:productId"],
  titleKey: "catalog:products.title",
  Page: ProductsPage,
} as const;

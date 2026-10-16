/** BO-05 «Chakana narxlar» table — current price, editable new price, change %, row status. */
import { useUnit } from "effector-react";

import { useTranslation } from "@shared/i18n";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { DataTable, EmptyState, MoneyInput, StatusChip, type DataTableColumn } from "@shared/ui";
import { Tag } from "lucide-react";
import { Link } from "react-router-dom";

import { $categoryNames } from "#/entities/product/index.ts";
import { apiErrorText } from "#/shared/lib/messages.ts";

import {
  $changes,
  $drafts,
  $listError,
  $listStatus,
  $page,
  $prices,
  $products,
  $selectedId,
  $total,
  draftChanged,
  listRefreshRequested,
  pageChanged,
  PRICES_PAGE_SIZE,
  productSelected,
  rowStateOf,
  type ApprovalLimit,
  type ProductOut,
  type RowState,
} from "../../model/index.ts";

const STATE_TONE: Record<RowState, "neutral" | "primary" | "awaiting-approval" | "destructive"> = {
  unchanged: "neutral",
  changed: "primary",
  approval: "awaiting-approval",
  approvalMaybe: "awaiting-approval",
  invalid: "destructive",
};

export function PriceTable({ editable, approvalLimit }: { editable: boolean; approvalLimit: ApprovalLimit }) {
  const { t } = useTranslation("catalog");
  const [products, prices, drafts, changes, names, status, error, page, total, selectedId] = useUnit([
    $products,
    $prices,
    $drafts,
    $changes,
    $categoryNames,
    $listStatus,
    $listError,
    $page,
    $total,
    $selectedId,
  ]);
  const [onDraft, onSelect, onPage, retry] = useUnit([
    draftChanged,
    productSelected,
    pageChanged,
    listRefreshRequested,
  ]);
  const changeOf = new Map(changes.map((c) => [c.product.id, c]));

  const columns: DataTableColumn<ProductOut>[] = [
    {
      id: "name",
      header: t("prices.columns.product"),
      cell: (p) => (
        <span className="flex min-w-0 flex-col">
          <span className="truncate font-semibold">{p.name}</span>
          <span className="truncate text-[12px] text-muted-foreground">
            {p.name_ru ?? t("products.noNameRu")}
            {p.category_id && names.get(p.category_id) ? ` · ${names.get(p.category_id)}` : ""}
          </span>
        </span>
      ),
    },
    {
      id: "cost",
      header: t("prices.columns.cost"),
      numeric: true,
      width: "110px",
      cell: () => <span className="font-normal text-muted-foreground">{t("common.notAvailable")}</span>,
    },
    {
      id: "current",
      header: t("prices.columns.current"),
      numeric: true,
      width: "130px",
      cell: (p) => {
        const price = prices[p.id];
        if (!price) return <span className="font-normal text-muted-foreground">…</span>;
        return (
          <span className="flex flex-col items-end">
            {price.current ? (
              formatMoney(price.current, { withCurrency: false })
            ) : (
              <span className="font-normal text-muted-foreground">{t("prices.noPrice")}</span>
            )}
            {price.scheduled ? (
              <span className="text-[11px] font-semibold text-info-strong">
                {t("prices.scheduled", {
                  price: formatMoney(price.scheduled.price, { withCurrency: false }),
                })}
              </span>
            ) : null}
          </span>
        );
      },
    },
    {
      id: "markup",
      header: t("prices.columns.markup"),
      numeric: true,
      width: "90px",
      cell: () => <span className="font-normal text-muted-foreground">{t("common.notAvailable")}</span>,
    },
    {
      id: "new",
      header: t("prices.columns.new"),
      width: "170px",
      cell: (p) => {
        const state = rowStateOf(changeOf.get(p.id), approvalLimit);
        return (
          <MoneyInput
            aria-label={t("prices.newPriceFor", { name: p.name })}
            withCurrency={false}
            value={drafts[p.id]?.value ?? prices[p.id]?.current ?? ""}
            onChange={(value) => onDraft({ productId: p.id, value })}
            onFocus={() => onSelect(p.id)}
            disabled={!editable || !prices[p.id]}
            aria-invalid={state === "invalid" || undefined}
            className={
              state === "approval" || state === "approvalMaybe"
                ? "[&_input]:border-awaiting-approval [&_input]:bg-awaiting-approval-soft/40"
                : state === "changed"
                  ? "[&_input]:border-primary [&_input]:bg-primary-soft/40"
                  : undefined
            }
          />
        );
      },
    },
    {
      id: "delta",
      header: t("prices.columns.delta"),
      numeric: true,
      width: "100px",
      cell: (p) => {
        const change = changeOf.get(p.id);
        if (!change?.pct) return <span className="font-normal text-muted-foreground">—</span>;
        const sign = change.pct.startsWith("-") ? "" : "+";
        const state = rowStateOf(change, approvalLimit);
        const over = state === "approval" || state === "approvalMaybe";
        return (
          <span className={over ? "text-awaiting-approval-strong" : "text-primary-strong"}>
            {sign}
            {formatPercent(change.pct)}
          </span>
        );
      },
    },
    {
      id: "state",
      header: t("prices.columns.state"),
      width: "140px",
      cell: (p) => {
        const state = rowStateOf(changeOf.get(p.id), approvalLimit);
        return <StatusChip tone={STATE_TONE[state]}>{t(`prices.state.${state}`)}</StatusChip>;
      },
    },
  ];

  return (
    <DataTable
      label={t("prices.tableLabel")}
      columns={columns}
      data={products}
      getRowId={(p) => p.id}
      status={status}
      errorMessage={error ? apiErrorText(error) : undefined}
      onRetry={retry}
      minWidth={880}
      selectedRowId={selectedId}
      onRowClick={(p) => onSelect(p.id)}
      empty={
        <EmptyState
          icon={Tag}
          title={t("prices.empty.title")}
          description={t("prices.empty.description")}
          action={
            <Link className="text-small font-semibold text-primary" to="/app/catalog/products">
              {t("prices.empty.action")}
            </Link>
          }
        />
      }
      pagination={{ kind: "page", page, size: PRICES_PAGE_SIZE, total, onPageChange: onPage }}
    />
  );
}

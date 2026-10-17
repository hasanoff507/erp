/**
 * BO-03 «Qoldiq» tab (07): kam qoldiq / muddati yaqin banner («Faqat kamlarini ko'rsatish»,
 * «Xaridnoma tuzish»), filters (qidiruv, faqat kam qoldiq, muddati 7 kunda tugaydi), the balance
 * table (tovar — birlik, kategoriya, markirovka; shtrix-kod, qoldiq, min., tannarx (o'rt.), qiymat,
 * holat «Kam qoldi» / «Yetarli» + «Muddati N kunda», «⚠ manfiy»), sahifadagi jami, oxirgi yangilanish.
 * The expiring view lists lots (`GET /stock-lots?expiring_within_days=7`) with «Hisobdan chiqarish».
 */
import { useUnit } from "effector-react";
import { CalendarClock, PackageOpen, Trash2, TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatDateTime, formatMoney } from "@shared/lib/format";
import {
  Banner,
  Button,
  DataTable,
  EmptyState,
  Icon,
  Label,
  SearchInput,
  StatusChip,
  Switch,
  buttonVariants,
  type DataTableColumn,
} from "@shared/ui";

import { $categories, $products, unitLabel, useQtyFormat } from "#/entities/refs/index.ts";
import { daysUntil } from "#/shared/lib/effect.ts";
import { isNegative } from "#/shared/lib/decimal.ts";
import { errorText } from "#/shared/lib/errors.ts";

import {
  $balances,
  $cursor,
  $error,
  $expiring,
  $expiryDays,
  $filters,
  $lastUpdated,
  $lots,
  $lotsCursor,
  $lotsError,
  $lotsMoreLoading,
  $lotsStatus,
  $moreLoading,
  $pageTotal,
  $status,
  $summary,
  $today,
  $view,
  EXPIRY_DAYS,
  lotsMoreRequested,
  lowOnlyToggled,
  moreRequested,
  reloadRequested,
  searchChanged,
  viewChanged,
  type Balance,
  type Lot,
} from "../../model/index.ts";

export interface BalancesTabProps {
  canWriteOff: boolean;
  canCreatePo: boolean;
  online: boolean;
  onWriteOffLot: (lot: Lot) => void;
}

function ExpiryChip({ days }: { days: number }) {
  const { t } = useTranslation("warehouse");
  return days < 0 ? (
    <StatusChip tone="destructive">{t("stock.status.expired")}</StatusChip>
  ) : (
    <StatusChip tone="warning">{t("stock.status.expiresIn", { count: days })}</StatusChip>
  );
}

export function BalancesTab({ canWriteOff, canCreatePo, online, onWriteOffLot }: BalancesTabProps) {
  const { t } = useTranslation("warehouse");
  const [
    rows,
    status,
    error,
    cursor,
    moreLoading,
    filters,
    view,
    total,
    updated,
    summary,
    expiring,
    expiryDays,
  ] = useUnit([
    $balances,
    $status,
    $error,
    $cursor,
    $moreLoading,
    $filters,
    $view,
    $pageTotal,
    $lastUpdated,
    $summary,
    $expiring,
    $expiryDays,
  ]);
  const [onSearch, onLow, onView, more, reload] = useUnit([
    searchChanged,
    lowOnlyToggled,
    viewChanged,
    moreRequested,
    reloadRequested,
  ]);
  const [products, categories] = useUnit([$products, $categories]);
  const formatQty = useQtyFormat();

  const unitOf = (productId: string) => products[productId]?.unit_code;
  const expiringCount = expiring?.lots.length ?? 0;
  const lowCount = summary?.low ?? 0;

  const columns: DataTableColumn<Balance>[] = [
    {
      id: "product",
      header: t("stock.columns.product"),
      cell: (b) => {
        const p = products[b.product_id];
        const meta = [
          unitLabel(p?.unit_code),
          p?.category_id ? categories[p.category_id] : null,
          p?.is_marked ? t("stock.marked") : null,
        ].filter(Boolean);
        return (
          <span className="flex flex-col">
            <span className="font-semibold">{b.product_name}</span>
            {meta.length > 0 ? (
              <span className="text-[12px] text-muted-foreground">{meta.join(" · ")}</span>
            ) : null}
          </span>
        );
      },
    },
    {
      id: "barcode",
      header: t("stock.columns.barcode"),
      width: "140px",
      cell: (b) => (
        <span className="tabular-nums text-foreground-secondary">
          {products[b.product_id]?.barcodes[0]?.barcode ?? "—"}
        </span>
      ),
    },
    {
      id: "qty",
      header: t("stock.columns.qty"),
      numeric: true,
      width: "110px",
      cell: (b) => (
        <span className={b.is_low || b.is_negative ? "text-destructive-strong" : undefined}>
          {formatQty(b.qty, unitOf(b.product_id))}
        </span>
      ),
    },
    {
      id: "min",
      header: t("stock.columns.min"),
      numeric: true,
      width: "90px",
      cell: (b) => (b.min_stock ? formatQty(b.min_stock, unitOf(b.product_id)) : "—"),
    },
    {
      id: "cost",
      header: t("stock.columns.avgCost"),
      numeric: true,
      width: "130px",
      cell: (b) => (b.avg_cost ? formatMoney(b.avg_cost, { withCurrency: false }) : "—"),
    },
    {
      id: "value",
      header: t("stock.columns.value"),
      numeric: true,
      width: "140px",
      cell: (b) => formatMoney(b.value, { withCurrency: false }),
    },
    {
      id: "status",
      header: t("stock.columns.status"),
      width: "210px",
      cell: (b) => {
        const days = expiryDays[b.product_id];
        return (
          <span className="flex flex-wrap gap-1.5">
            {b.is_negative || isNegative(b.qty) ? (
              <StatusChip tone="destructive" icon={TriangleAlert}>
                {t("stock.status.negative")}
              </StatusChip>
            ) : b.is_low ? (
              <StatusChip tone="destructive">{t("stock.status.low")}</StatusChip>
            ) : (
              <StatusChip tone="success">{t("stock.status.ok")}</StatusChip>
            )}
            {days !== undefined ? <ExpiryChip days={days} /> : null}
          </span>
        );
      },
    },
  ];

  return (
    <section className="flex flex-col gap-3" aria-label={t("tabs.balances")}>
      {lowCount > 0 || expiringCount > 0 ? (
        <Banner
          tone="warning"
          icon={TriangleAlert}
          action={
            <span className="flex flex-wrap gap-2">
              {lowCount > 0 ? (
                <Button size="sm" variant="secondary" onClick={() => onLow(true)}>
                  {t("stock.banner.showLow")}
                </Button>
              ) : null}
              {canCreatePo && lowCount > 0 ? (
                <Link to="/app/purchases?tab=orders&new=1" className={buttonVariants({ size: "sm" })}>
                  {t("stock.banner.createPo")}
                </Link>
              ) : null}
            </span>
          }
        >
          <span className="flex flex-col gap-0.5">
            {lowCount > 0 ? (
              <span className="font-bold">{t("stock.banner.low", { count: lowCount })}</span>
            ) : null}
            <span className="font-normal">
              {summary && summary.lowNames.length > 0
                ? t("stock.banner.lowNames", {
                    names: summary.lowNames.join(", "),
                    count: Math.max(0, lowCount - summary.lowNames.length),
                  })
                : null}{" "}
              {expiringCount > 0
                ? t("stock.banner.expiring", { count: expiringCount, days: EXPIRY_DAYS })
                : null}
            </span>
          </span>
        </Banner>
      ) : null}
      <div role="search" aria-label={t("stock.filters.label")} className="flex flex-wrap items-center gap-4">
        <SearchInput
          className="w-72"
          value={filters.search}
          onSearch={onSearch}
          maxLength={64}
          aria-label={t("stock.filters.search")}
          placeholder={t("stock.filters.searchPlaceholder")}
        />
        <span className="flex items-center gap-2">
          <Switch id="stock-low-only" checked={filters.lowOnly} onCheckedChange={onLow} />
          <Label htmlFor="stock-low-only">{t("stock.filters.lowOnly")}</Label>
        </span>
        <span className="flex items-center gap-2">
          <Switch
            id="stock-expiring"
            checked={view === "expiring"}
            onCheckedChange={(on) => onView(on ? "expiring" : "balances")}
          />
          <Label htmlFor="stock-expiring">{t("stock.filters.expiring", { days: EXPIRY_DAYS })}</Label>
        </span>
      </div>
      {view === "expiring" ? (
        <LotsTable canWriteOff={canWriteOff} online={online} onWriteOff={onWriteOffLot} />
      ) : (
        <>
          <DataTable
            label={t("stock.tableLabel")}
            columns={columns}
            data={rows}
            getRowId={(b) => b.product_id}
            status={status}
            errorMessage={error ? errorText(error) : undefined}
            onRetry={reload}
            minWidth={1000}
            empty={
              <EmptyState
                icon={PackageOpen}
                title={t(filters.search || filters.lowOnly ? "stock.empty.filtered" : "stock.empty.title")}
                description={filters.search || filters.lowOnly ? undefined : t("stock.empty.description")}
              />
            }
            pagination={{
              kind: "cursor",
              hasMore: cursor !== null,
              loadingMore: moreLoading,
              onLoadMore: more,
            }}
          />
          {rows.length > 0 ? (
            <div
              role="group"
              aria-label={t("stock.pageTotal")}
              className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border bg-muted px-4 py-3"
            >
              <span className="text-[14px] font-bold">{t("stock.pageTotal")}</span>
              <span className="text-small text-foreground-secondary">
                {t("stock.pageTotalHint", { count: rows.length })}
              </span>
              <span className="grow" />
              <span className="text-[16px] font-extrabold tabular-nums" data-testid="stock-page-total">
                {formatMoney(total)}
              </span>
            </div>
          ) : null}
          {updated ? (
            <p className="text-[12px] text-muted-foreground">
              {t("stock.lastUpdated", { at: formatDateTime(updated) })}
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}

function LotsTable({
  canWriteOff,
  online,
  onWriteOff,
}: {
  canWriteOff: boolean;
  online: boolean;
  onWriteOff: (lot: Lot) => void;
}) {
  const { t } = useTranslation("warehouse");
  const [lots, status, error, cursor, moreLoading, today, products] = useUnit([
    $lots,
    $lotsStatus,
    $lotsError,
    $lotsCursor,
    $lotsMoreLoading,
    $today,
    $products,
  ]);
  const [more, reload] = useUnit([lotsMoreRequested, reloadRequested]);
  const formatQty = useQtyFormat();
  const unitOf = (id: string) => products[id]?.unit_code;

  const columns: DataTableColumn<Lot>[] = [
    {
      id: "product",
      header: t("stock.columns.product"),
      cell: (l) => <span className="font-semibold">{l.product_name}</span>,
    },
    {
      id: "received",
      header: t("stock.lots.received"),
      width: "120px",
      cell: (l) => <span className="tabular-nums">{formatDate(l.received_at)}</span>,
    },
    {
      id: "expiry",
      header: t("stock.lots.expiry"),
      width: "120px",
      cell: (l) => (l.expiry_date ? <span className="tabular-nums">{formatDate(l.expiry_date)}</span> : "—"),
    },
    {
      id: "left",
      header: t("stock.lots.left"),
      numeric: true,
      width: "110px",
      cell: (l) => formatQty(l.qty_left, unitOf(l.product_id)),
    },
    {
      id: "cost",
      header: t("stock.lots.unitCost"),
      numeric: true,
      width: "130px",
      cell: (l) => formatMoney(l.unit_cost, { withCurrency: false }),
    },
    {
      id: "status",
      header: t("stock.columns.status"),
      width: "160px",
      cell: (l) => (l.expiry_date ? <ExpiryChip days={daysUntil(l.expiry_date, today)} /> : "—"),
    },
    ...(canWriteOff
      ? [
          {
            id: "action",
            header: t("stock.lots.action"),
            hideHeader: true,
            width: "190px",
            cell: (l: Lot) => (
              <Button
                size="sm"
                variant="secondary"
                disabled={!online}
                aria-label={t("stock.lots.writeOffFor", { name: l.product_name })}
                onClick={() => onWriteOff(l)}
              >
                <Icon as={Trash2} size="sm" />
                {t("actions.writeOff")}
              </Button>
            ),
          } satisfies DataTableColumn<Lot>,
        ]
      : []),
  ];

  return (
    <DataTable
      label={t("stock.lots.tableLabel")}
      columns={columns}
      data={lots}
      getRowId={(l) => l.id}
      status={status}
      errorMessage={error ? errorText(error) : undefined}
      onRetry={reload}
      minWidth={900}
      empty={<EmptyState icon={CalendarClock} title={t("stock.lots.empty", { days: EXPIRY_DAYS })} />}
      pagination={{ kind: "cursor", hasMore: cursor !== null, loadingMore: moreLoading, onLoadMore: more }}
    />
  );
}

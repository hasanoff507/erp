/**
 * POS-11 — Mahsulot va narxni tez qidirish (07, route /pos/lookup, F9; mockup Pos11Qidiruv.dc.html):
 * view only — no sale is created. Left: results (product, code, kind, stock, price) + count; offline →
 * yellow banner «narx va qoldiq oxirgi sinxron holatida» with the last update time. Right: the chosen
 * product card (price per unit, barcodes, code, VAT, marking note, this branch's stock and its time).
 * Scanner works here too. Esc → back to POS-02. Permission `stock.view` (cashier / storekeeper).
 */
import { useUnit } from "effector-react";
import { ArrowLeft, PackageSearch, ScanLine, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatMoney, formatPercent, formatQty } from "@shared/lib/format";
import { toDecimal } from "@shared/lib/money";
import { catalog, stock, type BarcodeRow, type ProductView, type StockRow } from "@shared/offline";
import { $syncState } from "@shared/state/sync";
import { Banner, Button, cn, EmptyState, Icon, Kbd, NoPermissionState } from "@shared/ui";

import { $posCashier, cashierCan } from "#/entities/pos-session/index.ts";
import { tashkentDateTime } from "#/shared/lib/dates.ts";
import { dyn } from "#/shared/lib/i18n-errors.ts";
import { useBarcodeWedge } from "#/shared/lib/use-barcode-wedge.ts";
import { hasPosHistory, posBackTarget } from "#/shared/lib/pos-history.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";

const kindOf = (p: ProductView) =>
  p.product.is_marked ? "marked" : p.product.is_weighed ? "weighed" : "piece";

function stockTotal(rows: readonly StockRow[]): string {
  return rows.reduce((acc, r) => acc.plus(toDecimal(r.qty ?? "0")), toDecimal("0")).toFixed(3);
}

function latest(rows: readonly StockRow[]): string | null {
  let best: string | null = null;
  for (const r of rows) {
    const at = typeof r.updated_at === "string" ? r.updated_at : null;
    if (at && (!best || at > best)) best = at;
  }
  return best;
}

function ProductCard({ view }: { view: ProductView }) {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const [rows, setRows] = useState<StockRow[]>([]);
  const [codes, setCodes] = useState<BarcodeRow[]>([]);
  useEffect(() => {
    void stock.forProduct(view.product.id).then(setRows);
    void catalog.barcodesOf(view.product.id).then(setCodes);
  }, [view.product.id]);
  const kind = kindOf(view);
  const qtyKind = view.product.is_weighed ? "fractional" : "integer";
  return (
    <section
      className="flex w-[420px] shrink-0 flex-col gap-3 rounded-2xl border border-border bg-card p-5 shadow-raised"
      data-testid="lookup-card"
    >
      <h2 className="text-[20px] font-extrabold">{view.product.name}</h2>
      {view.product.name_ru ? <p className="-mt-2 text-muted-foreground">{view.product.name_ru}</p> : null}
      <div className="rounded-xl bg-muted p-4">
        <div className="text-[13px] text-muted-foreground">{t("search.price")}</div>
        <div className="text-[32px] font-extrabold" data-testid="lookup-price">
          {view.price === null ? t("search.noPrice") : formatMoney(view.price)}
          {view.price !== null && view.product.is_weighed ? (
            <span className="text-[16px]"> / {view.product.unit_code}</span>
          ) : null}
        </div>
        <div className="text-[12px] text-muted-foreground">{t("search.priceReadOnly")}</div>
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[14px]">
        <dt className="text-muted-foreground">{t("search.barcode")}</dt>
        <dd className="font-mono">{codes.map((c) => c.barcode).join(", ") || "—"}</dd>
        <dt className="text-muted-foreground">{t("search.code")}</dt>
        <dd>{typeof view.product.code === "string" ? view.product.code : "—"}</dd>
        <dt className="text-muted-foreground">{t("search.vat")}</dt>
        <dd>
          {typeof view.product.vat_rate === "string"
            ? t("search.vatIncluded", { rate: formatPercent(view.product.vat_rate) })
            : t("search.vatExempt")}
        </dd>
        <dt className="text-muted-foreground">{t("search.stock")}</dt>
        <dd data-testid="lookup-stock">
          {formatQty(stockTotal(rows), qtyKind)} {view.product.unit_code}
          {latest(rows) ? (
            <span className="text-muted-foreground"> · {tashkentDateTime(latest(rows))}</span>
          ) : null}
        </dd>
      </dl>
      {kind === "marked" ? (
        <Banner tone="info" icon={ScanLine}>
          {t("search.markedNote")}
        </Banner>
      ) : null}
    </section>
  );
}

function LookupPage() {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const navigate = useNavigate();
  const [cashier, sync] = useUnit([$posCashier, $syncState]);
  const { pathname } = useLocation();
  // UX-09: back to where the user came from (POS-02 / warehouse hub)
  const goBack = () => {
    if (hasPosHistory(pathname)) void navigate(-1);
    else void navigate(posBackTarget(pathname, cashierCan(cashier, "sales.create")));
  };
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<ProductView[]>([]);
  const [stocks, setStocks] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<ProductView | null>(null);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const loading = loadedFor !== query;

  useEffect(() => {
    let alive = true;
    void catalog.search(query, { limit: 100 }).then(async (rows) => {
      if (!alive) return;
      setItems(rows);
      setLoadedFor(query);
      const entries = await Promise.all(
        rows.map(async (r) => [r.product.id, stockTotal(await stock.forProduct(r.product.id))] as const),
      );
      if (alive) setStocks(Object.fromEntries(entries));
    });
    return () => {
      alive = false;
    };
  }, [query]);

  useBarcodeWedge((code) => {
    void catalog.byBarcode(code).then((hit) => {
      setQuery("");
      if (hit) setSelected(hit);
    });
  });
  useHotkeys([{ key: "Escape", allowInInput: true, handler: () => goBack() }]);

  if (cashier && !cashierCan(cashier, "stock.view")) return <NoPermissionState />;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center gap-3">
        <Button size="pos" variant="secondary" onClick={() => goBack()}>
          <Icon as={ArrowLeft} size="lg" />
          {t("search.back")}
          <Kbd keys="Esc" />
        </Button>
        <h1 className="text-[22px] font-extrabold">{t("search.title")}</h1>
        <span className="text-[13px] text-muted-foreground">{t("search.viewOnly")}</span>
      </div>
      {!sync.online ? (
        <Banner tone="warning" icon={WifiOff}>
          {t("search.offline", { at: sync.lastPullAt ? tashkentDateTime(sync.lastPullAt) : "—" })}
        </Banner>
      ) : null}
      <div className="flex min-h-0 flex-1 gap-3">
        <section className="flex min-w-0 flex-1 flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-raised">
          <label className="flex h-14 items-center gap-3 rounded-xl border-2 border-primary px-4">
            <Icon as={ScanLine} size="xl" className="text-primary" />
            <input
              autoFocus
              data-testid="lookup-query"
              aria-label={t("search.query")}
              placeholder={t("search.placeholder")}
              maxLength={64}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="h-full flex-1 bg-transparent text-[17px] font-semibold outline-none"
            />
          </label>
          <p className="text-[13px] text-muted-foreground">{t("search.count", { n: items.length })}</p>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {!loading && items.length === 0 ? (
              <EmptyState icon={PackageSearch} title={t("search.empty")} />
            ) : (
              <table className="w-full text-[14px]">
                <thead className="sticky top-0 bg-card text-left text-[12px] text-muted-foreground">
                  <tr>
                    <th className="py-2">{t("search.colProduct")}</th>
                    <th>{t("search.colCode")}</th>
                    <th>{t("search.colKind")}</th>
                    <th className="text-right">{t("search.colStock")}</th>
                    <th className="text-right">{t("search.colPrice")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((p) => (
                    <tr
                      key={p.product.id}
                      data-testid="lookup-row"
                      onClick={() => setSelected(p)}
                      className={cn(
                        "h-12 cursor-pointer border-t border-border",
                        selected?.product.id === p.product.id && "bg-primary-soft",
                      )}
                    >
                      <td className="font-bold">{p.product.name}</td>
                      <td>{typeof p.product.code === "string" ? p.product.code : ""}</td>
                      <td>{t(`sale.kind.${kindOf(p)}`)}</td>
                      <td className="text-right">
                        {stocks[p.product.id]
                          ? formatQty(
                              stocks[p.product.id] ?? "0",
                              p.product.is_weighed ? "fractional" : "integer",
                            )
                          : "—"}
                      </td>
                      <td className="text-right font-extrabold">
                        {p.price === null ? "—" : formatMoney(p.price, { withCurrency: false })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
        {selected ? <ProductCard view={selected} /> : null}
      </div>
    </div>
  );
}

export const Lookup = { route: "lookup", titleKey: "pos:search.title", Page: LookupPage } as const;

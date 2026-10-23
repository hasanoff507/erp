/**
 * POS-02 left column (07 POS-02, 24 §5.1): BarcodeField (F1 — scanner always active), «Kartochka / Ro'yxat»
 * switch (device setting `pos.catalog_view`), category tabs («Hammasi» + categories that have products) and a
 * virtualized product grid / list (@tanstack/react-virtual). Prices are shown read-only (US-M09-03).
 */
import { useVirtualizer } from "@tanstack/react-virtual";
import { useUnit } from "effector-react";
import { ScanLine } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent, type RefObject } from "react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { catalog, pullApplied, type ProductView } from "@shared/offline";
import { cn, Icon, Kbd, SegmentedControl } from "@shared/ui";

import {
  $catalogView,
  $categories,
  $categoryId,
  catalogViewChanged,
  categoryChanged,
  type CatalogView,
} from "../model/context.ts";
import { codeScanned, kindOf, productPicked } from "../model/scan.ts";

const TILE_MIN = 168;

function useProducts(query: string, categoryId: string | null) {
  const [items, setItems] = useState<ProductView[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [tick, setTick] = useState(0);
  useEffect(() => pullApplied.watch(() => setTick((n) => n + 1)), []);
  useEffect(() => {
    let alive = true;
    void catalog
      .search(query, { categoryId, limit: 1000 })
      .then((rows) => {
        if (!alive) return;
        setItems(rows);
        setLoaded(true);
      })
      .catch(() => alive && setLoaded(true));
    return () => {
      alive = false;
    };
  }, [query, categoryId, tick]);
  return { items, loaded };
}

function useWidth(ref: RefObject<HTMLDivElement | null>): number {
  const [width, setWidth] = useState(800);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(([entry]) => entry && setWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return width;
}

function KindChip({ view }: { view: ProductView }) {
  const { t } = useTranslation("pos");
  const kind = kindOf(view);
  return (
    <span
      className={cn(
        "rounded-md px-1.5 py-0.5 text-[11px] font-bold",
        kind === "piece" && "bg-muted text-foreground-secondary",
        kind === "weighed" && "bg-info-soft text-info-strong",
        kind === "marked" && "bg-primary-soft text-primary-strong",
      )}
    >
      {t(`sale.kind.${kind}`)}
    </span>
  );
}

function priceText(view: ProductView, perUnit: string): string {
  if (view.price === null) return "—";
  const money = formatMoney(view.price, { withCurrency: false });
  return view.product.is_weighed ? `${money} / ${perUnit}` : money;
}

export interface ProductPanelProps {
  disabled: boolean;
  inputRef: RefObject<HTMLInputElement | null>;
}

export function ProductPanel({ disabled, inputRef }: ProductPanelProps) {
  const { t } = useTranslation("pos");
  const [view, categories, categoryId, setView, setCategory, scan, pick] = useUnit([
    $catalogView,
    $categories,
    $categoryId,
    catalogViewChanged,
    categoryChanged,
    codeScanned,
    productPicked,
  ]);
  const [query, setQuery] = useState("");
  // a scanner burst also lands in the focused field — clear it once the scan is taken
  useEffect(() => codeScanned.watch(() => setQuery("")), []);
  const { items, loaded } = useProducts(query, categoryId);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const width = useWidth(scrollRef);
  const cols = view === "grid" ? Math.max(2, Math.floor(width / TILE_MIN)) : 1;
  const rows = Math.ceil(items.length / cols);
  // eslint-disable-next-line react-hooks/incompatible-library -- @tanstack/react-virtual (24 §5.1) returns non-memoizable functions
  const virtualizer = useVirtualizer({
    count: rows,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => (view === "grid" ? 132 : 60),
    overscan: 4,
  });

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== "Enter" || e.defaultPrevented) return;
    e.preventDefault();
    const text = query.trim();
    if (!text) return;
    const exact = items.length === 1 ? items[0] : undefined;
    if (exact) productPicked(exact);
    else scan(text);
    setQuery("");
  };

  const pickOne = (p: ProductView) => {
    if (disabled) return;
    pick(p);
    inputRef.current?.focus();
  };

  const tabs = [{ id: null as string | null, name: t("sale.allCategories") }, ...categories];

  return (
    <section className="flex min-h-0 flex-1 flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-raised">
      <div className="flex items-center gap-3">
        <label className="flex h-14 min-w-0 flex-1 items-center gap-3 rounded-xl border-2 border-primary bg-background px-4">
          <Icon as={ScanLine} size="xl" className="text-primary" />
          <input
            ref={inputRef}
            data-testid="barcode-field"
            aria-label={t("sale.barcodeLabel")}
            placeholder={t("sale.barcodePlaceholder")}
            maxLength={64}
            autoComplete="off"
            value={query}
            disabled={disabled}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            className="h-full min-w-0 flex-1 bg-transparent text-[17px] font-semibold outline-none"
          />
          <Kbd keys="F1" />
        </label>
        <SegmentedControl<CatalogView>
          label={t("sale.viewLabel")}
          density="touch"
          value={view}
          onChange={setView}
          options={[
            { value: "grid", label: t("sale.viewGrid") },
            { value: "list", label: t("sale.viewList") },
          ]}
        />
      </div>

      <div role="tablist" aria-label={t("sale.categoriesLabel")} className="flex gap-2 overflow-x-auto pb-1">
        {tabs.map((c) => {
          const selected = c.id === categoryId;
          return (
            <button
              key={c.id ?? "all"}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => {
                setCategory(c.id);
                inputRef.current?.focus();
              }}
              className={cn(
                "h-12 shrink-0 rounded-xl border px-4 text-[14px] font-bold",
                selected ? "border-foreground bg-foreground text-background" : "border-border bg-card",
              )}
            >
              {c.name}
            </button>
          );
        })}
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto" data-testid="product-panel">
        {loaded && items.length === 0 ? (
          <p className="py-10 text-center text-muted-foreground">{t("sale.noProducts")}</p>
        ) : (
          <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
            {virtualizer.getVirtualItems().map((row) => (
              <div
                key={row.key}
                className={cn("absolute inset-x-0 grid gap-3 pb-3")}
                style={{
                  transform: `translateY(${row.start}px)`,
                  gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
                }}
              >
                {items.slice(row.index * cols, row.index * cols + cols).map((p) =>
                  view === "grid" ? (
                    <button
                      key={p.product.id}
                      type="button"
                      disabled={disabled}
                      onClick={() => pickOne(p)}
                      data-testid="product-tile"
                      className="flex h-[120px] flex-col items-start gap-1 rounded-xl border border-border bg-background p-3 text-left hover:border-primary disabled:opacity-60"
                    >
                      <div className="flex w-full items-center justify-between">
                        <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary-soft text-[13px] font-extrabold text-primary-strong">
                          {p.product.name.slice(0, 2).toUpperCase()}
                        </span>
                        <KindChip view={p} />
                      </div>
                      <span className="line-clamp-2 text-[14px] font-bold leading-tight">
                        {p.product.name}
                      </span>
                      <span className="mt-auto text-[16px] font-extrabold">
                        {priceText(p, p.product.unit_code)}
                      </span>
                    </button>
                  ) : (
                    <button
                      key={p.product.id}
                      type="button"
                      disabled={disabled}
                      onClick={() => pickOne(p)}
                      data-testid="product-row"
                      className="flex h-12 items-center gap-3 rounded-lg border border-border bg-background px-3 text-left hover:border-primary disabled:opacity-60"
                    >
                      <span className="min-w-0 flex-1 truncate text-[14px] font-bold">{p.product.name}</span>
                      <KindChip view={p} />
                      <span className="w-32 text-right text-[15px] font-extrabold">
                        {priceText(p, p.product.unit_code)}
                      </span>
                    </button>
                  ),
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

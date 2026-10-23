/**
 * «Qo'lda kiritish» — local catalog search (offline, `catalog.search`, 24 §5.1) for products without a readable
 * barcode. F2 focuses it; ↑/↓ + Enter pick a result without the mouse.
 */
import { Search } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { useTranslation } from "@shared/i18n";
import { catalog, type ProductView } from "@shared/offline";
import { Icon, Input, cn } from "@shared/ui";

export interface ProductSearchProps {
  onPick: (product: ProductView) => void;
  placeholder: string;
  inputRef?: React.RefObject<HTMLInputElement | null>;
  search?: (query: string) => Promise<ProductView[]>;
}

export function ProductSearch({ onPick, placeholder, inputRef, search }: ProductSearchProps) {
  const { i18n } = useTranslation("pos");
  const own = useRef<HTMLInputElement | null>(null);
  const ref = inputRef ?? own;
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<{ query: string; items: ProductView[] }>({ query: "", items: [] });
  const [active, setActive] = useState(0);
  const q = query.trim();
  // results of an older query are never shown (async search)
  const items = q.length >= 2 && found.query === q ? found.items : [];

  useEffect(() => {
    let alive = true;
    if (q.length < 2) return undefined;
    (search ?? ((s: string) => catalog.search(s, { limit: 8 })))(q)
      .then((rows) => {
        if (alive) {
          setFound({ query: q, items: rows.slice(0, 8) });
          setActive(0);
        }
      })
      .catch(() => {
        if (alive) setFound({ query: q, items: [] });
      });
    return () => {
      alive = false;
    };
  }, [q, search]);

  const pick = (p: ProductView | undefined) => {
    if (!p) return;
    onPick(p);
    setQuery("");
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      pick(items[active]);
    }
  };
  const nameOf = (p: ProductView) =>
    i18n.language === "ru" && p.product.name_ru ? p.product.name_ru : p.product.name;

  return (
    <div className="relative">
      <Icon
        as={Search}
        size="md"
        className="pointer-events-none absolute left-3 top-[26px] -translate-y-1/2 text-muted-foreground"
      />
      <Input
        ref={ref}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        aria-label={placeholder}
        className="h-[52px] pl-11 text-[15px]"
        maxLength={100}
        autoComplete="off"
      />
      {items.length > 0 ? (
        <ul
          role="listbox"
          className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-border bg-card shadow-raised"
        >
          {items.map((p, i) => (
            <li key={p.product.id} role="option" aria-selected={i === active}>
              <button
                type="button"
                className={cn(
                  "flex min-h-12 w-full items-center justify-between gap-3 px-4 text-left text-[15px]",
                  i === active ? "bg-primary-soft" : "hover:bg-accent",
                )}
                onClick={() => pick(p)}
              >
                <span className="truncate font-semibold">{nameOf(p)}</span>
                <span className="text-[13px] text-muted-foreground">{p.product.unit_code}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

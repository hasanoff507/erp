/**
 * `Ctrl+K` / `Cmd+K` palette (06 §1.9, 08 §9 — cmdk via @shared/ui `CommandDialog`): screens the user
 * may open, products and counterparties from the server search. ↑ / ↓ move, Enter opens, Esc closes.
 * The topbar search field is its trigger. Results are navigation only — nothing is changed here.
 */
import { useUnit } from "effector-react";
import { Boxes, CornerDownLeft, Search, Users, type LucideIcon } from "lucide-react";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatPhone } from "@shared/lib/format";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandLoading,
  Icon,
  Kbd,
} from "@shared/ui";

import {
  $open,
  $query,
  $results,
  $searchError,
  $searching,
  counterpartyHref,
  filterScreens,
  paletteClosed,
  paletteOpened,
  productHref,
  queryChanged,
  searchable,
  type PaletteRights,
} from "../model/index.ts";

export interface PaletteScreen {
  key: string;
  label: string;
  to: string;
  icon: LucideIcon;
  /** Extra words to match (e.g. the group name). */
  keywords?: string;
}

export function PaletteTrigger({ rights }: { rights: PaletteRights }) {
  const { t } = useTranslation();
  const open = useUnit(paletteOpened);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        open(rights);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, rights]);

  return (
    <button
      type="button"
      onClick={() => open(rights)}
      aria-label={t("topbar.searchLabel")}
      aria-keyshortcuts="Control+K Meta+K"
      className="hidden h-[42px] min-w-[240px] items-center gap-2 rounded-lg border border-input bg-muted px-3 text-left text-[14px] text-muted-foreground hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:flex"
    >
      <Icon as={Search} size="md" className="shrink-0" />
      <span className="min-w-0 flex-1 truncate">{t("topbar.searchPlaceholder")}</span>
      <Kbd keys="Ctrl K" />
    </button>
  );
}

export function CommandPalette({ screens }: { screens: readonly PaletteScreen[] }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [open, query, results, searching, error, close, onQuery] = useUnit([
    $open,
    $query,
    $results,
    $searching,
    $searchError,
    paletteClosed,
    queryChanged,
  ]);
  const shownScreens = filterScreens(screens, query);
  const go = (to: string) => {
    close();
    void navigate(to);
  };
  const serverQuery = searchable(query) !== null;

  return (
    <CommandDialog
      open={open}
      onOpenChange={(next) => (next ? undefined : close())}
      title={t("topbar.palette.title")}
      description={t("topbar.palette.hint")}
      commandProps={{ shouldFilter: false, loop: true }}
    >
      <CommandInput
        value={query}
        onValueChange={onQuery}
        placeholder={t("topbar.searchPlaceholder")}
        maxLength={64}
      />
      <CommandList>
        {searching ? <CommandLoading>{t("topbar.palette.searching")}</CommandLoading> : null}
        {error ? (
          <p className="px-3 py-2 text-small text-destructive-strong">{t("topbar.palette.error")}</p>
        ) : null}
        <CommandEmpty>{serverQuery ? t("topbar.palette.empty") : t("topbar.palette.typeMore")}</CommandEmpty>
        {shownScreens.length > 0 ? (
          <CommandGroup heading={t("topbar.palette.screens")}>
            {shownScreens.map((s) => (
              <CommandItem key={`screen-${s.key}`} value={`screen-${s.key}`} onSelect={() => go(s.to)}>
                <Icon as={s.icon} size="md" className="text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate">{s.label}</span>
                <Icon as={CornerDownLeft} size="sm" className="text-muted-foreground" />
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}
        {results.products.length > 0 ? (
          <CommandGroup heading={t("topbar.palette.products")}>
            {results.products.map((p) => (
              <CommandItem
                key={`product-${p.id}`}
                value={`product-${p.id}`}
                onSelect={() => go(productHref(p.id))}
              >
                <Icon as={Boxes} size="md" className="text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate">{p.name}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}
        {results.counterparties.length > 0 ? (
          <CommandGroup heading={t("topbar.palette.counterparties")}>
            {results.counterparties.map((c) => (
              <CommandItem
                key={`cp-${c.id}`}
                value={`cp-${c.id}`}
                onSelect={() => go(counterpartyHref(c.id))}
              >
                <Icon as={Users} size="md" className="text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate">{c.name}</span>
                {c.phone ? (
                  <span className="text-[12px] text-muted-foreground">{formatPhone(c.phone)}</span>
                ) : null}
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}
      </CommandList>
    </CommandDialog>
  );
}

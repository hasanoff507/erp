/**
 * Remote search picker (product / supplier): a button opens a popover with a debounced SearchInput
 * and the results; picking one calls `onPick` and closes. Results come from a `createSearch` model.
 */
import { useUnit } from "effector-react";
import { LoaderCircle } from "lucide-react";
import { useState, type ReactNode } from "react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import {
  Button,
  Icon,
  Popover,
  PopoverContent,
  PopoverTrigger,
  SearchInput,
  type LucideIcon,
} from "@shared/ui";

import type { SearchModel } from "../lib/search.ts";

export interface SearchPickerProps<T> {
  model: SearchModel<T>;
  /** Trigger text (button) — the chosen value or an action («Tovar qo'shish»). */
  trigger: ReactNode;
  triggerIcon?: LucideIcon;
  /** Accessible name of the trigger when its text is the chosen value. */
  triggerLabel?: string;
  searchLabel: string;
  placeholder?: string;
  getKey: (item: T) => string;
  renderItem: (item: T) => { title: string; meta?: string };
  onPick: (item: T) => void;
  disabled?: boolean;
  variant?: "secondary" | "outline" | "dashed";
  className?: string;
  id?: string;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
}

export function SearchPicker<T>({
  model,
  trigger,
  triggerIcon,
  triggerLabel,
  searchLabel,
  placeholder,
  getKey,
  renderItem,
  onPick,
  disabled,
  variant = "secondary",
  className,
  id,
  ...aria
}: SearchPickerProps<T>) {
  const { t } = useTranslation("warehouse");
  const [open, setOpen] = useState(false);
  const [query, results, pending, error, search, reset] = useUnit([
    model.$query,
    model.$results,
    model.searchFx.pending,
    model.$error,
    model.queryChanged,
    model.reset,
  ]);

  const toggle = (next: boolean) => {
    setOpen(next);
    if (!next) reset();
  };

  return (
    <Popover open={open} onOpenChange={toggle}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant={variant}
          disabled={disabled}
          aria-label={triggerLabel}
          className={className}
          {...aria}
        >
          {triggerIcon ? <Icon as={triggerIcon} size="sm" /> : null}
          {trigger}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(92vw,420px)] p-3">
        <div className="flex flex-col gap-2">
          <SearchInput
            value={query}
            onSearch={search}
            aria-label={searchLabel}
            placeholder={placeholder}
            autoFocus
          />
          {pending ? (
            <p
              role="status"
              className="flex items-center gap-2 px-1 py-3 text-small text-foreground-secondary"
            >
              <Icon as={LoaderCircle} size="sm" className="animate-spin" />
              {t("picker.searching")}
            </p>
          ) : error ? (
            <p role="alert" className="px-1 py-3 text-small font-semibold text-destructive">
              {serverErrorText(error)}
            </p>
          ) : query === "" ? (
            <p className="px-1 py-3 text-small text-muted-foreground">{t("picker.typeToSearch")}</p>
          ) : results.length === 0 ? (
            <p className="px-1 py-3 text-small text-muted-foreground">{t("picker.noResults")}</p>
          ) : (
            <ul className="flex max-h-72 flex-col overflow-y-auto" aria-label={t("picker.results")}>
              {results.map((item) => {
                const view = renderItem(item);
                return (
                  <li key={getKey(item)}>
                    <button
                      type="button"
                      onClick={() => {
                        onPick(item);
                        toggle(false);
                      }}
                      className="flex w-full flex-col items-start gap-0.5 rounded-md px-2.5 py-2 text-left hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <span className="text-[13px] font-semibold">{view.title}</span>
                      {view.meta ? (
                        <span className="text-[12px] tabular-nums text-muted-foreground">{view.meta}</span>
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

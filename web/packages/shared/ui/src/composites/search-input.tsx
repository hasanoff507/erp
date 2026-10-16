/**
 * SearchInput — debounced list search (catalog, MXIK, staff). Typing updates the field immediately;
 * `onSearch` fires `delay` ms after the last keystroke (default 300), immediately on Enter, and with
 * "" on Esc / clear. Leading/trailing spaces are trimmed before `onSearch`. `minLength` suppresses
 * searches shorter than N characters (an empty query is always sent, it resets the list).
 */
import { Search, X } from "lucide-react";
import { useEffect, useRef, useState, type InputHTMLAttributes, type Ref } from "react";

import { useTranslation } from "@shared/i18n";

import { inputClassName } from "#/components/ui/input.tsx";
import { Icon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

export interface SearchInputProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "value" | "onChange" | "type" | "defaultValue"
> {
  /** Initial / externally reset query. */
  value?: string;
  onSearch: (query: string) => void;
  delay?: number;
  minLength?: number;
  ref?: Ref<HTMLInputElement>;
}

export function SearchInput({
  value = "",
  onSearch,
  delay = 300,
  minLength = 0,
  className,
  placeholder,
  ref,
  "aria-label": ariaLabel,
  onKeyDown,
  ...props
}: SearchInputProps) {
  const { t } = useTranslation("common");
  const [text, setText] = useState(value);
  const [synced, setSynced] = useState(value);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSent = useRef(value.trim());
  const onSearchRef = useRef(onSearch);

  useEffect(() => {
    onSearchRef.current = onSearch;
  }, [onSearch]);

  if (value !== synced) {
    setSynced(value);
    setText(value);
  }

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const send = (raw: string) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    const q = raw.trim();
    if (q !== "" && q.length < minLength) return;
    if (q === lastSent.current) return;
    lastSent.current = q;
    onSearchRef.current(q);
  };

  const schedule = (raw: string) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => send(raw), delay);
  };

  return (
    <div className={cn("relative flex w-full", className)}>
      <Icon
        as={Search}
        size="md"
        className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground"
      />
      <input
        ref={ref}
        type="search"
        autoComplete="off"
        aria-label={ariaLabel ?? t("ui.search.label")}
        placeholder={placeholder}
        className={cn(inputClassName, "pl-10 pr-10 [&::-webkit-search-cancel-button]:hidden")}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          schedule(e.target.value);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            send(text);
          } else if (e.key === "Escape" && text !== "") {
            e.preventDefault();
            setText("");
            send("");
          }
          onKeyDown?.(e);
        }}
        {...props}
      />
      {text !== "" ? (
        <button
          type="button"
          aria-label={t("ui.search.clear")}
          onClick={() => {
            setText("");
            send("");
          }}
          className="absolute right-1 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Icon as={X} size="sm" />
        </button>
      ) : null}
    </div>
  );
}

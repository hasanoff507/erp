/**
 * CheckboxList + MultiSelect — roles / branches pickers (BO-11 "Rol(lar)", "Filial(lar)").
 * CheckboxList: <fieldset><legend> + one checkbox row (≥40px, whole row clickable) per option,
 * optional "Hammasi" row (indeterminate when partially selected). MultiSelect: a Select-looking
 * trigger ("2 ta tanlandi" / the single label) that opens the same list in a Popover.
 * Values are option ids (`string[]`), order follows `options`.
 */
import { ChevronDown } from "lucide-react";
import { useId, type Ref } from "react";

import { useTranslation } from "@shared/i18n";

import { Checkbox } from "#/components/ui/checkbox.tsx";
import { Popover, PopoverContent, PopoverTrigger } from "#/components/ui/popover.tsx";
import { Icon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

export interface CheckboxOption {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
}

export interface CheckboxListProps {
  options: readonly CheckboxOption[];
  value: readonly string[];
  onChange: (value: string[]) => void;
  /** Group label (rendered as <legend>; `hideLegend` keeps it for screen readers only). */
  legend: string;
  hideLegend?: boolean;
  /** Adds a "Hammasi" row. */
  selectAll?: boolean;
  disabled?: boolean;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
  className?: string;
}

function ordered(options: readonly CheckboxOption[], set: Set<string>): string[] {
  return options.filter((o) => set.has(o.value)).map((o) => o.value);
}

export function CheckboxList({
  options,
  value,
  onChange,
  legend,
  hideLegend = false,
  selectAll = false,
  disabled = false,
  className,
  ...aria
}: CheckboxListProps) {
  const { t } = useTranslation("common");
  const base = useId();
  const selected = new Set(value);
  const enabled = options.filter((o) => !o.disabled);
  const allChecked = enabled.length > 0 && enabled.every((o) => selected.has(o.value));
  const someChecked = enabled.some((o) => selected.has(o.value));

  const toggle = (v: string, checked: boolean) => {
    const next = new Set(selected);
    if (checked) next.add(v);
    else next.delete(v);
    onChange(ordered(options, next));
  };

  const rowClass =
    "flex min-h-10 cursor-pointer items-center gap-3 rounded-md px-2.5 py-2 hover:bg-accent has-[button:disabled]:cursor-not-allowed has-[button:disabled]:opacity-60";

  return (
    <fieldset
      className={cn("m-0 flex min-w-0 flex-col gap-0.5 border-0 p-0", className)}
      disabled={disabled}
      aria-invalid={aria["aria-invalid"]}
      aria-describedby={aria["aria-describedby"]}
    >
      <legend className={cn("mb-1 p-0 text-label text-foreground-secondary", hideLegend && "sr-only")}>
        {legend}
      </legend>
      {selectAll ? (
        <label htmlFor={`${base}-all`} className={cn(rowClass, "border-b border-divider")}>
          <Checkbox
            id={`${base}-all`}
            checked={allChecked ? true : someChecked ? "indeterminate" : false}
            onCheckedChange={(c) => {
              const next = new Set(selected);
              for (const o of enabled) {
                if (c === true) next.add(o.value);
                else next.delete(o.value);
              }
              onChange(ordered(options, next));
            }}
          />
          <span className="text-[14px] font-bold">{t("ui.multiSelect.all")}</span>
        </label>
      ) : null}
      {options.map((o, i) => (
        <label key={o.value} htmlFor={`${base}-${i}`} className={rowClass}>
          <Checkbox
            id={`${base}-${i}`}
            checked={selected.has(o.value)}
            disabled={o.disabled}
            onCheckedChange={(c) => toggle(o.value, c === true)}
          />
          <span className="flex min-w-0 flex-col">
            <span className="text-[14px] font-semibold text-foreground">{o.label}</span>
            {o.description ? (
              <span className="text-[12px] text-muted-foreground">{o.description}</span>
            ) : null}
          </span>
        </label>
      ))}
    </fieldset>
  );
}

export interface MultiSelectProps extends Omit<CheckboxListProps, "hideLegend" | "className"> {
  id?: string;
  placeholder?: string;
  className?: string;
  ref?: Ref<HTMLButtonElement>;
}

export function MultiSelect({
  options,
  value,
  onChange,
  legend,
  selectAll,
  disabled,
  id,
  placeholder,
  className,
  ref,
  ...aria
}: MultiSelectProps) {
  const { t } = useTranslation("common");
  const labels = options.filter((o) => value.includes(o.value)).map((o) => o.label);
  const summary =
    labels.length === 0
      ? (placeholder ?? t("ui.select.placeholder"))
      : labels.length <= 2
        ? labels.join(", ")
        : t("ui.multiSelect.selected", { count: labels.length });
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          ref={ref}
          id={id}
          type="button"
          disabled={disabled}
          aria-invalid={aria["aria-invalid"]}
          aria-describedby={aria["aria-describedby"]}
          className={cn(
            "flex h-11 w-full min-w-0 items-center justify-between gap-2 rounded-lg border border-input bg-card px-3.5 text-left text-[15px]",
            "focus-visible:border-primary focus-visible:shadow-focus-soft focus-visible:outline-none aria-[invalid=true]:border-destructive",
            "disabled:cursor-not-allowed disabled:text-disabled-foreground",
            labels.length === 0 ? "text-muted-foreground" : "text-foreground",
            className,
          )}
        >
          <span className="truncate">{summary}</span>
          <Icon as={ChevronDown} size="sm" className="shrink-0 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] min-w-56 max-h-80 overflow-y-auto p-1.5">
        <CheckboxList
          options={options}
          value={value}
          onChange={onChange}
          legend={legend}
          hideLegend
          selectAll={selectAll}
        />
      </PopoverContent>
    </Popover>
  );
}

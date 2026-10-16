/**
 * MXIK (IKPU) code input + classifier search (19 §1 "MXIK qidiruv/tekshirish", 21 §7).
 * Search is debounced (SearchInput, ≥ 3 chars) and may take up to ~15 s while tasnif.soliq.uz is
 * slow — a loading state is shown. A complete 17-digit code is verified on blur:
 * found / not found (404) / could not verify (`stale_cache`, outage) — never blocking (19 §1).
 */
import { BadgeCheck, CircleAlert, LoaderCircle, Search } from "lucide-react";
import { useUnit } from "effector-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import type { MxikItem, MxikLookupOut } from "@shared/models";
import {
  Button,
  Icon,
  Input,
  Popover,
  PopoverContent,
  PopoverTrigger,
  SearchInput,
  type FieldControlProps,
} from "@shared/ui";

import { isMxikFormat } from "#/entities/product/index.ts";
import { apiErrorText } from "#/shared/lib/messages.ts";

import {
  $mxikError,
  $mxikQuery,
  $mxikResults,
  lookupMxikFx,
  MXIK_MIN_QUERY,
  mxikQueryChanged,
  searchMxikFx,
} from "../../model/index.ts";

type Verify =
  | { state: "idle" }
  | { state: "checking" }
  | { state: "found"; name: string }
  | { state: "notFound" }
  | { state: "unverified" };

export interface MxikFieldProps {
  control: FieldControlProps;
  value: string;
  onChange: (code: string) => void;
  onBlur: () => void;
  /** Classifier VAT hint ("12.00" / "0.00") of a picked code. */
  onVatHint: (vat: string) => void;
  disabled?: boolean;
}

function verifyOf(result: MxikLookupOut, code: string): Verify {
  const hit = result.items.find((i) => i.code === code) ?? result.items[0];
  if (hit) return { state: "found", name: hit.name };
  return result.source === "stale_cache" ? { state: "unverified" } : { state: "notFound" };
}

export function MxikField({ control, value, onChange, onBlur, onVatHint, disabled }: MxikFieldProps) {
  const { t } = useTranslation("catalog");
  const [open, setOpen] = useState(false);
  const [verify, setVerify] = useState<Verify>({ state: "idle" });
  const [query, results, searching, error, search, lookup] = useUnit([
    $mxikQuery,
    $mxikResults,
    searchMxikFx.pending,
    $mxikError,
    mxikQueryChanged,
    lookupMxikFx,
  ]);

  const check = (code: string) => {
    if (!isMxikFormat(code)) {
      setVerify({ state: "idle" });
      return;
    }
    setVerify({ state: "checking" });
    lookup(code)
      .then((res) => setVerify(verifyOf(res, code)))
      .catch((e: unknown) => {
        const status = (e as { status?: number | null }).status;
        setVerify(status === 404 ? { state: "notFound" } : { state: "unverified" });
      });
  };

  const pick = (item: MxikItem) => {
    onChange(item.code);
    setVerify({ state: "found", name: item.name });
    if (item.vat_hint === "12.00" || item.vat_hint === "0.00") onVatHint(item.vat_hint);
    setOpen(false);
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex gap-2">
        <Input
          {...control}
          value={value}
          inputMode="numeric"
          autoComplete="off"
          maxLength={17}
          placeholder="00000000000000000"
          disabled={disabled}
          className="font-semibold tabular-nums"
          onChange={(e) => {
            const digits = e.target.value.replace(/\D/g, "").slice(0, 17);
            onChange(digits);
            if (verify.state !== "idle") setVerify({ state: "idle" });
          }}
          onBlur={() => {
            onBlur();
            check(value);
          }}
        />
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button type="button" variant="secondary" disabled={disabled}>
              <Icon as={Search} size="sm" />
              {t("products.mxik.search")}
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-[min(92vw,440px)] p-3">
            <div className="flex flex-col gap-2">
              <SearchInput
                value={query}
                onSearch={search}
                minLength={MXIK_MIN_QUERY}
                delay={400}
                aria-label={t("products.mxik.searchLabel")}
                placeholder={t("products.mxik.searchPlaceholder")}
                autoFocus
              />
              <MxikResults
                query={query}
                results={results}
                searching={searching}
                error={error ? apiErrorText(error) : null}
                onPick={pick}
              />
            </div>
          </PopoverContent>
        </Popover>
      </div>
      <VerifyLine verify={verify} />
    </div>
  );
}

function MxikResults({
  query,
  results,
  searching,
  error,
  onPick,
}: {
  query: string;
  results: readonly MxikItem[];
  searching: boolean;
  error: string | null;
  onPick: (item: MxikItem) => void;
}) {
  const { t } = useTranslation("catalog");
  if (searching) {
    return (
      <p role="status" className="flex items-center gap-2 px-1 py-3 text-small text-foreground-secondary">
        <Icon as={LoaderCircle} size="sm" className="animate-spin" />
        {t("products.mxik.searching")}
      </p>
    );
  }
  if (error) {
    return (
      <p role="alert" className="px-1 py-3 text-small font-semibold text-destructive">
        {error}
      </p>
    );
  }
  if (query.length < MXIK_MIN_QUERY) {
    return <p className="px-1 py-3 text-small text-muted-foreground">{t("products.mxik.minQuery")}</p>;
  }
  if (results.length === 0) {
    return <p className="px-1 py-3 text-small text-muted-foreground">{t("products.mxik.noResults")}</p>;
  }
  return (
    <ul className="flex max-h-72 flex-col overflow-y-auto" aria-label={t("products.mxik.results")}>
      {results.map((item) => (
        <li key={item.code}>
          <button
            type="button"
            onClick={() => onPick(item)}
            className="flex w-full flex-col items-start gap-0.5 rounded-md px-2.5 py-2 text-left hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="text-[13px] font-semibold">{item.name}</span>
            <span className="text-[12px] tabular-nums text-muted-foreground">
              {item.code}
              {item.vat_hint
                ? ` · ${t("products.mxik.vatHint", { rate: item.vat_hint.replace(".00", "") })}`
                : ""}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function VerifyLine({ verify }: { verify: Verify }) {
  const { t } = useTranslation("catalog");
  switch (verify.state) {
    case "checking":
      return (
        <p role="status" className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
          <Icon as={LoaderCircle} size="sm" className="animate-spin" />
          {t("products.mxik.checking")}
        </p>
      );
    case "found":
      return (
        <p className="flex items-center gap-1.5 text-[12px] font-semibold text-success-strong">
          <Icon as={BadgeCheck} size="sm" />
          {verify.name}
        </p>
      );
    case "notFound":
      return (
        <p className="flex items-center gap-1.5 text-[12px] font-semibold text-warning-strong">
          <Icon as={CircleAlert} size="sm" />
          {t("products.mxik.notFound")}
        </p>
      );
    case "unverified":
      return (
        <p className="flex items-center gap-1.5 text-[12px] font-semibold text-warning-strong">
          <Icon as={CircleAlert} size="sm" />
          {t("products.mxik.unverified")}
        </p>
      );
    default:
      return null;
  }
}

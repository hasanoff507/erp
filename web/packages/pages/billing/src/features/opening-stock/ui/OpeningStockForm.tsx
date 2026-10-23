/**
 * BO-21 ③b «Qo'lda» — opening stock lines (07 `openingStockMethod`, 19 §16): find a product, enter
 * qty, unit cost (tannarx, 4 dp) and an optional expiry date, «Qoldiqni saqlash» posts one
 * stock-opening document to the default branch warehouse. useEffect only fires `formOpened` (24 §2).
 */
import { useUnit } from "effector-react";
import { CircleCheck, Plus, Trash2, TriangleAlert, Warehouse } from "lucide-react";
import { useEffect } from "react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { dayjs } from "@shared/lib/date";
import { formatMoney } from "@shared/lib/format";
import { Banner, Button, DecimalInput, FormField, Icon, Input, PriceInput, SearchInput } from "@shared/ui";

import {
  $canSubmit,
  $lines,
  $posted,
  $problems,
  $results,
  $search,
  $submitError,
  $submitting,
  $warehouse,
  $warehouseError,
  formOpened,
  formReset,
  lineChanged,
  lineRemoved,
  productPicked,
  searchChanged,
  submitted,
  toOpeningProduct,
} from "../model/index.ts";

export function OpeningStockForm({ online }: { online: boolean }) {
  const { t } = useTranslation("onboarding");
  const [lines, problems, results, search, warehouse, warehouseError, submitError, posted, canSubmit, busy] =
    useUnit([
      $lines,
      $problems,
      $results,
      $search,
      $warehouse,
      $warehouseError,
      $submitError,
      $posted,
      $canSubmit,
      $submitting,
    ]);
  const [opened, onSearch, pick, change, remove, submit, reset] = useUnit([
    formOpened,
    searchChanged,
    productPicked,
    lineChanged,
    lineRemoved,
    submitted,
    formReset,
  ]);

  useEffect(() => {
    opened({ today: dayjs().format("YYYY-MM-DD") });
  }, [opened]);

  if (posted && lines.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <Banner tone="success" icon={CircleCheck} live="polite">
          {t("openingStock.manual.posted", {
            number: posted.number ?? "—",
            count: posted.line_count,
            amount: formatMoney(posted.total_amount),
          })}
        </Banner>
        <div>
          <Button variant="secondary" onClick={() => reset()}>
            <Icon as={Plus} size="sm" />
            {t("openingStock.manual.again")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {warehouse ? (
        <p className="flex items-center gap-1.5 text-small text-foreground-secondary">
          <Icon as={Warehouse} size="sm" />
          {t("openingStock.manual.warehouse", { name: warehouse.name })}
        </p>
      ) : null}
      {warehouseError ? (
        <Banner tone="destructive" icon={TriangleAlert}>
          {serverErrorText(warehouseError)}
        </Banner>
      ) : null}

      <FormField label={t("openingStock.manual.search")} hint={t("openingStock.manual.searchHint")}>
        {(a11y) => (
          <SearchInput
            {...a11y}
            aria-label={t("openingStock.manual.search")}
            value={search}
            onSearch={onSearch}
            placeholder={t("openingStock.manual.searchPlaceholder")}
            disabled={!online}
          />
        )}
      </FormField>
      {results.length > 0 ? (
        <ul
          aria-label={t("openingStock.manual.results")}
          className="flex flex-col divide-y divide-divider rounded-lg border border-border"
        >
          {results.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => pick(toOpeningProduct(p))}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-[14px] hover:bg-accent focus-visible:bg-accent focus-visible:outline-none"
              >
                <Icon as={Plus} size="sm" className="text-primary" />
                <span className="min-w-0 flex-1 truncate font-semibold">{p.name}</span>
                <span className="text-[12px] text-muted-foreground">
                  {p.barcodes[0]?.barcode ?? p.unit_code}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : search.trim().length >= 2 ? (
        <p className="text-small text-muted-foreground">{t("openingStock.manual.noResults")}</p>
      ) : null}

      {lines.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table
            className="w-full min-w-[640px] text-[14px]"
            aria-label={t("openingStock.manual.tableLabel")}
          >
            <thead className="bg-muted text-caption text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-bold">{t("openingStock.manual.columns.product")}</th>
                <th className="w-32 px-3 py-2 text-right font-bold">
                  {t("openingStock.manual.columns.qty")}
                </th>
                <th className="w-40 px-3 py-2 text-right font-bold">
                  {t("openingStock.manual.columns.unitCost")}
                </th>
                <th className="w-40 px-3 py-2 text-left font-bold">
                  {t("openingStock.manual.columns.expiry")}
                </th>
                <th className="w-12 px-2 py-2">
                  <span className="sr-only">{t("openingStock.manual.columns.remove")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line) => {
                const problem = problems[line.key] ?? null;
                return (
                  <tr key={line.key} className="border-t border-divider align-top">
                    <td className="px-3 py-2 font-semibold">{line.product.name}</td>
                    <td className="px-3 py-2">
                      <DecimalInput
                        aria-label={t("openingStock.manual.qtyFor", { name: line.product.name })}
                        precision={3}
                        outputScale={3}
                        value={line.qty}
                        onChange={(qty) => change({ key: line.key, patch: { qty } })}
                        aria-invalid={(problem === "qty" && line.qty !== "") || undefined}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <PriceInput
                        aria-label={t("openingStock.manual.costFor", { name: line.product.name })}
                        withCurrency={false}
                        value={line.unitCost}
                        onChange={(unitCost) => change({ key: line.key, patch: { unitCost } })}
                        aria-invalid={(problem === "unitCost" && line.unitCost !== "") || undefined}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <Input
                        type="date"
                        aria-label={t("openingStock.manual.expiryFor", { name: line.product.name })}
                        value={line.expiryDate}
                        onChange={(e) => change({ key: line.key, patch: { expiryDate: e.target.value } })}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={t("openingStock.manual.removeFor", { name: line.product.name })}
                        onClick={() => remove(line.key)}
                      >
                        <Icon as={Trash2} size="sm" />
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-small text-muted-foreground">{t("openingStock.manual.empty")}</p>
      )}

      {submitError ? (
        <Banner tone="destructive" icon={TriangleAlert} live="assertive">
          {serverErrorText(submitError)}
        </Banner>
      ) : null}

      <div className="flex flex-wrap items-center justify-end gap-3">
        <p className="text-small text-foreground-secondary">{t("openingStock.manual.costHint")}</p>
        <Button
          variant="secondary"
          onClick={() => submit()}
          disabled={!online || !canSubmit}
          aria-busy={busy || undefined}
        >
          {t("openingStock.manual.save", { count: lines.length })}
        </Button>
      </div>
    </div>
  );
}

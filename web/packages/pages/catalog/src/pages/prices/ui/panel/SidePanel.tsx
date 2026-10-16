/**
 * BO-05 right panel: «Narx tarixi» of the selected product (`GET /products/{id}/prices`: price,
 * change, date / who — `set_by_name`), its `nameRu` (qaror #29, PATCH /products — `catalog.manage`, applies at once)
 * and the «Doimiy mijoz chegirmasi» block (read-only list from customer cards — M08/BO-06, a later
 * phase: shown as "keyingi bosqich").
 */
import { History, Users } from "lucide-react";
import { useUnit } from "effector-react";
import { useState } from "react";

import type { ApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney, formatPercent } from "@shared/lib/format";
import { $user } from "@shared/state/session";
import {
  Button,
  Card,
  CardTitle,
  EmptyState,
  ErrorState,
  FormField,
  Icon,
  Input,
  Skeleton,
  StatusChip,
  toast,
} from "@shared/ui";

import { changePct, priceAuthorOf, type PriceAuthor } from "#/entities/product/index.ts";
import { apiErrorText } from "#/shared/lib/messages.ts";

import {
  $history,
  $historyCursor,
  $historyError,
  $selectedProduct,
  historyMoreRequested,
  loadHistoryFx,
  productSelected,
  saveNameRuFx,
  type PriceHistoryItem,
  type ProductOut,
} from "../../model/index.ts";

export function SidePanel({ canManageCatalog, online }: { canManageCatalog: boolean; online: boolean }) {
  const product = useUnit($selectedProduct);
  return (
    <aside className="flex min-w-0 flex-[1_1_320px] flex-col gap-3.5">
      <HistoryCard product={product} />
      {product ? (
        <NameRuCard
          key={`${product.id}:${product.version}`}
          product={product}
          editable={canManageCatalog && online}
        />
      ) : null}
      <StandingDiscountCard />
    </aside>
  );
}

function HistoryCard({ product }: { product: ProductOut | null }) {
  const { t } = useTranslation("catalog");
  const [items, cursor, error, loading, more, retry, user] = useUnit([
    $history,
    $historyCursor,
    $historyError,
    loadHistoryFx.pending,
    historyMoreRequested,
    productSelected,
    $user,
  ]);
  const [now] = useState(() => Date.now());

  return (
    <Card className="flex flex-col gap-3">
      <div>
        <CardTitle>{t("prices.history.title")}</CardTitle>
        {product ? (
          <p className="truncate text-small text-foreground-secondary">
            {product.name}
            {product.barcodes[0] ? ` · ${product.barcodes[0].barcode}` : ""}
          </p>
        ) : null}
      </div>
      {!product ? (
        <EmptyState icon={History} title={t("prices.history.pick")} className="py-6" />
      ) : error ? (
        <ErrorState message={apiErrorText(error)} onRetry={() => retry(product.id)} className="py-6" />
      ) : loading && items.length === 0 ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : items.length === 0 ? (
        <EmptyState icon={History} title={t("prices.history.empty")} className="py-6" />
      ) : (
        <ol className="flex flex-col divide-y divide-divider" aria-label={t("prices.history.title")}>
          {items.map((item, i) => (
            <HistoryRow
              key={`${item.valid_from}-${item.price_change_doc_id ?? i}`}
              item={item}
              previous={items[i + 1] ?? null}
              future={new Date(item.valid_from).getTime() > now}
              current={
                new Date(item.valid_from).getTime() <= now &&
                (item.valid_to === null || new Date(item.valid_to).getTime() > now)
              }
              author={priceAuthorOf(item, user?.id ?? null)}
            />
          ))}
        </ol>
      )}
      {cursor ? (
        <Button variant="secondary" size="sm" onClick={() => more()} disabled={loading}>
          {t("prices.history.more")}
        </Button>
      ) : null}
    </Card>
  );
}

function HistoryRow({
  item,
  previous,
  future,
  current,
  author,
}: {
  item: PriceHistoryItem;
  previous: PriceHistoryItem | null;
  future: boolean;
  current: boolean;
  author: PriceAuthor;
}) {
  const { t } = useTranslation("catalog");
  const pct = changePct(previous?.price ?? null, item.price);
  const period = item.valid_to
    ? t("prices.history.period", { from: formatDate(item.valid_from), to: formatDate(item.valid_to) })
    : t("prices.history.since", { from: formatDate(item.valid_from) });
  // «kim o'rnatdi» — 19 §4 `set_by_name`; no author (`set_by` null: system/import/legacy row) → «tizim».
  const who =
    author.kind === "user"
      ? author.name
      : author.kind === "you"
        ? t("prices.history.byYou")
        : author.kind === "staff"
          ? t("prices.history.byStaff")
          : t("prices.history.bySystem");
  return (
    <li className="flex flex-col gap-0.5 py-2.5">
      <span className="flex items-center gap-2">
        <span className="font-extrabold tabular-nums">{formatMoney(item.price)}</span>
        {pct ? (
          <span className="text-small font-semibold text-foreground-secondary">
            {pct.startsWith("-") ? "" : "+"}
            {formatPercent(pct)}
          </span>
        ) : null}
        <span className="grow" />
        {future ? <StatusChip tone="info">{t("prices.history.future")}</StatusChip> : null}
        {current ? <StatusChip tone="success">{t("prices.history.current")}</StatusChip> : null}
        {item.branch_id ? <StatusChip tone="neutral">{t("prices.history.branch")}</StatusChip> : null}
      </span>
      <span className="text-[12px] text-muted-foreground">
        {period} · {who}
      </span>
    </li>
  );
}

function NameRuCard({ product, editable }: { product: ProductOut; editable: boolean }) {
  const { t } = useTranslation("catalog");
  const [save, saving] = useUnit([saveNameRuFx, saveNameRuFx.pending]);
  const [value, setValue] = useState(product.name_ru ?? "");
  const [error, setError] = useState<string | null>(null);
  const dirty = value.trim() !== (product.name_ru ?? "");

  return (
    <Card className="flex flex-col gap-3">
      <FormField label={t("prices.nameRu.label")} hint={t("prices.nameRu.hint")} error={error} optional>
        <Input
          value={value}
          maxLength={255}
          lang="ru"
          disabled={!editable}
          onChange={(e) => {
            setValue(e.target.value);
            setError(null);
          }}
        />
      </FormField>
      {editable ? (
        <div className="flex justify-end">
          <Button
            size="sm"
            variant="secondary"
            disabled={!dirty || saving}
            onClick={() => {
              save({ product, nameRu: value })
                .then(() => toast.success(t("prices.nameRu.saved")))
                .catch((e: ApiError) => setError(apiErrorText(e)));
            }}
          >
            {t("prices.nameRu.save")}
          </Button>
        </div>
      ) : null}
    </Card>
  );
}

function StandingDiscountCard() {
  const { t } = useTranslation("catalog");
  return (
    <Card className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <CardTitle>{t("prices.standingDiscount.title")}</CardTitle>
        <StatusChip tone="neutral">{t("common.nextPhase")}</StatusChip>
      </div>
      <p className="flex items-start gap-2 text-small text-foreground-secondary">
        <Icon as={Users} size="sm" className="mt-0.5 shrink-0" />
        {t("prices.standingDiscount.body")}
      </p>
    </Card>
  );
}

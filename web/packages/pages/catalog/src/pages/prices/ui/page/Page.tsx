/**
 * BO-05 — Narxlar (07, route /app/catalog/prices). MVP layout of 07: filters (category, search,
 * effectiveFrom), over-limit banner, «Chakana narxlar» table with editable new prices, footer
 * «N ta o'zgarish · {sana} dan amal qiladi», «Bekor qilish» / «Saqlash» (Ctrl+S), right panel with
 * price history and nameRu. The «Chegirma qoidalari» tab is not shown in the MVP (07, qaror #33).
 *
 * Permissions: `prices.edit` edits prices; without `prices.approve` a change > 10% goes to the
 * Owner's approval (BO-16); `catalog.manage` edits nameRu. Offline: view only (07 Holatlar).
 */
import { CircleCheck, Hourglass, TriangleAlert, WifiOff } from "lucide-react";
import { useUnit } from "effector-react";
import { useEffect, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney, formatPercent } from "@shared/lib/format";
import { $isOnline } from "@shared/state/network";
import { useCan } from "@shared/state/permissions";
import { $activeBranch } from "@shared/state/session";
import { Banner, Button, ConfirmDialog, FormField, Input, Kbd, SearchInput, SimpleSelect } from "@shared/ui";

import { $categories, isPositiveAmount } from "#/entities/product/index.ts";
import { apiErrorText } from "#/shared/lib/messages.ts";

import {
  $changes,
  $drafts,
  $effectiveFrom,
  $filters,
  $saveError,
  $saveResult,
  $scope,
  ALL_BRANCHES_SCOPE,
  approvalLimitOf,
  categoryChanged,
  draftsReset,
  effectiveFromChanged,
  pageMounted,
  resultDismissed,
  savePricesFx,
  saveRequested,
  scopeChanged,
  searchChanged,
  todayIso,
} from "../../model/index.ts";
import { SidePanel } from "../panel/SidePanel.tsx";
import { PriceTable } from "../table/PriceTable.tsx";

const ALL = "all";

function PricesPage() {
  const { t } = useTranslation("catalog");
  const mounted = useUnit(pageMounted);
  useEffect(() => {
    mounted();
  }, [mounted]);

  const canEdit = useCan({ permission: "prices.edit" });
  const canApprove = useCan({ permission: "prices.approve" });
  const canManageCatalog = useCan({ permission: "catalog.manage" });
  const online = useUnit($isOnline);
  const editable = canEdit && online;
  // GET /auth/session has no `limit_value` — a `prices.approve` holder's own limit is unknown (advisory).
  const approvalLimit = approvalLimitOf(canApprove);
  const save = useUnit(saveRequested);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      if (editable) save();
    }
  };

  return (
    <div className="flex flex-col gap-[18px]" onKeyDown={onKeyDown}>
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="min-w-0">
          <p className="text-small text-foreground-secondary">{t("prices.subtitle")}</p>
        </div>
        <div className="grow" />
        <nav aria-label={t("nav.label")} className="flex flex-wrap gap-2">
          <Button variant="secondary" asChild>
            <Link to="/app/catalog/products">{t("nav.products")}</Link>
          </Button>
          {canManageCatalog ? (
            <Button variant="secondary" asChild>
              <Link to="/app/catalog/products/import">{t("nav.import")}</Link>
            </Button>
          ) : null}
        </nav>
      </div>

      {online ? null : (
        <Banner tone="warning" icon={WifiOff}>
          {t("prices.offline")}
        </Banner>
      )}
      {!canEdit ? (
        <Banner tone="info" icon={TriangleAlert}>
          {t("prices.readOnly")}
        </Banner>
      ) : null}

      <Filters />
      <ResultBanner />
      <LimitBanner canApprove={canApprove} />

      <div className="flex flex-wrap items-start gap-3.5">
        <div className="flex min-w-0 flex-[2_1_620px] flex-col gap-3">
          <PriceTable editable={editable} approvalLimit={approvalLimit} />
          {editable ? <SaveBar /> : null}
        </div>
        <SidePanel canManageCatalog={canManageCatalog} online={online} />
      </div>
    </div>
  );
}

function Filters() {
  const { t } = useTranslation("catalog");
  const [filters, categories, effectiveFrom, scope, branch, drafts] = useUnit([
    $filters,
    $categories,
    $effectiveFrom,
    $scope,
    $activeBranch,
    $drafts,
  ]);
  // Changing the scope drops the drafts (the base price changes) — confirm when there are unsaved edits.
  const [pendingScope, setPendingScope] = useState<string | null>(null);
  const requestScope = (next: string) => {
    if (next === scope) return;
    if (Object.keys(drafts).length > 0) setPendingScope(next);
    else onScope(next);
  };
  const [onSearch, onCategory, onDate, onScope] = useUnit([
    searchChanged,
    categoryChanged,
    effectiveFromChanged,
    scopeChanged,
  ]);
  const today = todayIso();

  return (
    <div className="flex flex-wrap items-end gap-3">
      <FormField label={t("prices.filters.category")} className="w-56">
        <SimpleSelect
          options={[
            { value: ALL, label: t("products.filters.allCategories") },
            ...categories.map((c) => ({ value: c.id, label: c.name })),
          ]}
          value={filters.categoryId ?? ALL}
          onValueChange={(v) => onCategory(v === ALL ? null : v)}
        />
      </FormField>
      <FormField label={t("prices.filters.search")} className="max-w-md flex-[1_1_260px]">
        {(a11y) => (
          <SearchInput
            {...a11y}
            value={filters.search}
            onSearch={onSearch}
            placeholder={t("prices.filters.searchPlaceholder")}
          />
        )}
      </FormField>
      <FormField label={t("prices.filters.effectiveFrom")} className="w-44">
        <Input
          type="date"
          min={today}
          value={effectiveFrom}
          onChange={(e) => {
            const v = e.target.value;
            if (v !== "" && v >= today) onDate(v);
          }}
        />
      </FormField>
      {branch ? (
        <FormField label={t("prices.filters.scope")} className="w-56">
          <SimpleSelect
            options={[
              { value: ALL_BRANCHES_SCOPE, label: t("prices.scope.all") },
              { value: branch.id, label: t("prices.scope.branch", { name: branch.name }) },
            ]}
            value={scope}
            onValueChange={requestScope}
          />
        </FormField>
      ) : null}
      <ConfirmDialog
        open={pendingScope !== null}
        onOpenChange={(open) => {
          if (!open) setPendingScope(null);
        }}
        title={t("prices.scopeConfirm.title")}
        description={t("prices.scopeConfirm.description", { count: Object.keys(drafts).length })}
        confirmLabel={t("prices.scopeConfirm.confirm")}
        tone="destructive"
        onConfirm={() => {
          if (pendingScope !== null) onScope(pendingScope);
          setPendingScope(null);
        }}
      />
    </div>
  );
}

/** 07 BO-05: «N ta o'zgarish 10% dan katta — Egasi tasdig'i kerak» (tovar, eski → yangi, foiz; → BO-16). */
function LimitBanner({ canApprove }: { canApprove: boolean }) {
  const { t } = useTranslation("catalog");
  const changes = useUnit($changes);
  if (canApprove) return null;
  const over = changes.filter((c) => c.overLimit);
  if (over.length === 0) return null;
  return (
    <Banner
      tone="awaiting-approval"
      icon={Hourglass}
      action={
        <Button variant="secondary" size="sm" asChild>
          <Link to="/app/approvals">{t("prices.approvalQueue")}</Link>
        </Button>
      }
    >
      <p>{t("prices.limit.title", { count: over.length })}</p>
      <ul className="mt-1 font-normal">
        {over.map((c) => (
          <li key={c.product.id}>
            {t("prices.limit.line", {
              name: c.product.name,
              from: c.oldPrice ? formatMoney(c.oldPrice) : "—",
              to: formatMoney(c.newPrice),
              pct: `${c.pct?.startsWith("-") ? "" : "+"}${formatPercent(c.pct ?? "0")}`,
            })}
          </li>
        ))}
      </ul>
      <p className="mt-1 font-normal">{t("prices.limit.note")}</p>
    </Banner>
  );
}

function ResultBanner() {
  const { t } = useTranslation("catalog");
  const [result, error, dismiss] = useUnit([$saveResult, $saveError, resultDismissed]);
  if (error) {
    return (
      <Banner tone="destructive" icon={TriangleAlert} live="assertive">
        {apiErrorText(error)}
      </Banner>
    );
  }
  if (!result) return null;
  if (result.status === "pending_approval") {
    return (
      <Banner
        tone="awaiting-approval"
        icon={Hourglass}
        live="assertive"
        action={
          <Button variant="secondary" size="sm" onClick={() => dismiss()}>
            {t("prices.result.dismiss")}
          </Button>
        }
      >
        {t("prices.result.pending", { count: result.lines.length })}
      </Banner>
    );
  }
  return (
    <Banner
      tone="success"
      icon={CircleCheck}
      action={
        <Button variant="secondary" size="sm" onClick={() => dismiss()}>
          {t("prices.result.dismiss")}
        </Button>
      }
    >
      {t("prices.result.posted", { count: result.lines.length })}
    </Banner>
  );
}

function SaveBar() {
  const { t } = useTranslation("catalog");
  const [changes, effectiveFrom, saving, save, reset] = useUnit([
    $changes,
    $effectiveFrom,
    savePricesFx.pending,
    saveRequested,
    draftsReset,
  ]);
  const invalid = changes.some((c) => !isPositiveAmount(c.newPrice));
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
      <p className="text-small text-foreground-secondary" aria-live="polite">
        {t("prices.footer", { count: changes.length, date: formatDate(effectiveFrom) })}
      </p>
      <div className="grow" />
      <Button variant="secondary" onClick={() => reset()} disabled={changes.length === 0 || saving}>
        {t("prices.cancel")}
      </Button>
      <Button
        onClick={() => save()}
        disabled={changes.length === 0 || saving || invalid}
        aria-busy={saving || undefined}
        aria-keyshortcuts="Control+S"
      >
        {t("prices.save")}
        <Kbd keys="Ctrl+S" inverted className="ml-1" />
      </Button>
    </div>
  );
}

export const Prices = {
  route: "catalog/prices",
  titleKey: "catalog:title",
  Page: PricesPage,
} as const;

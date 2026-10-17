/**
 * POS-10 — Inventarizatsiya (07 POS-10, maket Pos10Inventar.dc.html; route /pos/warehouse/stocktake).
 * Left: header, scanner / «Qo'lda kiritish», error banner, filter tabs, the lines table. Right: progress and
 * counters, the «Joriy tovar» card (−/+, «Qatorni saqlash» Enter), offline note, «Sanashni yakunlash».
 * Hotkeys: F1 scanner, F2 manual search, Enter save line, F9 finish, Esc back.
 */
import { useUnit } from "effector-react";
import { AlertTriangle, ClipboardList, PackageSearch, WifiOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatDate } from "@shared/lib/date";
import { $isOnline } from "@shared/state/network";
import {
  Banner,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Kbd,
  NoPermissionState,
  StatusChip,
  Tabs,
  TabsList,
  TabsTrigger,
  cn,
} from "@shared/ui";

import { usePosPermission } from "#/entities/pos-session/index.ts";
import {
  ProductSearch,
  QtyStepper,
  ScanField,
  WhScreen,
  subtractQty,
  trimQty,
} from "#/features/wh-scan/index.ts";
import { errorText } from "#/shared/lib/i18n-errors.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";

import {
  $count,
  $counts,
  $current,
  $error,
  $filter,
  $loaded,
  $progress,
  $rows,
  $submitted,
  $submitting,
  $unknownCodes,
  $visibleRows,
  $warehouse,
  countSelected,
  currentQtyChanged,
  currentSaved,
  errorDismissed,
  filterChanged,
  finishConfirmed,
  productPicked,
  scanned,
  startRequested,
  stockCountOpened,
  type CountError,
  type CountFilter,
  type CountRow,
} from "../../model/index.ts";

const WAREHOUSE_HUB = "/pos/warehouse";

function diffTone(diff: string | null): "success" | "warning" | "destructive" | "neutral" {
  if (diff === null) return "neutral";
  const sign = diff.startsWith("-") ? -1 : /^0(\.0+)?$/.test(diff) ? 0 : 1;
  return sign === 0 ? "success" : sign < 0 ? "destructive" : "warning";
}

function useErrorText(error: CountError | null): string | null {
  const { t } = useTranslation("pos");
  if (!error) return null;
  switch (error.kind) {
    case "unknown_barcode":
      return t("stockCount.unknownBarcode", { code: error.code });
    case "check_digit":
      return t("stockCount.checkDigit", { code: error.code });
    case "no_price":
      return t("stockCount.noPrice", { code: error.code });
    case "no_actor":
      return t("wh.noActor");
    case "not_synced":
      return t("stockCount.notSynced");
    default:
      return errorText(error.code, error.params ?? {});
  }
}

function StockCountPage() {
  const { t } = useTranslation("pos");
  const navigate = useNavigate();
  const canCount = usePosPermission("stock.count.create");
  const [online, loaded, warehouse, counts, count, rows, visible, filter, progress, current, error, submitting,
    submitted, unknownCodes] = useUnit([
    $isOnline, $loaded, $warehouse, $counts, $count, $rows, $visibleRows, $filter, $progress, $current, $error,
    $submitting, $submitted, $unknownCodes,
  ]); // prettier-ignore
  const scanRef = useRef<HTMLInputElement | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const [confirm, setConfirm] = useState(false);
  const errorMessage = useErrorText(error);

  useEffect(() => {
    if (canCount) stockCountOpened();
  }, [canCount]);

  useHotkeys([
    { key: "F1", handler: () => scanRef.current?.focus() },
    { key: "F2", handler: () => searchRef.current?.focus() },
    { key: "F9", handler: () => count && online && setConfirm(true) },
    { key: "Enter", handler: () => current?.dirty && currentSaved() },
    {
      key: "Escape",
      allowInInput: true,
      handler: () => (confirm ? setConfirm(false) : navigate(WAREHOUSE_HUB)),
    },
  ]);

  if (!canCount) return <NoPermissionState />;

  const back = () => navigate(WAREHOUSE_HUB);
  const subtitle = count
    ? t("stockCount.subtitle", { warehouse: warehouse?.name ?? "", date: formatDate(count.doc_date) })
    : (warehouse?.name ?? undefined);
  const tabs: { value: CountFilter; label: string }[] = [
    { value: "all", label: t("stockCount.tabs.all") },
    { value: "diff", label: t("stockCount.tabs.diff", { count: progress.diff }) },
    { value: "uncounted", label: t("stockCount.tabs.uncounted", { count: progress.left }) },
    { value: "match", label: t("stockCount.tabs.match") },
  ];

  return (
    <WhScreen
      title={t("stockCount.title")}
      subtitle={subtitle}
      onBack={back}
      testId="pos-stock-count"
      actions={
        count ? (
          <Button
            size="pos"
            onClick={() => setConfirm(true)}
            disabled={!online || submitting}
            title={online ? undefined : t("stockCount.finishOffline")}
            data-testid="count-finish"
          >
            {t("stockCount.finish")}
            <Kbd keys="F9" inverted />
          </Button>
        ) : null
      }
    >
      {submitted ? (
        <Banner tone="success" icon={ClipboardList} className="mb-3">
          {t("stockCount.submitted", { number: submitted.number ?? t("stockCount.draftNumber") })}
        </Banner>
      ) : null}
      {!online ? (
        <Banner tone="warning" icon={WifiOff} className="mb-3">
          {t("wh.offlineNote")}
        </Banner>
      ) : null}
      {errorMessage ? (
        <Banner
          tone={error?.kind === "unknown_barcode" ? "warning" : "destructive"}
          icon={AlertTriangle}
          className="mb-3"
          action={
            <Button size="sm" variant="ghost" onClick={() => errorDismissed()}>
              ✕
            </Button>
          }
        >
          <span data-testid="count-error">{errorMessage}</span>
          {error?.kind === "unknown_barcode" ? (
            <span className="block text-[12px] font-normal">{t("stockCount.unknownNote")}</span>
          ) : null}
        </Banner>
      ) : null}

      {!count ? (
        <Card className="p-4">
          {loaded && !warehouse ? (
            <EmptyState icon={PackageSearch} title={t("wh.noWarehouse")} />
          ) : counts.length > 0 ? (
            <div className="flex flex-col gap-2">
              <h2 className="text-[15px] font-bold">{t("stockCount.pick")}</h2>
              {counts.map((c) => (
                <Button
                  key={c.id}
                  variant="secondary"
                  size="pos"
                  className="justify-start"
                  onClick={() => countSelected(c.id)}
                >
                  {t("stockCount.pickRow", {
                    number: c.number ?? t("stockCount.draftNumber"),
                    date: formatDate(c.doc_date),
                    counted: c.counted_count,
                    total: c.line_count,
                  })}
                </Button>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={ClipboardList}
              title={t("stockCount.empty")}
              description={online ? t("stockCount.emptyHint") : t("stockCount.startOffline")}
              action={
                <Button size="pos" onClick={() => startRequested()} disabled={!online || !warehouse}>
                  {t("stockCount.start")}
                </Button>
              }
            />
          )}
        </Card>
      ) : (
        <div className="grid min-h-0 gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="flex min-w-0 flex-col gap-3">
            <ScanField onScan={(code) => scanned(code)} inputRef={scanRef} />
            <ProductSearch
              inputRef={searchRef}
              placeholder={`${t("stockCount.manual")} — ${t("stockCount.searchPlaceholder")}`}
              onPick={(p) =>
                productPicked({
                  productId: p.product.id,
                  name: p.product.name,
                  isMarked: p.product.is_marked === true,
                })
              }
            />
            <Tabs value={filter} onValueChange={(v) => filterChanged(v as CountFilter)}>
              <TabsList>
                {tabs.map((tab) => (
                  <TabsTrigger key={tab.value} value={tab.value} className="h-11 px-4">
                    {tab.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            <CountTable rows={visible} />
            {unknownCodes.length > 0 ? (
              <Card className="p-3">
                <h3 className="text-[13px] font-bold">{t("stockCount.unknownList")}</h3>
                <ul className="text-[13px]">
                  {unknownCodes.map((u) => (
                    <li key={u.code} className="flex justify-between">
                      <span className="font-mono">{u.code}</span>
                      <span>{trimQty(u.counted)}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : null}
          </div>
          <aside className="flex flex-col gap-3">
            <Card className="p-4">
              <p className="text-[15px] font-bold" data-testid="count-progress">
                {t("stockCount.progress", { counted: progress.counted, total: rows.length })}
              </p>
              <div className="mt-2 grid grid-cols-3 gap-2 text-center text-[13px]">
                <Counter
                  label={t("stockCount.shortage")}
                  value={progress.shortage}
                  tone="text-destructive-strong"
                />
                <Counter
                  label={t("stockCount.surplus")}
                  value={progress.surplus}
                  tone="text-warning-strong"
                />
                <Counter label={t("stockCount.left")} value={progress.left} tone="text-foreground" />
              </div>
            </Card>
            <Card className="p-4" data-testid="count-current">
              <h2 className="text-[13px] font-bold uppercase text-muted-foreground">
                {t("stockCount.current")}
              </h2>
              {current ? (
                <div className="mt-2 flex flex-col gap-2">
                  <p className="text-[17px] font-extrabold">{current.name}</p>
                  {current.isMarked ? <StatusChip tone="info">{t("stockCount.marked")}</StatusChip> : null}
                  {current.code ? (
                    <p className="font-mono text-[13px] text-muted-foreground">{current.code}</p>
                  ) : null}
                  <p className="text-[14px]">
                    {t("stockCount.systemQty")}: <b>{trimQty(current.expected)}</b>
                  </p>
                  <QtyStepper
                    value={current.counted}
                    label={t("stockCount.countedQty")}
                    onChange={(v) => currentQtyChanged(v)}
                    testId="count-current-qty"
                  />
                  <p className="text-[14px]">
                    {t("stockCount.diffQty")}:{" "}
                    <b>{trimQty(subtractQty(current.counted || "0", current.expected))}</b>
                  </p>
                  <Button size="pos" onClick={() => currentSaved()} disabled={!current.dirty}>
                    {current.dirty ? t("stockCount.saveLine") : t("stockCount.lineSaved")}
                    <Kbd keys="Enter" inverted={current.dirty} />
                  </Button>
                </div>
              ) : (
                <p className="mt-2 text-[14px] text-muted-foreground">{t("stockCount.currentEmpty")}</p>
              )}
            </Card>
          </aside>
        </div>
      )}

      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={t("stockCount.finishTitle")}
        description={t("stockCount.finishBody", { left: progress.left })}
        confirmLabel={t("stockCount.finish")}
        pending={submitting}
        onConfirm={() => {
          setConfirm(false);
          finishConfirmed();
        }}
      />
    </WhScreen>
  );
}

function Counter({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="rounded-lg bg-accent p-2">
      <div className={cn("text-[20px] font-extrabold", tone)}>{value}</div>
      <div className="text-muted-foreground">{label}</div>
    </div>
  );
}

function CountTable({ rows }: { rows: readonly CountRow[] }) {
  const { t } = useTranslation("pos");
  if (rows.length === 0) {
    return <p className="p-4 text-center text-[14px] text-muted-foreground">{t("stockCount.empty_rows")}</p>;
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-[14px]" data-testid="count-table">
        <thead className="bg-accent text-left text-[12px] uppercase text-muted-foreground">
          <tr>
            <th className="px-3 py-2">{t("stockCount.cols.product")}</th>
            <th className="px-3 py-2 text-right">{t("stockCount.cols.system")}</th>
            <th className="px-3 py-2 text-right">{t("stockCount.cols.counted")}</th>
            <th className="px-3 py-2 text-right">{t("stockCount.cols.diff")}</th>
            <th className="px-3 py-2">{t("stockCount.cols.sync")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.productId} className="border-t border-border" data-testid="count-row">
              <td className="px-3 py-2 font-semibold">{r.name}</td>
              <td className="px-3 py-2 text-right tabular-nums">{trimQty(r.expected)}</td>
              <td className="px-3 py-2 text-right tabular-nums">
                {r.counted === null ? "—" : trimQty(r.counted)}
              </td>
              <td className="px-3 py-2 text-right">
                {r.diff === null ? "—" : <StatusChip tone={diffTone(r.diff)}>{trimQty(r.diff)}</StatusChip>}
              </td>
              <td className="px-3 py-2 text-[12px] text-muted-foreground">
                {r.sync ? t(`wh.sync.${r.sync}` as "wh.sync.pending") : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const StockCount = {
  route: "warehouse/stocktake",
  titleKey: "pos:stockCount.title",
  Page: StockCountPage,
} as const;

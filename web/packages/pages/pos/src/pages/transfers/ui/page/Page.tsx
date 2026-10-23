/**
 * POS-09 — Omborlar orasida ko'chirish (07 POS-09, maket Pos09Kochirish.dc.html; route /pos/warehouse/transfer).
 * «Yuborish» tab: left — source/destination, scanner (F1), lines (source balance, −/+, marking count, short
 * warning), totals; right — transport block and «O'tkazish» (online) / «Yuborish» (F9, offline too).
 * «Qabul qilish» tab: incoming `sent` transfers (cached for offline), received qty per line, «Qabul qilish».
 * «Jo'natmalar» tab: this device's transfer events with their sync state.
 */
import { useUnit } from "effector-react";
import {
  AlertTriangle,
  ArrowRightLeft,
  CheckCircle2,
  PackageOpen,
  Trash2,
  Truck,
  WifiOff,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { tashkentDateTime } from "#/shared/lib/dates.ts";
import { $isOnline } from "@shared/state/network";
import {
  Banner,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Icon,
  Input,
  Kbd,
  Label,
  NativeSelect,
  NoPermissionState,
  SegmentedControl,
  StatusChip,
  Tabs,
  TabsList,
  TabsTrigger,
} from "@shared/ui";

import { usePosPermission } from "#/entities/pos-session/index.ts";
import { ProductSearch, QtyStepper, ScanField, WhScreen, trimQty } from "#/features/wh-scan/index.ts";
import { errorText, messageText } from "#/shared/lib/i18n-errors.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";

import {
  $acting,
  $destinations,
  $error,
  $form,
  $formErrors,
  $history,
  $incoming,
  $incomingCached,
  $notice,
  $posted,
  $receiveQty,
  $selectedIncoming,
  $source,
  $tab,
  $warehouses,
  destinationChanged,
  driverNameChanged,
  errorDismissed,
  incomingSelected,
  isSendReady,
  isShort,
  lineQtyChanged,
  lineRemoved,
  noticeDismissed,
  postRequested,
  productPicked,
  receiveConfirmed,
  receiveLineError,
  receiveQtyChanged,
  scanned,
  sendConfirmed,
  sendExistingRequested,
  tabChanged,
  totalsOf,
  transfersOpened,
  transportModeChanged,
  vehiclePlateChanged,
  type TransfersError,
  type TransfersTab,
} from "../../model/index.ts";

const WAREHOUSE_HUB = "/pos/warehouse";

function useErrorMessage(error: TransfersError | null): string | null {
  const { t } = useTranslation("pos");
  if (!error) return null;
  if (error.kind === "unknown_barcode") return t("stockCount.unknownBarcode", { code: error.code });
  if (error.kind === "check_digit") return t("stockCount.checkDigit", { code: error.code });
  if (error.kind === "api") return errorText(error.code, error.params);
  return error.kind === "no_actor" ? t("wh.noActor") : t("wh.noDevice");
}

function TransfersPage() {
  const { t } = useTranslation("pos");
  const navigate = useNavigate();
  const canCreate = usePosPermission("transfer.create");
  const canReceive = usePosPermission("transfer.receive");
  const [online, tab, error, notice] = useUnit([$isOnline, $tab, $error, $notice]);
  const errorMessage = useErrorMessage(error);
  const scanRef = useRef<HTMLInputElement | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const [confirmShort, setConfirmShort] = useState(false);
  const form = useUnit($form);

  useEffect(() => {
    if (canCreate || canReceive) transfersOpened();
  }, [canCreate, canReceive]);
  useEffect(() => {
    if (!canCreate && canReceive && tab === "send") tabChanged("receive");
  }, [canCreate, canReceive, tab]);

  const trySend = () => {
    if (form.lines.some(isShort)) setConfirmShort(true);
    else sendConfirmed();
  };

  useHotkeys([
    { key: "F1", handler: () => scanRef.current?.focus() },
    { key: "F2", handler: () => searchRef.current?.focus() },
    {
      key: "F9",
      handler: () => (tab === "send" ? trySend() : tab === "receive" ? receiveConfirmed() : undefined),
    },
    { key: "Escape", allowInInput: true, handler: () => navigate(WAREHOUSE_HUB) },
  ]);

  if (!canCreate && !canReceive) return <NoPermissionState />;

  const tabs: { value: TransfersTab; label: string; enabled: boolean }[] = [
    { value: "send", label: t("transfers.tabs.send"), enabled: canCreate },
    { value: "receive", label: t("transfers.tabs.receive"), enabled: canReceive },
    { value: "history", label: t("transfers.tabs.history"), enabled: true },
  ];

  return (
    <WhScreen title={t("transfers.title")} onBack={() => navigate(WAREHOUSE_HUB)} testId="pos-transfers">
      <Tabs value={tab} onValueChange={(v) => tabChanged(v as TransfersTab)} className="mb-3">
        <TabsList>
          {tabs.map((x) => (
            <TabsTrigger key={x.value} value={x.value} disabled={!x.enabled} className="h-11 px-5">
              {x.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {!online ? (
        <Banner tone="warning" icon={WifiOff} className="mb-3">
          {t("wh.offlineNote")}
        </Banner>
      ) : null}
      {errorMessage ? (
        <Banner
          tone="destructive"
          icon={AlertTriangle}
          className="mb-3"
          action={
            <Button size="sm" variant="ghost" onClick={() => errorDismissed()}>
              ✕
            </Button>
          }
        >
          <span data-testid="transfer-error">{errorMessage}</span>
        </Banner>
      ) : null}
      {notice ? <NoticeBanner /> : null}

      {tab === "send" ? <SendTab scanRef={scanRef} searchRef={searchRef} onSend={trySend} /> : null}
      {tab === "receive" ? <ReceiveTab /> : null}
      {tab === "history" ? <HistoryTab /> : null}

      <ConfirmDialog
        open={confirmShort}
        onOpenChange={setConfirmShort}
        title={t("transfers.confirmShortTitle")}
        description={t("transfers.confirmShortBody")}
        confirmLabel={t("transfers.send")}
        onConfirm={() => {
          setConfirmShort(false);
          sendConfirmed();
        }}
      />
    </WhScreen>
  );
}

function NoticeBanner() {
  const { t } = useTranslation("pos");
  const notice = useUnit($notice);
  if (!notice) return null;
  const dismiss = (
    <Button size="sm" variant="ghost" onClick={() => noticeDismissed()}>
      ✕
    </Button>
  );
  if (notice.kind === "posted") {
    return (
      <Banner tone="success" icon={CheckCircle2} className="mb-3" action={dismiss}>
        {t("transfers.posted", { number: notice.transfer.number ?? "" })}
      </Banner>
    );
  }
  if (notice.kind === "received_local") {
    return (
      <Banner tone="success" icon={CheckCircle2} className="mb-3" action={dismiss}>
        <span data-testid="transfer-notice">{t("transfers.receivedLocal")}</span>
        {notice.status ? ` · ${t(`transfers.status.${notice.status}` as "transfers.status.received")}` : null}
      </Banner>
    );
  }
  const ettn = notice.warnings.includes("ETTN_REQUIRED");
  return (
    <Banner
      tone={ettn ? "warning" : "success"}
      icon={ettn ? Truck : CheckCircle2}
      className="mb-3"
      action={dismiss}
    >
      <span data-testid="transfer-notice">
        {t("transfers.sentLocal")}
        {notice.number ? ` · ${notice.number}` : ""}
        {notice.status ? ` · ${t(`transfers.status.${notice.status}` as "transfers.status.sent")}` : ""}
      </span>
      {ettn ? <span className="block">{t("transfers.ettnWaiting")}</span> : null}
    </Banner>
  );
}

function SendTab({
  scanRef,
  searchRef,
  onSend,
}: {
  scanRef: React.RefObject<HTMLInputElement | null>;
  searchRef: React.RefObject<HTMLInputElement | null>;
  onSend: () => void;
}) {
  const { t } = useTranslation("pos");
  const [online, source, destinations, form, errors, acting, posted] = useUnit([
    $isOnline, $source, $destinations, $form, $formErrors, $acting, $posted,
  ]); // prettier-ignore
  const totals = totalsOf(form.lines);
  const canSubmit = errors.length === 0 && !acting;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="flex min-w-0 flex-col gap-3">
        <Card className="grid gap-3 p-4 sm:grid-cols-[1fr_auto_1fr] sm:items-end">
          <div>
            <Label>{t("transfers.from")}</Label>
            <p className="mt-1 h-[42px] content-center text-[15px] font-bold" data-testid="transfer-from">
              {source?.name ?? "—"}
            </p>
          </div>
          <Icon as={ArrowRightLeft} size="md" className="hidden text-muted-foreground sm:block" />
          <div>
            <Label htmlFor="transfer-to">{t("transfers.to")}</Label>
            <NativeSelect
              id="transfer-to"
              value={form.toWarehouseId ?? ""}
              onChange={(e) => destinationChanged(e.target.value || null)}
              options={[
                { value: "", label: t("transfers.toPlaceholder") },
                ...destinations.map((w) => ({ value: w.id, label: w.name })),
              ]}
              wrapperClassName="w-full"
              className="h-12"
            />
          </div>
          {destinations.length === 0 ? (
            <p className="text-[13px] text-warning-strong sm:col-span-3">{t("transfers.noDestinations")}</p>
          ) : null}
        </Card>
        <ScanField onScan={(code) => scanned(code)} inputRef={scanRef} />
        <ProductSearch
          inputRef={searchRef}
          placeholder={`${t("stockCount.manual")} — ${t("stockCount.searchPlaceholder")}`}
          onPick={(p) => productPicked({ productId: p.product.id, name: p.product.name })}
        />
        <Card className="p-0">
          {form.lines.length === 0 ? (
            <EmptyState icon={PackageOpen} title={t("transfers.empty")} />
          ) : (
            <ul className="divide-y divide-border" data-testid="transfer-lines">
              {form.lines.map((l) => (
                <li
                  key={l.productId}
                  className="flex flex-wrap items-center gap-3 px-4 py-3"
                  data-testid="transfer-line"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[15px] font-bold">{l.name}</p>
                    <p className="text-[12px] text-muted-foreground">
                      {l.available !== null ? t("transfers.available", { qty: trimQty(l.available) }) : null}
                      {l.markingCodes.length
                        ? ` · ${t("transfers.markingCodes", { count: l.markingCodes.length })}`
                        : ""}
                    </p>
                    {isShort(l) ? (
                      <p className="text-[12px] font-semibold text-warning-strong">
                        {t("transfers.short", { qty: trimQty(l.available ?? "0") })}
                      </p>
                    ) : null}
                  </div>
                  <QtyStepper
                    value={l.qty}
                    label={l.name}
                    onChange={(qty) => lineQtyChanged({ productId: l.productId, qty })}
                  />
                  <Button
                    size="icon-pos"
                    variant="ghost"
                    aria-label={t("transfers.remove")}
                    onClick={() => lineRemoved(l.productId)}
                  >
                    <Icon as={Trash2} size="md" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <p className="text-[14px] font-semibold" data-testid="transfer-totals">
          {t("transfers.totals", { lines: totals.lines, qty: trimQty(totals.qty) })}
          {totals.marking ? ` · ${t("transfers.markingCodes", { count: totals.marking })}` : ""}
        </p>
      </div>
      <aside className="flex flex-col gap-3">
        <Card className="flex flex-col gap-3 p-4">
          <h2 className="text-[15px] font-bold">{t("transfers.transportMode")}</h2>
          <SegmentedControl
            label={t("transfers.transportMode")}
            density="touch"
            value={form.transportMode}
            onChange={(m) => transportModeChanged(m)}
            options={[
              { value: "vehicle", label: t("transfers.transport.vehicle") },
              { value: "on_foot_or_public", label: t("transfers.transport.on_foot_or_public") },
            ]}
          />
          {form.transportMode === "vehicle" ? (
            <>
              <div>
                <Label htmlFor="transfer-plate">{t("transfers.vehiclePlate")}</Label>
                <Input
                  id="transfer-plate"
                  value={form.vehiclePlate}
                  maxLength={16}
                  onChange={(e) => vehiclePlateChanged(e.target.value)}
                  className="h-12"
                />
                {errors.includes("plate_required") && form.lines.length > 0 ? (
                  <p className="mt-1 text-[12px] text-destructive-strong">
                    {t("transfers.vehiclePlateRequired")}
                  </p>
                ) : null}
              </div>
              <div>
                <Label htmlFor="transfer-driver">{t("transfers.driverName")}</Label>
                <Input
                  id="transfer-driver"
                  value={form.driverName}
                  maxLength={255}
                  onChange={(e) => driverNameChanged(e.target.value)}
                  className="h-12"
                />
              </div>
              <p className="text-[12px] text-muted-foreground">{t("transfers.ettnNote")}</p>
            </>
          ) : null}
        </Card>
        {posted ? <PostedCard /> : null}
        <Button
          size="pos"
          variant="secondary"
          disabled={!online || !canSubmit}
          title={online ? undefined : t("transfers.postOffline")}
          onClick={() => postRequested()}
        >
          {t("transfers.post")}
        </Button>
        <Button size="pos-cta" disabled={!canSubmit} onClick={onSend} data-testid="transfer-send">
          {t("transfers.send")}
          <Kbd keys="F9" inverted />
        </Button>
      </aside>
    </div>
  );
}

function PostedCard() {
  const { t } = useTranslation("pos");
  const [posted, acting] = useUnit([$posted, $acting]);
  if (!posted) return null;
  const ready = isSendReady(posted);
  const steps = [
    "draft",
    "posted",
    ...(posted.transport_mode === "vehicle" ? ["ettn"] : []),
    "sent",
    "received",
  ];
  const doneUntil =
    posted.status === "posted" ? (ready ? (posted.transport_mode === "vehicle" ? 3 : 2) : 2) : 1;
  return (
    <Card className="flex flex-col gap-2 p-4">
      <p className="text-[15px] font-bold">
        {t("transfers.doc")}: {posted.number ?? "—"}
      </p>
      <ol className="flex flex-col gap-1 text-[13px]">
        {steps.map((s, i) => (
          <li key={s} className={i < doneUntil ? "font-bold text-success-strong" : "text-muted-foreground"}>
            {i + 1}. {t(`transfers.steps.${s}` as "transfers.steps.draft")}
          </li>
        ))}
      </ol>
      {ready ? (
        <Button size="pos" disabled={acting} onClick={() => sendExistingRequested(posted.id)}>
          {t("transfers.sendExisting")}
        </Button>
      ) : (
        <StatusChip tone="awaiting-approval">{t("transfers.ettnWaiting")}</StatusChip>
      )}
    </Card>
  );
}

function ReceiveTab() {
  const { t } = useTranslation("pos");
  const [incoming, cached, selected, qty, acting, online, warehouses] = useUnit([
    $incoming, $incomingCached, $selectedIncoming, $receiveQty, $acting, $isOnline, $warehouses,
  ]); // prettier-ignore
  const whName = (id: string) => warehouses.find((w) => w.id === id)?.name ?? "—";
  const lineErrors = selected
    ? selected.lines.map((l) => receiveLineError(l.qty_sent, qty[l.id] ?? l.qty_sent))
    : [];
  return (
    <div className="grid gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
      <Card className="flex flex-col gap-2 p-3">
        {cached && !online ? (
          <p className="text-[12px] text-muted-foreground">{t("transfers.incomingCached")}</p>
        ) : null}
        {incoming.length === 0 ? (
          <EmptyState icon={PackageOpen} title={t("transfers.incomingEmpty")} />
        ) : (
          incoming.map((tr) => (
            <Button
              key={tr.id}
              variant={selected?.id === tr.id ? "default" : "secondary"}
              size="pos"
              className="justify-start"
              onClick={() => incomingSelected(tr.id)}
              data-testid="incoming-transfer"
            >
              {t("transfers.incomingRow", {
                number: tr.number ?? "—",
                from: whName(tr.from_warehouse_id),
                lines: tr.lines.length,
              })}
            </Button>
          ))
        )}
      </Card>
      {selected ? (
        <Card className="flex flex-col gap-3 p-4">
          <ul className="divide-y divide-border">
            {selected.lines.map((l, i) => (
              <li key={l.id} className="flex flex-wrap items-center gap-3 py-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-bold">{l.product_name}</p>
                  <p className="text-[12px] text-muted-foreground">
                    {t("transfers.sent")}: {trimQty(l.qty_sent)}
                  </p>
                  {lineErrors[i] ? (
                    <p className="text-[12px] text-destructive-strong">
                      {t("transfers.receiveRange", { max: trimQty(l.qty_sent) })}
                    </p>
                  ) : null}
                </div>
                <QtyStepper
                  value={qty[l.id] ?? l.qty_sent}
                  label={`${t("transfers.received")} — ${l.product_name}`}
                  onChange={(v) => receiveQtyChanged({ lineId: l.id, qty: v })}
                />
              </li>
            ))}
          </ul>
          <Button
            size="pos-cta"
            disabled={acting || lineErrors.some(Boolean)}
            onClick={() => receiveConfirmed()}
            data-testid="transfer-receive"
          >
            {t("transfers.receive")}
            <Kbd keys="F9" inverted />
          </Button>
        </Card>
      ) : null}
    </div>
  );
}

function HistoryTab() {
  const { t } = useTranslation("pos");
  const history = useUnit($history);
  if (history.length === 0) return <EmptyState icon={Truck} title={t("transfers.historyEmpty")} />;
  return (
    <Card className="p-0">
      <ul className="divide-y divide-border" data-testid="transfer-history">
        {history.map((h) => (
          <li key={h.clientEventId} className="flex flex-wrap items-center gap-3 px-4 py-3">
            <div className="min-w-0 flex-1">
              <p className="font-bold">
                {h.kind === "sent" ? t("transfers.tabs.send") : t("transfers.tabs.receive")} ·{" "}
                {h.number ?? "—"}
              </p>
              <p className="text-[12px] text-muted-foreground">
                {tashkentDateTime(h.createdAt)} · {t("transfers.historyLines", { count: h.lines })}
              </p>
              {h.warnings.includes("ETTN_REQUIRED") ? (
                <p className="text-[12px] text-warning-strong">{t("transfers.warnings.ETTN_REQUIRED")}</p>
              ) : null}
              {h.sync === "rejected" ? (
                <p className="text-[12px] text-destructive-strong">{messageText(h.message, h.errorCode)}</p>
              ) : null}
            </div>
            {h.status ? (
              <StatusChip tone="neutral">
                {t(`transfers.status.${h.status}` as "transfers.status.sent")}
              </StatusChip>
            ) : null}
            <StatusChip
              tone={h.sync === "accepted" ? "success" : h.sync === "rejected" ? "destructive" : "warning"}
            >
              {t(`wh.sync.${h.sync}` as "wh.sync.pending")}
            </StatusChip>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export const Transfers = {
  route: "warehouse/transfer",
  titleKey: "pos:transfers.title",
  Page: TransfersPage,
} as const;

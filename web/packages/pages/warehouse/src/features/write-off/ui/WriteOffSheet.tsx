/**
 * «Hisobdan chiqarish» sheet (07 BO-03, US-M04-06): partiya (muddati bilan), miqdor, sabab
 * (`expired|damaged|gift|other`), sovg'a turi (`promo_justified|other`, standart `other`), aksiya
 * buyrug'i (`promo_justified` da majburiy), javobgar shaxs → `POST /write-offs` → `/post`.
 * 200 → toast; 202 (limitdan oshdi) → «Tasdiq kutilmoqda» (BO-16). A refused post keeps the draft
 * with «Qayta o'tkazish» / «Qoralamani bekor qilish». Online only (qaror #54).
 */
import { useUnit } from "effector-react";
import { Hourglass, Trash2, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney } from "@shared/lib/format";
import {
  Banner,
  Button,
  DecimalInput,
  FormField,
  Icon,
  Input,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SimpleSelect,
  Textarea,
  toast,
} from "@shared/ui";

import { ProductPicker, type PickedProduct } from "#/entities/product/index.tsx";
import { productCached, unitLabel, useQtyFormat, type Warehouse } from "#/entities/refs/index.ts";
import { ResponsibleSelect } from "#/entities/refs/ui/ResponsibleSelect.tsx";
import { todayIso } from "#/shared/lib/effect.ts";
import { errorText } from "#/shared/lib/errors.ts";
import { ReasonDialog } from "#/shared/ui/ReasonDialog.tsx";

import {
  $awaiting,
  $failedDraft,
  $lots,
  AUTO_LOT,
  GIFT_KINDS,
  WRITE_OFF_REASONS,
  cancelWriteOffFx,
  lineError,
  loadLotsFx,
  lotAvailable,
  needsPromoRef,
  repostWriteOffFx,
  submitWriteOffFx,
  writeOffClosed,
  writeOffProductSearch,
  type GiftKind,
  type WriteOffLineDraft,
  type WriteOffReason,
} from "../model/index.ts";

/** Opening a write-off from an expiring lot (Qoldiq → «Muddati 7 kunda tugaydi»). */
export interface WriteOffPreset {
  productId: string;
  name: string;
  unitCode: string;
  lotId?: string;
  reason?: WriteOffReason;
}

export interface WriteOffSheetProps {
  open: boolean;
  onClose: () => void;
  warehouse: Warehouse | null;
  preset?: WriteOffPreset | null;
  online: boolean;
}

export function WriteOffSheet({ open, onClose, warehouse, preset, online }: WriteOffSheetProps) {
  const { t } = useTranslation("warehouse");
  const closed = useUnit(writeOffClosed);
  const close = () => {
    closed();
    onClose();
  };
  return (
    <Sheet open={open} onOpenChange={(next) => (next ? undefined : close())}>
      <SheetContent wide>
        <SheetHeader>
          <SheetTitle>{t("writeOff.title")}</SheetTitle>
          <SheetDescription>{t("writeOff.description")}</SheetDescription>
        </SheetHeader>
        {open && warehouse ? (
          <WriteOffBody warehouse={warehouse} preset={preset ?? null} online={online} onClose={close} />
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

let nextKey = 1;
const lineOf = (
  p: Omit<WriteOffPreset, "lotId" | "reason">,
  lotId = AUTO_LOT,
  reason: WriteOffReason = "expired",
): WriteOffLineDraft => ({
  key: `l${(nextKey += 1)}`,
  productId: p.productId,
  name: p.name,
  unitCode: p.unitCode,
  lotId,
  qty: "",
  reason,
  giftKind: "other",
});

function WriteOffBody({
  warehouse,
  preset,
  online,
  onClose,
}: {
  warehouse: Warehouse;
  preset: WriteOffPreset | null;
  online: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation("warehouse");
  const formatQty = useQtyFormat();
  const [lots, awaiting, failed, loadLots, submit, repost, cancelDraft, cache, pending] = useUnit([
    $lots,
    $awaiting,
    $failedDraft,
    loadLotsFx,
    submitWriteOffFx,
    repostWriteOffFx,
    cancelWriteOffFx,
    productCached,
    submitWriteOffFx.pending,
  ]);
  const reposting = useUnit(repostWriteOffFx.pending);
  const [lines, setLines] = useState<WriteOffLineDraft[]>(() =>
    preset ? [lineOf(preset, preset.lotId ?? AUTO_LOT, preset.reason ?? "expired")] : [],
  );
  const [docDate, setDocDate] = useState(todayIso());
  const [promoRef, setPromoRef] = useState("");
  const [responsible, setResponsible] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  const promoRequired = needsPromoRef(lines);
  const errors = lines.map((l) => lineError(l, lots[l.productId] ?? []));
  const valid =
    lines.length > 0 &&
    errors.every((e) => e === null) &&
    (!promoRequired || promoRef.trim() !== "") &&
    docDate !== "";

  const update = (key: string, patch: Partial<WriteOffLineDraft>) =>
    setLines((prev) => prev.map((l) => (l.key === key ? { ...l, ...patch } : l)));

  const add = (p: PickedProduct) => {
    cache(p);
    setLines((prev) => [...prev, lineOf({ productId: p.id, name: p.name, unitCode: p.unit_code })]);
    if (!(p.id in lots)) loadLots({ warehouseId: warehouse.id, productId: p.id }).catch(() => undefined);
  };

  const send = () => {
    setSubmitted(true);
    if (!valid) return;
    setError(null);
    submit({
      warehouseId: warehouse.id,
      docDate,
      lines,
      promoOrderRef: promoRef,
      responsibleUserId: responsible,
      comment,
    })
      .then(({ doc, postError }) => {
        if (postError) return;
        if (doc.status === "posted") {
          toast.success(
            t("writeOff.toast.posted", { number: doc.number ?? "" }),
            formatMoney(doc.total_cost),
          );
          onClose();
        }
      })
      .catch((e: unknown) => setError(errorText(e)));
  };

  if (awaiting) {
    return (
      <>
        <SheetBody>
          <Banner tone="awaiting-approval" icon={Hourglass} live="assertive">
            <span className="flex flex-col gap-1">
              <span className="font-bold">{t("writeOff.awaiting.title")}</span>
              <span className="font-normal">
                {t("writeOff.awaiting.description", { amount: formatMoney(awaiting.total_cost) })}
              </span>
            </span>
          </Banner>
        </SheetBody>
        <SheetFooter>
          <Button onClick={onClose}>{t("actions.close")}</Button>
        </SheetFooter>
      </>
    );
  }

  if (failed) {
    return (
      <>
        <SheetBody>
          <Banner tone="destructive" icon={TriangleAlert} live="assertive">
            <span className="flex flex-col gap-1">
              <span className="font-bold">{t("writeOff.failed.title")}</span>
              <span className="font-normal">{errorText(failed.error)}</span>
            </span>
          </Banner>
          <p className="text-small text-foreground-secondary">{t("writeOff.failed.description")}</p>
        </SheetBody>
        <SheetFooter>
          <Button
            variant="destructive-outline"
            disabled={reposting || !online}
            onClick={() => setCancelling(true)}
          >
            {t("writeOff.failed.cancel")}
          </Button>
          <Button
            disabled={reposting || !online}
            aria-busy={reposting || undefined}
            onClick={() =>
              repost(failed.doc.id)
                .then((doc) => {
                  if (doc.status === "posted") {
                    toast.success(t("writeOff.toast.posted", { number: doc.number ?? "" }));
                    onClose();
                  }
                })
                .catch(() => undefined)
            }
          >
            {t("writeOff.failed.retry")}
          </Button>
        </SheetFooter>
        <ReasonDialog
          open={cancelling}
          onOpenChange={setCancelling}
          title={t("writeOff.failed.cancel")}
          onConfirm={async (reason) => {
            await cancelDraft({ id: failed.doc.id, reason });
            toast.info(t("writeOff.toast.cancelled"));
            onClose();
          }}
        />
      </>
    );
  }

  return (
    <>
      <SheetBody>
        {!online ? (
          <Banner tone="warning" icon={TriangleAlert}>
            {t("writeOff.offline")}
          </Banner>
        ) : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            label={t("writeOff.fields.docDate")}
            required
            error={submitted && docDate === "" ? "validation.required" : null}
          >
            <Input type="date" value={docDate} onChange={(e) => setDocDate(e.target.value)} />
          </FormField>
          <FormField label={t("writeOff.fields.responsible")} hint={t("writeOff.fields.responsibleHint")}>
            {(a11y) => <ResponsibleSelect {...a11y} value={responsible} onChange={setResponsible} />}
          </FormField>
        </div>
        <section className="flex flex-col gap-2" aria-label={t("writeOff.linesLabel")}>
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[14px] font-bold">{t("writeOff.linesLabel")}</h3>
            <ProductPicker model={writeOffProductSearch} onPick={add} disabled={!online} />
          </div>
          {submitted && lines.length === 0 ? (
            <p role="alert" className="text-small font-semibold text-destructive">
              {t("writeOff.noLines")}
            </p>
          ) : null}
          {lines.map((l, i) => {
            const productLots = lots[l.productId];
            const lot = productLots?.find((x) => x.id === l.lotId);
            const lineErr = errors[i];
            return (
              <div key={l.key} className="flex flex-col gap-3 rounded-lg border border-border px-3 py-3">
                <div className="flex items-center gap-2">
                  <p className="min-w-0 flex-1 truncate text-[13px] font-bold">{l.name}</p>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-label={t("actions.removeLine", { name: l.name })}
                    onClick={() => setLines((prev) => prev.filter((x) => x.key !== l.key))}
                  >
                    <Icon as={Trash2} size="sm" />
                  </Button>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <FormField label={t("writeOff.fields.lot")}>
                    <SimpleSelect
                      options={[
                        { value: AUTO_LOT, label: t("writeOff.autoLot") },
                        ...(productLots ?? []).map((x) => ({
                          value: x.id,
                          label: t("writeOff.lotOption", {
                            expiry: x.expiry_date ? formatDate(x.expiry_date) : t("writeOff.noExpiry"),
                            qty: `${formatQty(lotAvailable(x), l.unitCode)} ${unitLabel(l.unitCode)}`,
                            received: formatDate(x.received_at),
                          }),
                        })),
                      ]}
                      value={l.lotId}
                      onValueChange={(v) => update(l.key, { lotId: v })}
                    />
                  </FormField>
                  <FormField
                    label={t("writeOff.fields.qty")}
                    required
                    error={
                      submitted && lineErr === "qty"
                        ? t("validation.positiveQty")
                        : lineErr === "overLot" && lot
                          ? t("writeOff.overLot", { qty: formatQty(lotAvailable(lot), l.unitCode) })
                          : null
                    }
                  >
                    <DecimalInput
                      precision={3}
                      outputScale={3}
                      suffix={unitLabel(l.unitCode)}
                      value={l.qty}
                      onChange={(v) => update(l.key, { qty: v })}
                    />
                  </FormField>
                  <FormField label={t("writeOff.fields.reason")} required>
                    <SimpleSelect
                      options={WRITE_OFF_REASONS.map((r) => ({
                        value: r,
                        label: t(`writeOff.reasons.${r}`),
                      }))}
                      value={l.reason}
                      onValueChange={(v) => update(l.key, { reason: v as WriteOffReason })}
                    />
                  </FormField>
                  {l.reason === "gift" ? (
                    <FormField
                      label={t("writeOff.fields.giftKind")}
                      required
                      hint={t(`writeOff.giftHint.${l.giftKind}`)}
                    >
                      <SimpleSelect
                        options={GIFT_KINDS.map((g) => ({ value: g, label: t(`writeOff.giftKinds.${g}`) }))}
                        value={l.giftKind}
                        onValueChange={(v) => update(l.key, { giftKind: v as GiftKind })}
                      />
                    </FormField>
                  ) : null}
                </div>
              </div>
            );
          })}
        </section>
        {promoRequired ? (
          <FormField
            label={t("writeOff.fields.promoOrderRef")}
            required
            hint={t("writeOff.fields.promoOrderRefHint")}
            error={submitted && promoRef.trim() === "" ? "validation.required" : null}
          >
            <Input value={promoRef} maxLength={100} onChange={(e) => setPromoRef(e.target.value)} />
          </FormField>
        ) : null}
        <FormField label={t("writeOff.fields.comment")} optional>
          <Textarea value={comment} rows={2} maxLength={1000} onChange={(e) => setComment(e.target.value)} />
        </FormField>
        {error ? (
          <Banner tone="destructive" icon={TriangleAlert} live="assertive">
            {error}
          </Banner>
        ) : null}
      </SheetBody>
      <SheetFooter>
        <Button variant="secondary" disabled={pending} onClick={onClose}>
          {t("actions.back")}
        </Button>
        <Button disabled={pending || !online} aria-busy={pending || undefined} onClick={send}>
          {t("writeOff.submit")}
        </Button>
      </SheetFooter>
    </>
  );
}

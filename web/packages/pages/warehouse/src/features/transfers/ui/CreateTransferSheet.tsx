/**
 * «Ko'chirish» sheet (07 BO-03 action, fields of POS-09): manzil — another branch's warehouse (no
 * transfer inside one branch, qaror #54), sana, tashish usuli (Avtotransport / Piyoda yoki jamoat
 * transporti), avtomobil raqami (vehicle — majburiy, ≤ 16), haydovchi, izoh, lines (tovar, manbada
 * qoldiq, miqdor — overselling only warns). «Qoralama» = `POST /transfers`; «O'tkazish» = + `/post`
 * (vehicle → e-TTN `pending_signature`, 19 §13).
 */
import { useUnit } from "effector-react";
import { Trash2, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import {
  Banner,
  Button,
  DecimalInput,
  FormField,
  Icon,
  Input,
  SegmentedControl,
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
import {
  $warehouses,
  otherBranchWarehouses,
  productCached,
  unitLabel,
  useBranchName,
  useQtyFormat,
  type Warehouse,
} from "#/entities/refs/index.ts";
import { compareQty, isPositive, qty3 } from "#/shared/lib/decimal.ts";
import { todayIso } from "#/shared/lib/effect.ts";
import { errorText } from "#/shared/lib/errors.ts";

import {
  $available,
  VEHICLE_PLATE_MAX,
  createTransferFx,
  loadAvailableFx,
  transferProductSearch,
  type TransferCreate,
} from "../model/index.ts";

type Mode = TransferCreate["transport_mode"] & string;

interface Line {
  productId: string;
  name: string;
  unitCode: string;
  qty: string;
}

export interface CreateTransferSheetProps {
  open: boolean;
  onClose: () => void;
  /** The current branch's warehouse (source, qaror #54). */
  source: Warehouse | null;
  online: boolean;
}

export function CreateTransferSheet({ open, onClose, source, online }: CreateTransferSheetProps) {
  const { t } = useTranslation("warehouse");
  return (
    <Sheet open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <SheetContent wide>
        <SheetHeader>
          <SheetTitle>{t("transfers.create.title")}</SheetTitle>
          <SheetDescription>{t("transfers.create.description")}</SheetDescription>
        </SheetHeader>
        {open && source ? <CreateForm source={source} online={online} onClose={onClose} /> : null}
      </SheetContent>
    </Sheet>
  );
}

function CreateForm({
  source,
  online,
  onClose,
}: {
  source: Warehouse;
  online: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation("warehouse");
  const [warehouses, available, create, loadAvailable, cache, pending] = useUnit([
    $warehouses,
    $available,
    createTransferFx,
    loadAvailableFx,
    productCached,
    createTransferFx.pending,
  ]);
  const branchName = useBranchName();
  const formatQty = useQtyFormat();
  const targets = otherBranchWarehouses(warehouses, source.branch_id);

  const [to, setTo] = useState("");
  const [docDate, setDocDate] = useState(todayIso());
  const [mode, setMode] = useState<Mode>("vehicle");
  const [plate, setPlate] = useState("");
  const [driver, setDriver] = useState("");
  const [comment, setComment] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errors = {
    to: to === "" ? "validation.required" : null,
    docDate: docDate === "" ? "validation.required" : null,
    plate: mode === "vehicle" && plate.trim() === "" ? "validation.required" : null,
    lines: lines.length === 0 ? t("transfers.create.noLines") : null,
  };
  const lineInvalid = (l: Line) => !isPositive(l.qty);
  const valid = Object.values(errors).every((e) => e === null) && !lines.some(lineInvalid);
  const show = (e: string | null) => (submitted ? e : null);

  const addProduct = (p: PickedProduct) => {
    cache(p);
    if (lines.some((l) => l.productId === p.id)) return;
    setLines((prev) => [...prev, { productId: p.id, name: p.name, unitCode: p.unit_code, qty: "" }]);
    loadAvailable({ warehouseId: source.id, productId: p.id }).catch(() => undefined);
  };

  const submit = (post: boolean) => {
    setSubmitted(true);
    if (!valid) return;
    setError(null);
    create({
      post,
      body: {
        from_warehouse_id: source.id,
        to_warehouse_id: to,
        doc_date: docDate,
        transport_mode: mode,
        vehicle_plate: mode === "vehicle" ? plate.trim() : null,
        driver_name: driver.trim() || null,
        comment: comment.trim() || null,
        lines: lines.map((l) => ({ product_id: l.productId, qty_sent: qty3(l.qty) })),
      },
    })
      .then(({ transfer, postError }) => {
        if (postError) {
          toast.warning(t("transfers.toast.draftKept"), errorText(postError));
        } else {
          toast.success(
            post
              ? t("transfers.toast.posted", { number: transfer.number ?? "" })
              : t("transfers.toast.drafted"),
          );
        }
        onClose();
      })
      .catch((e: unknown) => setError(errorText(e)));
  };

  return (
    <>
      <SheetBody>
        <p className="text-small text-foreground-secondary">
          {t("transfers.create.from", { name: `${branchName(source.branch_id)} — ${source.name}` })}
        </p>
        <FormField label={t("transfers.fields.to")} required error={show(errors.to)}>
          <SimpleSelect
            options={targets.map((w) => ({ value: w.id, label: `${branchName(w.branch_id)} — ${w.name}` }))}
            value={to || undefined}
            onValueChange={setTo}
            placeholder={targets.length === 0 ? t("transfers.create.noTargets") : undefined}
            disabled={targets.length === 0}
          />
        </FormField>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label={t("transfers.fields.docDate")} required error={show(errors.docDate)}>
            <Input type="date" value={docDate} onChange={(e) => setDocDate(e.target.value)} />
          </FormField>
          <div className="flex flex-col gap-1.5">
            <span className="text-label text-foreground-secondary">
              {t("transfers.fields.transportMode")}
            </span>
            <SegmentedControl
              label={t("transfers.fields.transportMode")}
              options={[
                { value: "vehicle", label: t("transfers.mode.vehicle") },
                { value: "on_foot_or_public", label: t("transfers.mode.on_foot_or_public") },
              ]}
              value={mode}
              onChange={setMode}
            />
          </div>
        </div>
        {mode === "vehicle" ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label={t("transfers.fields.vehiclePlate")} required error={show(errors.plate)}>
              <Input
                value={plate}
                maxLength={VEHICLE_PLATE_MAX}
                autoComplete="off"
                onChange={(e) => setPlate(e.target.value.toUpperCase())}
              />
            </FormField>
            <FormField label={t("transfers.fields.driverName")} optional>
              <Input value={driver} maxLength={100} onChange={(e) => setDriver(e.target.value)} />
            </FormField>
          </div>
        ) : (
          <Banner tone="info" icon={TriangleAlert}>
            {t("transfers.create.noEttn")}
          </Banner>
        )}
        <section className="flex flex-col gap-2" aria-label={t("transfers.linesLabel")}>
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[14px] font-bold">{t("transfers.linesLabel")}</h3>
            <ProductPicker model={transferProductSearch} onPick={addProduct} disabled={!online} />
          </div>
          {show(errors.lines) ? (
            <p role="alert" className="text-small font-semibold text-destructive">
              {errors.lines}
            </p>
          ) : null}
          {lines.map((l) => {
            const balance = available[l.productId];
            const over = balance !== undefined && isPositive(l.qty) && compareQty(l.qty, balance) > 0;
            return (
              <div
                key={l.productId}
                className="flex flex-col gap-1 rounded-lg border border-border px-3 py-2"
              >
                <div className="flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-semibold">{l.name}</p>
                    <p className="text-[12px] text-muted-foreground">
                      {balance === undefined
                        ? t("transfers.create.balanceLoading")
                        : t("transfers.create.balance", {
                            qty: `${formatQty(balance, l.unitCode)} ${unitLabel(l.unitCode)}`,
                          })}
                    </p>
                  </div>
                  <DecimalInput
                    className="w-32"
                    aria-label={t("transfers.create.qtyFor", { name: l.name })}
                    aria-invalid={(submitted && lineInvalid(l)) || undefined}
                    precision={3}
                    outputScale={3}
                    value={l.qty}
                    onChange={(v) =>
                      setLines((prev) =>
                        prev.map((x) => (x.productId === l.productId ? { ...x, qty: v } : x)),
                      )
                    }
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-label={t("actions.removeLine", { name: l.name })}
                    onClick={() => setLines((prev) => prev.filter((x) => x.productId !== l.productId))}
                  >
                    <Icon as={Trash2} size="sm" />
                  </Button>
                </div>
                {over ? (
                  <p className="text-[12px] font-semibold text-warning-strong">
                    {t("transfers.create.overBalance")}
                  </p>
                ) : null}
                {submitted && lineInvalid(l) ? (
                  <p role="alert" className="text-[12px] font-semibold text-destructive">
                    {t("validation.positiveQty")}
                  </p>
                ) : null}
              </div>
            );
          })}
        </section>
        <FormField label={t("transfers.fields.comment")} optional>
          <Textarea value={comment} rows={2} maxLength={1000} onChange={(e) => setComment(e.target.value)} />
        </FormField>
        {error ? (
          <Banner tone="destructive" icon={TriangleAlert} live="assertive">
            {error}
          </Banner>
        ) : null}
      </SheetBody>
      <SheetFooter>
        <Button variant="secondary" disabled={pending || !online} onClick={() => submit(false)}>
          {t("transfers.create.saveDraft")}
        </Button>
        <Button disabled={pending || !online} aria-busy={pending || undefined} onClick={() => submit(true)}>
          {t("transfers.actions.post")}
        </Button>
      </SheetFooter>
    </>
  );
}

/**
 * Product card (create / edit) — 19 §1 `POST /products`, `PATCH /products/{id}` (version),
 * archive/unarchive, barcodes, MXIK. Field rules from 19 §1 (name 1–255, name_ru ≤ 255 — qaror #29,
 * unit from GET /units, MXIK 17 digits, VAT 12 / 0 or an exemption code, marking group when
 * is_marked, min_stock ≥ 0 with 3 decimals, first barcode on create).
 */
import { Archive, ArchiveRestore, RefreshCw, TriangleAlert } from "lucide-react";
import { useUnit } from "effector-react";
import { useState } from "react";

import type { ApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import type { ProductOut } from "@shared/models";
import {
  Banner,
  Button,
  ConfirmDialog,
  DecimalInput,
  ErrorState,
  Icon,
  Input,
  SheetBody,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SimpleSelect,
  Skeleton,
  StatusChip,
  Switch,
  toast,
} from "@shared/ui";
import { RhfField, useWatch, useZodForm, z, zDecimal } from "@shared/ui/form";

import { $categories, $units, barcodeIssue, isMxikFormat, unitLabel } from "#/entities/product/index.ts";
import { applyServerError } from "#/shared/lib/form.ts";
import { apiErrorText } from "#/shared/lib/messages.ts";

import {
  archiveProductFx,
  createProductFx,
  emptyProductForm,
  formToCreate,
  formToUpdate,
  MARKING_GROUPS,
  PRODUCT_FIELD_MAP,
  productRequested,
  productToForm,
  unarchiveProductFx,
  updateProductFx,
  type ProductFormValues,
} from "../../model/index.ts";
import { Barcodes } from "./Barcodes.tsx";
import { MxikField } from "./MxikField.tsx";

const NONE = "none";

const schema = z
  .object({
    name: z.string().trim().min(1).max(255),
    name_ru: z.string().trim().max(255),
    category_id: z.string(),
    unit_code: z.string().min(1),
    mxik_code: z.string().refine((v) => v === "" || isMxikFormat(v), { message: "validation.mxik_format" }),
    vat_mode: z.enum(["12.00", "0.00", "exempt"]),
    vat_exemption_code: z.string().trim().max(64),
    is_marked: z.boolean(),
    marking_group_code: z.string(),
    is_weighed: z.boolean(),
    min_stock: zDecimal({ scale: 3, optional: true }),
    barcode: z.string().trim().max(64),
  })
  .superRefine((v, ctx) => {
    if (v.vat_mode === "exempt" && v.vat_exemption_code === "") {
      ctx.addIssue({ code: "custom", path: ["vat_exemption_code"], message: "validation.required" });
    }
    if (v.is_marked && v.marking_group_code === "") {
      ctx.addIssue({ code: "custom", path: ["marking_group_code"], message: "validation.required" });
    }
    if (v.barcode !== "") {
      const issue = barcodeIssue(v.barcode);
      if (issue) ctx.addIssue({ code: "custom", path: ["barcode"], message: issue });
    }
  });

export interface ProductEditorProps {
  /** null → create a new product. */
  product: ProductOut | null;
  canManage: boolean;
  onCreated: (product: ProductOut) => void;
  onClose: () => void;
}

/** Loading / error shell around the form while GET /products/{id} runs. */
export function ProductEditorLoading({ error, onRetry }: { error: ApiError | null; onRetry: () => void }) {
  const { t } = useTranslation("catalog");
  return (
    <>
      <SheetHeader>
        <SheetTitle>{t("products.editor.editTitle")}</SheetTitle>
      </SheetHeader>
      <SheetBody>
        {error ? (
          <ErrorState message={apiErrorText(error)} onRetry={onRetry} />
        ) : (
          <div className="flex flex-col gap-4" aria-busy="true">
            <Skeleton className="h-11 w-full" />
            <Skeleton className="h-11 w-full" />
            <Skeleton className="h-11 w-2/3" />
          </div>
        )}
      </SheetBody>
    </>
  );
}

export function ProductEditor({ product, canManage, onCreated, onClose }: ProductEditorProps) {
  const { t } = useTranslation("catalog");
  const [units, categories] = useUnit([$units, $categories]);
  const [create, update, archive, unarchive, creating, updating, archiving] = useUnit([
    createProductFx,
    updateProductFx,
    archiveProductFx,
    unarchiveProductFx,
    createProductFx.pending,
    updateProductFx.pending,
    archiveProductFx.pending,
  ]);
  const reload = useUnit(productRequested);
  const [banner, setBanner] = useState<{ text: string; conflict: boolean } | null>(null);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);

  const isNew = product === null;
  const archived = product?.archived_at != null;
  const readOnly = !canManage || archived;

  const form = useZodForm(schema, { defaultValues: product ? productToForm(product) : emptyProductForm() });
  const [vatMode, isMarked] = useWatch({ control: form.control, name: ["vat_mode", "is_marked"] });

  const onError = (error: ApiError) => {
    const rest = applyServerError<ProductFormValues>(form, error, {
      fieldMap: PRODUCT_FIELD_MAP,
      codeFields: { BARCODE_DUPLICATE: "barcode", MXIK_CODE_INVALID: "mxik_code" },
    });
    setBanner(rest ? { text: rest, conflict: error.code === "VERSION_CONFLICT" } : null);
  };

  const submit = form.handleSubmit(async (values) => {
    setBanner(null);
    try {
      if (isNew) {
        const created = await create(formToCreate(values));
        toast.success(t("products.editor.created"));
        onCreated(created);
      } else {
        const saved = await update({ id: product.id, body: formToUpdate(values, product.version) });
        form.reset(productToForm(saved));
        toast.success(t("products.editor.saved"));
      }
    } catch (e) {
      onError(e as ApiError);
    }
  });

  const unitOptions = units.map((u) => ({ value: u.code, label: unitLabel(u.code) }));
  const categoryOptions = [
    { value: NONE, label: t("products.editor.noCategory") },
    ...categories.map((c) => ({ value: c.id, label: c.name })),
  ];

  return (
    <>
      <SheetHeader>
        <SheetTitle>{isNew ? t("products.editor.newTitle") : product.name}</SheetTitle>
        <SheetDescription>
          {isNew ? t("products.editor.newDescription") : t("products.editor.editDescription")}
        </SheetDescription>
        {archived ? <StatusChip tone="neutral">{t("products.status.archived")}</StatusChip> : null}
      </SheetHeader>
      <SheetBody>
        <form id="product-form" className="flex flex-col gap-5" onSubmit={(e) => void submit(e)} noValidate>
          {banner ? (
            <Banner
              tone="destructive"
              icon={TriangleAlert}
              live="assertive"
              action={
                banner.conflict && product ? (
                  <Button type="button" size="sm" variant="secondary" onClick={() => reload(product.id)}>
                    <Icon as={RefreshCw} size="sm" />
                    {t("products.editor.reload")}
                  </Button>
                ) : undefined
              }
            >
              {banner.text}
            </Banner>
          ) : null}
          {archived ? (
            <Banner tone="info" icon={Archive}>
              {t("products.editor.archivedHint")}
            </Banner>
          ) : null}

          <fieldset disabled={readOnly} className="flex flex-col gap-4">
            <legend className="mb-1 text-overline uppercase text-muted-foreground">
              {t("products.editor.sectionMain")}
            </legend>
            <RhfField
              control={form.control}
              name="name"
              label={t("products.fields.name")}
              required
              render={({ field, control }) => <Input {...control} {...field} maxLength={255} />}
            />
            <RhfField
              control={form.control}
              name="name_ru"
              label={t("products.fields.nameRu")}
              optional
              hint={t("products.fields.nameRuHint")}
              render={({ field, control }) => <Input {...control} {...field} maxLength={255} lang="ru" />}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <RhfField
                control={form.control}
                name="category_id"
                label={t("products.fields.category")}
                optional
                render={({ field, control }) => (
                  <SimpleSelect
                    {...control}
                    options={categoryOptions}
                    value={field.value === "" ? NONE : field.value}
                    onValueChange={(v) => field.onChange(v === NONE ? "" : v)}
                    disabled={readOnly}
                  />
                )}
              />
              <RhfField
                control={form.control}
                name="unit_code"
                label={t("products.fields.unit")}
                required
                render={({ field, control }) => (
                  <SimpleSelect
                    {...control}
                    options={unitOptions}
                    value={field.value}
                    onValueChange={field.onChange}
                    disabled={readOnly}
                  />
                )}
              />
            </div>
            {isNew ? (
              <RhfField
                control={form.control}
                name="barcode"
                label={t("products.fields.barcode")}
                optional
                hint={t("products.fields.barcodeHint")}
                render={({ field, control }) => (
                  <Input {...control} {...field} inputMode="numeric" autoComplete="off" maxLength={64} />
                )}
              />
            ) : null}
          </fieldset>

          <fieldset disabled={readOnly} className="flex flex-col gap-4">
            <legend className="mb-1 text-overline uppercase text-muted-foreground">
              {t("products.editor.sectionTax")}
            </legend>
            <RhfField
              control={form.control}
              name="mxik_code"
              label={t("products.fields.mxik")}
              hint={t("products.fields.mxikHint")}
              render={({ field, control }) => (
                <MxikField
                  control={control}
                  value={field.value}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                  onVatHint={(vat) => form.setValue("vat_mode", vat === "0.00" ? "0.00" : "12.00")}
                  disabled={readOnly}
                />
              )}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <RhfField
                control={form.control}
                name="vat_mode"
                label={t("products.fields.vat")}
                required
                render={({ field, control }) => (
                  <SimpleSelect
                    {...control}
                    options={[
                      { value: "12.00", label: t("products.vat.12") },
                      { value: "0.00", label: t("products.vat.0") },
                      { value: "exempt", label: t("products.vat.exempt") },
                    ]}
                    value={field.value}
                    onValueChange={field.onChange}
                    disabled={readOnly}
                  />
                )}
              />
              {vatMode === "exempt" ? (
                <RhfField
                  control={form.control}
                  name="vat_exemption_code"
                  label={t("products.fields.vatExemption")}
                  required
                  render={({ field, control }) => <Input {...control} {...field} maxLength={64} />}
                />
              ) : null}
            </div>
          </fieldset>

          <fieldset disabled={readOnly} className="flex flex-col gap-4">
            <legend className="mb-1 text-overline uppercase text-muted-foreground">
              {t("products.editor.sectionStock")}
            </legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <RhfField
                control={form.control}
                name="is_marked"
                label={t("products.fields.isMarked")}
                hint={t("products.fields.isMarkedHint")}
                render={({ field, control }) => (
                  <Switch
                    {...control}
                    checked={field.value}
                    onCheckedChange={field.onChange}
                    disabled={readOnly}
                  />
                )}
              />
              <RhfField
                control={form.control}
                name="is_weighed"
                label={t("products.fields.isWeighed")}
                hint={t("products.fields.isWeighedHint")}
                render={({ field, control }) => (
                  <Switch
                    {...control}
                    checked={field.value}
                    onCheckedChange={field.onChange}
                    disabled={readOnly}
                  />
                )}
              />
            </div>
            {isMarked ? (
              <RhfField
                control={form.control}
                name="marking_group_code"
                label={t("products.fields.markingGroup")}
                required
                render={({ field, control }) => (
                  <SimpleSelect
                    {...control}
                    options={MARKING_GROUPS.map((g) => ({ value: g, label: t(`products.marking.${g}`) }))}
                    value={field.value || undefined}
                    onValueChange={field.onChange}
                    disabled={readOnly}
                  />
                )}
              />
            ) : null}
            <RhfField
              control={form.control}
              name="min_stock"
              label={t("products.fields.minStock")}
              optional
              hint={t("products.fields.minStockHint")}
              render={({ field, control }) => (
                <DecimalInput
                  {...control}
                  value={field.value}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                  precision={3}
                  outputScale={3}
                  disabled={readOnly}
                />
              )}
            />
          </fieldset>
        </form>

        {product ? (
          <div className="mt-6 border-t border-divider pt-5">
            <Barcodes product={product} canManage={canManage} />
          </div>
        ) : null}
      </SheetBody>
      <SheetFooter>
        {product && canManage ? (
          archived ? (
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                unarchive(product.id)
                  .then(() => toast.success(t("products.editor.unarchived")))
                  .catch((e: ApiError) => toast.error(apiErrorText(e)));
              }}
            >
              <Icon as={ArchiveRestore} size="sm" />
              {t("products.actions.unarchive")}
            </Button>
          ) : (
            <Button
              type="button"
              variant="destructive-outline"
              onClick={() => {
                setArchiveError(null);
                setConfirmArchive(true);
              }}
            >
              <Icon as={Archive} size="sm" />
              {t("products.actions.archive")}
            </Button>
          )
        ) : null}
        <div className="grow" />
        <Button type="button" variant="secondary" onClick={onClose}>
          {t("products.editor.close")}
        </Button>
        {readOnly ? null : (
          <Button
            type="submit"
            form="product-form"
            disabled={creating || updating}
            aria-busy={creating || updating || undefined}
          >
            {isNew ? t("products.editor.create") : t("products.editor.save")}
          </Button>
        )}
      </SheetFooter>

      {product ? (
        <ConfirmDialog
          open={confirmArchive}
          onOpenChange={setConfirmArchive}
          title={t("products.archive.title")}
          description={t("products.archive.body", { name: product.name })}
          confirmLabel={t("products.actions.archive")}
          tone="destructive"
          pending={archiving}
          error={archiveError}
          onConfirm={() =>
            archive(product.id)
              .then(() => toast.success(t("products.editor.archived")))
              .catch((e: ApiError) => {
                setArchiveError(apiErrorText(e));
                throw e;
              })
          }
        />
      ) : null}
    </>
  );
}

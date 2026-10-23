import { useUnit } from "effector-react";
import { Info, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate } from "@shared/lib/date";
import {
  Banner,
  Button,
  ConfirmDialog,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  FormField,
  Input,
  RadioCard,
  RadioGroup,
  SegmentedControl,
  toast,
} from "@shared/ui";
import {
  Controller,
  RhfField,
  useZodForm,
  z,
  type Control,
  type FieldPath,
  type FieldValues,
} from "@shared/ui/form";

import { applyServerErrors } from "#/shared/lib/form.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  DEFAULT_SETTLEMENT_CATEGORY,
  SETTLEMENT_CATEGORIES,
  createBranchFx,
  currentMonthStart,
  updateBranchFx,
  type Branch,
  type SettlementCategory,
  type WarehouseType,
} from "../../model/index.ts";

const categorySchema = z.enum(["city_100k_plus", "other", "remote_mountain"]);
const SERVER_FIELDS = { settlement_category: "settlementCategory" } as const;

interface CategoryValues extends FieldValues {
  settlementCategory: SettlementCategory;
}

/** «Aholi punkti toifasi» (07 BO-12): 4% / 2% / 1% with the SK 467 explanation. */
export function SettlementCategoryField<T extends CategoryValues>({
  control,
  showDefaultHint,
}: {
  control: Control<T>;
  showDefaultHint: boolean;
}) {
  const { t } = useTranslation("settings");
  return (
    <Controller
      control={control}
      name={"settlementCategory" as FieldPath<T>}
      render={({ field }) => (
        <FormField
          label={t("branches.fields.settlementCategory")}
          required
          hint={showDefaultHint ? t("branches.category.defaultHint") : t("branches.category.help")}
        >
          {(a11y) => (
            <RadioGroup
              id={a11y.id}
              aria-describedby={a11y["aria-describedby"]}
              aria-label={t("branches.fields.settlementCategory")}
              value={field.value}
              onValueChange={field.onChange}
              className="grid gap-2"
            >
              {SETTLEMENT_CATEGORIES.map((c) => (
                <RadioCard
                  key={c}
                  value={c}
                  title={t(`branches.category.${c}`)}
                  description={t(`branches.categoryHint.${c}`)}
                />
              ))}
            </RadioGroup>
          )}
        </FormField>
      )}
    />
  );
}

const createSchema = z.object({
  name: z.string().trim().min(2).max(100),
  address: z.string().trim().max(200),
  settlementCategory: categorySchema,
  warehouseType: z.enum(["store", "stock"]),
});

/** «+ Filial qo'shish» (07 BO-12, US-M14-03): branch + its own warehouse (2920/2910 by type). */
export function CreateBranchDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return open ? <CreateBranchForm onClose={onClose} /> : null;
}

function CreateBranchForm({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const create = useUnit(createBranchFx);
  const online = useOnline();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useZodForm(createSchema, {
    defaultValues: {
      name: "",
      address: "",
      settlementCategory: DEFAULT_SETTLEMENT_CATEGORY,
      warehouseType: "store",
    },
  });
  const categoryChosen = form.formState.dirtyFields.settlementCategory === true;
  const categoryTouched = form.formState.touchedFields.settlementCategory === true || categoryChosen;

  const submit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      const created = await create({
        name: values.name,
        address: values.address,
        settlementCategory: values.settlementCategory,
        categoryChosen: categoryTouched,
        warehouseType: values.warehouseType,
      });
      toast.success(t("branches.created", { name: created.name, code: created.code }));
      onClose();
    } catch (error) {
      setFormError(applyServerErrors(form, error, SERVER_FIELDS));
    }
  });

  return (
    <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent size="md">
        <DialogHeader>
          <DialogTitle>{t("branches.createTitle")}</DialogTitle>
          <DialogDescription>{t("branches.createHint")}</DialogDescription>
        </DialogHeader>
        <form id="create-branch" noValidate onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
          <RhfField
            control={form.control}
            name="name"
            label={t("branches.fields.name")}
            required
            render={({ field, control }) => <Input {...control} {...field} maxLength={100} />}
          />
          <RhfField
            control={form.control}
            name="address"
            label={t("branches.fields.address")}
            optional
            render={({ field, control }) => <Input {...control} {...field} maxLength={200} />}
          />
          <SettlementCategoryField control={form.control} showDefaultHint={!categoryTouched} />
          <Controller
            control={form.control}
            name="warehouseType"
            render={({ field }) => (
              <FormField
                label={t("branches.fields.warehouseType")}
                required
                hint={t("branches.warehouseTypeHint")}
              >
                <SegmentedControl<WarehouseType>
                  label={t("branches.fields.warehouseType")}
                  value={field.value}
                  onChange={field.onChange}
                  options={[
                    { value: "store", label: t("branches.warehouseType.store") },
                    { value: "stock", label: t("branches.warehouseType.stock") },
                  ]}
                />
              </FormField>
            )}
          />
          {formError ? (
            <Banner tone="destructive" icon={TriangleAlert} live="assertive">
              {formError}
            </Banner>
          ) : null}
        </form>
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button type="submit" form="create-branch" disabled={!online || form.formState.isSubmitting}>
            {t("branches.saveNew")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const editSchema = z.object({
  name: z.string().trim().min(2).max(100),
  address: z.string().trim().max(200),
  settlementCategory: categorySchema,
});
type EditValues = z.infer<typeof editSchema>;

/**
 * «Tahrir» (07 BO-12): a category change applies from the 1st of the current month (20 #33, earlier
 * periods are not recalculated); an address change reminds to re-register the branch's registers.
 * Both are confirmed before saving.
 */
export function EditBranchDialog({ branch, onClose }: { branch: Branch | null; onClose: () => void }) {
  return branch ? (
    <EditBranchForm key={`${branch.id}:${branch.version}`} branch={branch} onClose={onClose} />
  ) : null;
}

function EditBranchForm({ branch, onClose }: { branch: Branch; onClose: () => void }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const update = useUnit(updateBranchFx);
  const online = useOnline();
  const [formError, setFormError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<EditValues | null>(null);
  const form = useZodForm(editSchema, {
    defaultValues: {
      name: branch.name,
      address: branch.address ?? "",
      settlementCategory: branch.settlement_category,
    },
  });

  const changes = (values: EditValues) => ({
    name: values.name.trim() !== branch.name ? values.name : undefined,
    address: values.address.trim() !== (branch.address ?? "") ? values.address.trim() || null : undefined,
    settlementCategory:
      values.settlementCategory !== branch.settlement_category ? values.settlementCategory : undefined,
  });

  const save = async (values: EditValues) => {
    setFormError(null);
    const c = changes(values);
    try {
      await update({
        branchId: branch.id,
        version: branch.version,
        ...(c.name !== undefined ? { name: c.name } : {}),
        ...(c.address !== undefined ? { address: c.address } : {}),
        ...(c.settlementCategory !== undefined ? { settlementCategory: c.settlementCategory } : {}),
      });
      toast.success(t("branches.saved"));
      onClose();
    } catch (error) {
      setFormError(applyServerErrors(form, error, SERVER_FIELDS));
      throw error;
    }
  };

  const submit = form.handleSubmit(async (values) => {
    const c = changes(values);
    if (c.settlementCategory !== undefined || c.address !== undefined) {
      setConfirming(values);
      return;
    }
    await save(values).catch(() => undefined);
  });

  const pending = confirming ? changes(confirming) : null;

  return (
    <>
      <Dialog open={confirming === null} onOpenChange={(o) => (o ? undefined : onClose())}>
        <DialogContent size="md">
          <DialogHeader>
            <DialogTitle>{t("branches.editTitle", { name: branch.name })}</DialogTitle>
            <DialogDescription>{t("branches.editHint")}</DialogDescription>
          </DialogHeader>
          <form id="edit-branch" noValidate onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
            <RhfField
              control={form.control}
              name="name"
              label={t("branches.fields.name")}
              required
              render={({ field, control }) => <Input {...control} {...field} maxLength={100} />}
            />
            <RhfField
              control={form.control}
              name="address"
              label={t("branches.fields.address")}
              optional
              render={({ field, control }) => <Input {...control} {...field} maxLength={200} />}
            />
            <SettlementCategoryField control={form.control} showDefaultHint={false} />
            {formError ? (
              <Banner tone="destructive" icon={TriangleAlert} live="assertive">
                {formError}
              </Banner>
            ) : null}
          </form>
          <DialogFooter>
            <Button variant="secondary" onClick={onClose}>
              {tc("actions.cancel")}
            </Button>
            <Button
              type="submit"
              form="edit-branch"
              disabled={!online || !form.formState.isDirty || form.formState.isSubmitting}
            >
              {tc("actions.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {confirming && pending ? (
        <ConfirmDialog
          open
          onOpenChange={(o) => (o ? undefined : setConfirming(null))}
          title={t("branches.confirmEdit.title")}
          confirmLabel={tc("actions.save")}
          onConfirm={() => save(confirming)}
          error={formError}
        >
          <div className="flex flex-col gap-2">
            {pending.settlementCategory !== undefined ? (
              <Banner tone="info" icon={Info}>
                {t("branches.confirmEdit.category", {
                  category: t(`branches.category.${pending.settlementCategory}`),
                  date: formatDate(currentMonthStart()),
                })}
              </Banner>
            ) : null}
            {pending.address !== undefined ? (
              <Banner tone="warning" icon={TriangleAlert}>
                {t("branches.confirmEdit.address")}
              </Banner>
            ) : null}
          </div>
        </ConfirmDialog>
      ) : null}
    </>
  );
}

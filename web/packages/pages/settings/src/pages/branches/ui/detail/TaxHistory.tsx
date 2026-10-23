import { useUnit } from "effector-react";
import { CalendarPlus, History, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate } from "@shared/lib/date";
import {
  Banner,
  Button,
  Card,
  DataTable,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  EmptyState,
  FormField,
  Icon,
  Input,
  NativeSelect,
  toast,
  type DataTableColumn,
} from "@shared/ui";
import { Controller, RhfField, useZodForm, z } from "@shared/ui/form";

import { errorText } from "#/shared/lib/errors.ts";
import { applyServerErrors } from "#/shared/lib/form.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $taxSettings,
  $taxSettingsError,
  branchDataReloadRequested,
  createTaxSettingFx,
  currentMonthValue,
  fetchTaxSettingsFx,
  isPastMonth,
  monthToValidFrom,
  type Branch,
  type TaxSetting,
} from "../../model/index.ts";
import { SettlementCategoryField } from "../form/BranchDialogs.tsx";

/** «Aholi punkti toifasi» history (20 #34) + a future-dated row (20 #35, no past months). */
export function TaxHistory({ branch, canEdit }: { branch: Branch; canEdit: boolean }) {
  const { t } = useTranslation("settings");
  const [rows, error, loading, reload] = useUnit([
    $taxSettings,
    $taxSettingsError,
    fetchTaxSettingsFx.pending,
    branchDataReloadRequested,
  ]);
  const online = useOnline();
  const [adding, setAdding] = useState(false);

  const columns: DataTableColumn<TaxSetting>[] = [
    {
      id: "from",
      header: t("branches.tax.validFrom"),
      cell: (r) => formatDate(r.valid_from),
      width: "140px",
    },
    {
      id: "category",
      header: t("branches.fields.settlementCategory"),
      cell: (r) => t(`branches.category.${r.settlement_category}`),
    },
    {
      id: "activity",
      header: t("branches.tax.activityType"),
      cell: (r) => t(`branches.activity.${r.activity_type}`),
      width: "170px",
    },
  ];

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[15px] font-bold">{t("branches.tax.title")}</h2>
        {canEdit ? (
          <Button size="sm" variant="secondary" disabled={!online} onClick={() => setAdding(true)}>
            <Icon as={CalendarPlus} size="sm" />
            {t("branches.tax.add")}
          </Button>
        ) : null}
      </div>
      <p className="text-small text-foreground-secondary">{t("branches.tax.hint")}</p>
      <DataTable
        label={t("branches.tax.title")}
        columns={columns}
        data={rows}
        getRowId={(r) => r.valid_from}
        status={error ? "error" : loading && rows.length === 0 ? "loading" : "idle"}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={reload}
        minWidth={480}
        skeletonRows={2}
        empty={<EmptyState icon={History} title={t("branches.tax.empty")} />}
      />
      {adding ? <AddTaxSettingDialog branch={branch} onClose={() => setAdding(false)} /> : null}
    </Card>
  );
}

const schema = z.object({
  month: z.string().regex(/^\d{4}-\d{2}$/),
  settlementCategory: z.enum(["city_100k_plus", "other", "remote_mountain"]),
  activityType: z.enum(["retail", "other"]),
});

function AddTaxSettingDialog({ branch, onClose }: { branch: Branch; onClose: () => void }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const create = useUnit(createTaxSettingFx);
  const online = useOnline();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useZodForm(schema, {
    defaultValues: {
      month: currentMonthValue(),
      settlementCategory: branch.settlement_category,
      activityType: branch.activity_type,
    },
  });

  const submit = form.handleSubmit(async (values) => {
    setFormError(null);
    if (isPastMonth(values.month)) {
      form.setError("month", { type: "client", message: "validation.past_period" });
      return;
    }
    try {
      await create({
        branchId: branch.id,
        validFrom: monthToValidFrom(values.month),
        settlementCategory: values.settlementCategory,
        activityType: values.activityType,
      });
      toast.success(t("branches.tax.added"));
      onClose();
    } catch (error) {
      setFormError(
        applyServerErrors(form, error, {
          valid_from: "month",
          settlement_category: "settlementCategory",
          activity_type: "activityType",
        }),
      );
    }
  });

  return (
    <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent size="md">
        <DialogHeader>
          <DialogTitle>{t("branches.tax.addTitle", { name: branch.name })}</DialogTitle>
          <DialogDescription>{t("branches.tax.addHint")}</DialogDescription>
        </DialogHeader>
        <form
          id="add-tax-setting"
          noValidate
          onSubmit={(e) => void submit(e)}
          className="flex flex-col gap-4"
        >
          <RhfField
            control={form.control}
            name="month"
            label={t("branches.tax.validFromMonth")}
            required
            render={({ field, control }) => (
              <Input {...control} {...field} type="month" min={currentMonthValue()} />
            )}
          />
          <SettlementCategoryField control={form.control} showDefaultHint={false} />
          <Controller
            control={form.control}
            name="activityType"
            render={({ field }) => (
              <FormField label={t("branches.tax.activityType")} required>
                <NativeSelect
                  options={[
                    { value: "retail", label: t("branches.activity.retail") },
                    { value: "other", label: t("branches.activity.other") },
                  ]}
                  value={field.value}
                  onChange={(e) => field.onChange(e.target.value)}
                  wrapperClassName="w-full"
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
          <Button type="submit" form="add-tax-setting" disabled={!online || form.formState.isSubmitting}>
            {tc("actions.add")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

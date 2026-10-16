import { useUnit } from "effector-react";
import { Archive, CreditCard, Monitor, Pencil, Plus, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { toApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { formatDate } from "@shared/lib/date";
import {
  Banner,
  Button,
  Card,
  Checkbox,
  ConfirmDialog,
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
  SegmentedControl,
  StatusChip,
  buttonVariants,
  toast,
  type DataTableColumn,
  type DataTableRowAction,
} from "@shared/ui";
import { Controller, RhfField, useZodForm, z } from "@shared/ui/form";

import { errorText } from "#/shared/lib/errors.ts";
import { applyServerErrors } from "#/shared/lib/form.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $cashRegisters,
  $cashRegistersError,
  $includeArchived,
  archiveCashRegisterFx,
  branchDataReloadRequested,
  createCashRegisterFx,
  fetchCashRegistersFx,
  includeArchivedToggled,
  renameCashRegisterFx,
  type Branch,
  type CashRegister,
  type CashRegisterKind,
} from "../../model/index.ts";
import { fmTone, ofdTone } from "../labels.ts";

/**
 * «Kassalar» of a branch (07 BO-12, 20 #38–#40i): tax registration, fiscal module, fiscal agent
 * (agents arrive in Bosqich 5 — cloud fiscal shown), card terminal (qaror #71, later stage), archive.
 * Adding over the plan limit → ADDON_REQUIRED → offer of an extra register in BO-19.
 */
export function CashRegisters({ branch, canManage }: { branch: Branch; canManage: boolean }) {
  const { t } = useTranslation("settings");
  const [registers, error, loading, includeArchived, toggleArchived, reload] = useUnit([
    $cashRegisters,
    $cashRegistersError,
    fetchCashRegistersFx.pending,
    $includeArchived,
    includeArchivedToggled,
    branchDataReloadRequested,
  ]);
  const online = useOnline();
  const [adding, setAdding] = useState(false);
  const [renaming, setRenaming] = useState<CashRegister | null>(null);
  const [archiving, setArchiving] = useState<CashRegister | null>(null);

  const columns: DataTableColumn<CashRegister>[] = [
    {
      id: "name",
      header: t("branches.registers.name"),
      cell: (r) => (
        <div className="min-w-0">
          <p className="text-[14px] font-bold">{r.name}</p>
          <p className="text-[12px] text-muted-foreground">{t(`branches.registers.kind.${r.kind}`)}</p>
        </div>
      ),
    },
    {
      id: "tax",
      header: t("branches.registers.taxRegistration"),
      cell: (r) => (
        <div className="flex flex-col items-start gap-1">
          <StatusChip tone={ofdTone(r.ofd_status)}>{t(`branches.registers.ofd.${r.ofd_status}`)}</StatusChip>
          <span className="text-[12px] text-muted-foreground">
            {r.tax_registered_at ? formatDate(r.tax_registered_at) : t("branches.registers.notRegistered")}
            {r.txkm_contract_ref ? ` · ${r.txkm_contract_ref}` : ""}
          </span>
        </div>
      ),
    },
    {
      id: "fm",
      header: t("branches.registers.fiscalModule"),
      width: "150px",
      cell: (r) => (
        <StatusChip tone={fmTone(r.fm_state)}>{t(`branches.registers.fm.${r.fm_state}`)}</StatusChip>
      ),
    },
    {
      id: "agent",
      header: t("branches.registers.fiscalAgent"),
      cell: (r) => (
        <span className="text-[13px]">
          {r.fiscal_agent_id ? t("branches.registers.agentLinked") : t("branches.registers.cloudFiscal")}
        </span>
      ),
    },
    {
      id: "terminal",
      header: t("branches.registers.cardTerminal"),
      cell: () => (
        <div className="flex flex-col items-start gap-1">
          <span className="flex items-center gap-1.5 text-[13px]">
            <Icon as={CreditCard} size="sm" className="text-muted-foreground" />
            {t("branches.registers.noTerminal")}
          </span>
          <span className="text-[11px] text-muted-foreground">{t("branches.registers.terminalLater")}</span>
        </div>
      ),
    },
    {
      id: "archived",
      header: t("branches.registers.status"),
      width: "130px",
      cell: (r) =>
        r.archived_at ? (
          <StatusChip tone="neutral">{t("branches.registers.archived")}</StatusChip>
        ) : (
          <StatusChip tone="success" dot>
            {t("branches.registers.active")}
          </StatusChip>
        ),
    },
  ];

  const rowActions = (r: CashRegister): DataTableRowAction<CashRegister>[] =>
    canManage && online && !r.archived_at
      ? [
          { id: "rename", label: t("branches.registers.rename"), icon: Pencil, onSelect: setRenaming },
          {
            id: "archive",
            label: t("branches.registers.archive"),
            icon: Archive,
            destructive: true,
            onSelect: setArchiving,
          },
        ]
      : [];

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-[15px] font-bold">{t("branches.registers.title")}</h2>
        <label className="flex items-center gap-2 text-[13px] font-semibold text-foreground-secondary">
          <Checkbox checked={includeArchived} onCheckedChange={(c) => toggleArchived(c === true)} />
          {t("branches.registers.showArchived")}
        </label>
        <div className="grow" />
        {canManage ? (
          <Button size="sm" variant="secondary" disabled={!online} onClick={() => setAdding(true)}>
            <Icon as={Plus} size="sm" />
            {t("branches.registers.add")}
          </Button>
        ) : null}
      </div>
      <DataTable
        label={t("branches.registers.title")}
        columns={columns}
        data={registers}
        getRowId={(r) => r.id}
        status={error ? "error" : loading && registers.length === 0 ? "loading" : "idle"}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={reload}
        rowActions={rowActions}
        minWidth={900}
        skeletonRows={2}
        empty={<EmptyState icon={Monitor} title={t("branches.registers.empty")} />}
      />
      <p className="text-[12px] text-muted-foreground">{t("branches.registers.footnote")}</p>
      {adding ? <AddRegisterDialog branch={branch} onClose={() => setAdding(false)} /> : null}
      {renaming ? <RenameRegisterDialog register={renaming} onClose={() => setRenaming(null)} /> : null}
      {archiving ? <ArchiveRegisterDialog register={archiving} onClose={() => setArchiving(null)} /> : null}
    </Card>
  );
}

const addSchema = z.object({
  name: z.string().trim().min(1).max(100),
  kind: z.enum(["web", "android"]),
});

function AddRegisterDialog({ branch, onClose }: { branch: Branch; onClose: () => void }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const create = useUnit(createCashRegisterFx);
  const online = useOnline();
  const [formError, setFormError] = useState<string | null>(null);
  const [addonRequired, setAddonRequired] = useState(false);
  const form = useZodForm(addSchema, { defaultValues: { name: "", kind: "web" } });

  const submit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await create({ branchId: branch.id, name: values.name, kind: values.kind });
      toast.success(t("branches.registers.added", { name: values.name.trim() }));
      onClose();
    } catch (error) {
      if (toApiError(error).code === "ADDON_REQUIRED") {
        setAddonRequired(true);
        return;
      }
      setFormError(applyServerErrors(form, error));
    }
  });

  if (addonRequired) {
    return (
      <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
        <DialogContent size="sm" role="alertdialog">
          <DialogHeader>
            <DialogTitle>{t("branches.registers.addon.title")}</DialogTitle>
            <DialogDescription>{t("branches.registers.addon.description")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="secondary" onClick={onClose}>
              {tc("actions.cancel")}
            </Button>
            <Link to="/app/billing" className={buttonVariants({ variant: "default" })}>
              {t("branches.registers.addon.goToBilling")}
            </Link>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>{t("branches.registers.addTitle", { branch: branch.name })}</DialogTitle>
          <DialogDescription>{t("branches.registers.addHint")}</DialogDescription>
        </DialogHeader>
        <form id="add-register" noValidate onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
          <RhfField
            control={form.control}
            name="name"
            label={t("branches.registers.name")}
            required
            render={({ field, control }) => <Input {...control} {...field} maxLength={100} />}
          />
          <Controller
            control={form.control}
            name="kind"
            render={({ field }) => (
              <FormField label={t("branches.registers.kindLabel")} required>
                <SegmentedControl<CashRegisterKind>
                  label={t("branches.registers.kindLabel")}
                  value={field.value}
                  onChange={field.onChange}
                  options={[
                    { value: "web", label: t("branches.registers.kind.web") },
                    { value: "android", label: t("branches.registers.kind.android") },
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
          <Button type="submit" form="add-register" disabled={!online || form.formState.isSubmitting}>
            {tc("actions.add")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const renameSchema = z.object({ name: z.string().trim().min(1).max(100) });

function RenameRegisterDialog({ register, onClose }: { register: CashRegister; onClose: () => void }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const rename = useUnit(renameCashRegisterFx);
  const online = useOnline();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useZodForm(renameSchema, { defaultValues: { name: register.name } });

  const submit = form.handleSubmit(async ({ name }) => {
    setFormError(null);
    try {
      await rename({ registerId: register.id, name, version: register.version });
      toast.success(t("branches.registers.renamed"));
      onClose();
    } catch (error) {
      setFormError(applyServerErrors(form, error));
    }
  });

  return (
    <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>{t("branches.registers.renameTitle")}</DialogTitle>
        </DialogHeader>
        <form
          id="rename-register"
          noValidate
          onSubmit={(e) => void submit(e)}
          className="flex flex-col gap-4"
        >
          <RhfField
            control={form.control}
            name="name"
            label={t("branches.registers.name")}
            required
            render={({ field, control }) => <Input {...control} {...field} maxLength={100} />}
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
          <Button
            type="submit"
            form="rename-register"
            disabled={!online || !form.formState.isDirty || form.formState.isSubmitting}
          >
            {tc("actions.save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ArchiveRegisterDialog({ register, onClose }: { register: CashRegister; onClose: () => void }) {
  const { t } = useTranslation("settings");
  const archive = useUnit(archiveCashRegisterFx);
  const [error, setError] = useState<string | null>(null);
  return (
    <ConfirmDialog
      open
      onOpenChange={(o) => (o ? undefined : onClose())}
      title={t("branches.registers.archiveTitle", { name: register.name })}
      description={t("branches.registers.archiveHint")}
      confirmLabel={t("branches.registers.archive")}
      tone="destructive"
      error={error}
      onConfirm={async () => {
        setError(null);
        try {
          await archive(register.id);
          toast.success(t("branches.registers.archivedToast", { name: register.name }));
        } catch (e) {
          setError(errorText(e));
          throw e;
        }
      }}
    />
  );
}

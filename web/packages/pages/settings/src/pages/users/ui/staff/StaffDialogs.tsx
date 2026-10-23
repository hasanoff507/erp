import { useUnit } from "effector-react";
import { Send, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { useTranslation } from "@shared/i18n";
import { toE164 } from "@shared/lib/phone";
import { $activeBranchId } from "@shared/state/session";
import {
  Banner,
  Button,
  CheckboxList,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Icon,
  Input,
  PhoneInput,
  toast,
  type CheckboxOption,
} from "@shared/ui";
import {
  RhfField,
  useZodForm,
  z,
  zPhone,
  type Control,
  type FieldPath,
  type FieldValues,
} from "@shared/ui/form";

import { applyServerErrors } from "#/shared/lib/form.ts";
import { isOwnerRole } from "#/shared/lib/roles.ts";
import { useOnline, useRoleName } from "#/shared/ui/hooks.ts";

import { $branches, $roles, createStaffFx, staffName, updateStaffFx, type Staff } from "../../model/index.ts";

const SERVER_FIELDS = { role_ids: "roleIds", branch_ids: "branchIds" } as const;

function useRoleOptions(current: readonly string[] = []): CheckboxOption[] {
  const roles = useUnit($roles);
  const roleName = useRoleName();
  // The owner role is never assignable here (14 §18.2); a user who already has it keeps it, disabled.
  return roles
    .filter((r) => !isOwnerRole(r) || current.includes(r.id))
    .map((r) => ({ value: r.id, label: roleName(r), disabled: isOwnerRole(r) }));
}

function useBranchOptions(): CheckboxOption[] {
  const branches = useUnit($branches);
  return branches.map((b) => ({ value: b.id, label: b.name }));
}

const createSchema = z.object({
  phone: zPhone(),
  name: z.string().trim().min(2).max(100),
  roleIds: z.array(z.string()).min(1),
  branchIds: z.array(z.string()).min(1),
});

/** BO-11 "+ Xodim qo'shish" (07): phone, full name, role(s), branch(es) → invite code (qaror #34). */
export function CreateStaffDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  return open ? <CreateStaffForm onClose={() => onOpenChange(false)} /> : null;
}

function CreateStaffForm({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const [branches, activeBranchId] = useUnit([$branches, $activeBranchId]);
  const roleOptions = useRoleOptions();
  const branchOptions = useBranchOptions();
  const online = useOnline();
  const create = useUnit(createStaffFx);
  const [formError, setFormError] = useState<string | null>(null);

  // 07 `branchIds` default: the current branch (or the only one).
  const defaultBranches = useMemo(() => {
    const current = branches.find((b) => b.id === activeBranchId);
    if (current) return [current.id];
    return branches.length === 1 && branches[0] ? [branches[0].id] : [];
  }, [branches, activeBranchId]);

  const form = useZodForm(createSchema, {
    defaultValues: { phone: "", name: "", roleIds: [], branchIds: defaultBranches },
  });

  const submit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      const created = await create({
        phone: toE164(values.phone),
        name: values.name,
        roleIds: values.roleIds,
        branchIds: values.branchIds,
      });
      toast.success(t("users.invite.sentTitle"), t(`users.invite.sentVia.${created.channel_used}`));
      onClose();
    } catch (error) {
      setFormError(applyServerErrors(form, error, SERVER_FIELDS));
    }
  });

  return (
    <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent size="md">
        <DialogHeader>
          <DialogTitle>{t("users.invite.title")}</DialogTitle>
          <DialogDescription>{t("users.invite.description")}</DialogDescription>
        </DialogHeader>
        <form id="create-staff" noValidate onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <RhfField
              control={form.control}
              name="phone"
              label={t("users.fields.phone")}
              required
              render={({ field, control }) => (
                <PhoneInput
                  {...control}
                  ref={field.ref}
                  name={field.name}
                  value={field.value}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                />
              )}
            />
            <RhfField
              control={form.control}
              name="name"
              label={t("users.fields.fullName")}
              required
              render={({ field, control }) => (
                <Input {...control} {...field} maxLength={100} autoComplete="off" />
              )}
            />
          </div>
          <RolesBranchesFields
            control={form.control}
            roleOptions={roleOptions}
            branchOptions={branchOptions}
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
          <Button type="submit" form="create-staff" disabled={!online || form.formState.isSubmitting}>
            <Icon as={Send} size="sm" />
            {t("users.invite.submit")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const editSchema = z.object({
  roleIds: z.array(z.string()).min(1),
  branchIds: z.array(z.string()).min(1),
});

/** "Tahrirlash": roles and branches only (limits live on roles — 07 BO-11). */
export function EditStaffDialog({ staff, onClose }: { staff: Staff | null; onClose: () => void }) {
  return staff ? <EditStaffForm key={staff.user_id} staff={staff} onClose={onClose} /> : null;
}

function EditStaffForm({ staff, onClose }: { staff: Staff; onClose: () => void }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const roleOptions = useRoleOptions(staff.role_ids);
  const branchOptions = useBranchOptions();
  const online = useOnline();
  const update = useUnit(updateStaffFx);
  const [formError, setFormError] = useState<string | null>(null);
  const form = useZodForm(editSchema, {
    defaultValues: { roleIds: [...staff.role_ids], branchIds: [...staff.branch_ids] },
  });

  const submit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await update({ userId: staff.user_id, roleIds: values.roleIds, branchIds: values.branchIds });
      toast.success(t("users.edit.saved"));
      onClose();
    } catch (error) {
      setFormError(applyServerErrors(form, error, SERVER_FIELDS));
    }
  });

  return (
    <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent size="md">
        <DialogHeader>
          <DialogTitle>{t("users.edit.title", { name: staffName(staff) })}</DialogTitle>
          <DialogDescription>{t("users.edit.description")}</DialogDescription>
        </DialogHeader>
        <form id="edit-staff" noValidate onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
          <RolesBranchesFields
            control={form.control}
            roleOptions={roleOptions}
            branchOptions={branchOptions}
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
            form="edit-staff"
            disabled={!online || !form.formState.isDirty || form.formState.isSubmitting}
          >
            {tc("actions.save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface RolesBranchesValues extends FieldValues {
  roleIds: string[];
  branchIds: string[];
}

function RolesBranchesFields<T extends RolesBranchesValues>({
  control: formControl,
  roleOptions,
  branchOptions,
}: {
  control: Control<T>;
  roleOptions: CheckboxOption[];
  branchOptions: CheckboxOption[];
}) {
  const { t } = useTranslation("settings");
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <RhfField
        control={formControl}
        name={"roleIds" as FieldPath<T>}
        label={t("users.fields.roles")}
        hideLabel
        required
        render={({ field, control }) => (
          <CheckboxList
            aria-invalid={control["aria-invalid"]}
            aria-describedby={control["aria-describedby"]}
            legend={`${t("users.fields.roles")} *`}
            options={roleOptions}
            value={field.value as string[]}
            onChange={field.onChange}
          />
        )}
      />
      <RhfField
        control={formControl}
        name={"branchIds" as FieldPath<T>}
        label={t("users.fields.branches")}
        hideLabel
        required
        render={({ field, control }) => (
          <CheckboxList
            aria-invalid={control["aria-invalid"]}
            aria-describedby={control["aria-describedby"]}
            legend={`${t("users.fields.branches")} *`}
            options={branchOptions}
            value={field.value as string[]}
            onChange={field.onChange}
            selectAll={branchOptions.length > 1}
          />
        )}
      />
    </div>
  );
}

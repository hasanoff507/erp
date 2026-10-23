import { useUnit } from "effector-react";
import { Lock, Plus, ShieldCheck, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useTranslation } from "@shared/i18n";
import {
  Banner,
  Button,
  Card,
  Checkbox,
  DecimalInput,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  EmptyState,
  ErrorState,
  FormField,
  Icon,
  Input,
  Skeleton,
  StatusChip,
  cn,
  toast,
} from "@shared/ui";
import { RhfField, useZodForm, z } from "@shared/ui/form";

import { errorText } from "#/shared/lib/errors.ts";
import { applyServerErrors } from "#/shared/lib/form.ts";
import { moduleLabel, permissionLabel, primaryModule } from "#/shared/lib/permissions.ts";
import { isOwnerRole, limitUnitOf } from "#/shared/lib/roles.ts";
import { useOnline, useRoleName } from "#/shared/ui/hooks.ts";

import {
  $catalog,
  $catalogError,
  $limitCodes,
  $rolePermissions,
  $rolePermissionsError,
  $roles,
  $rolesError,
  $selectedRole,
  createRoleFx,
  fetchCatalogFx,
  fetchRolePermissionsFx,
  renameRoleFx,
  replaceRolePermissionsFx,
  roleSelected,
  rolesTabOpened,
  sameDraft,
  toDraft,
  type CatalogItem,
  type PermissionsDraftRow,
  type Role,
} from "../../model/index.ts";

/**
 * BO-11 «Rollar» (07, 20 #24–#29): roles list, custom role create/rename (system role names are
 * read-only), permission + limit editor from `GET /permissions-catalog`. Limits are on the ROLE;
 * the unit is fixed per code (15 §2.1: `discount.*`, `prices.approve` — %, others — so'm).
 */
export function RolesTab() {
  const { t } = useTranslation("settings");
  const [roles, rolesError, selected, select, opened] = useUnit([
    $roles,
    $rolesError,
    $selectedRole,
    roleSelected,
    rolesTabOpened,
  ]);
  const roleName = useRoleName();
  const online = useOnline();
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    opened();
  }, [opened]);

  if (rolesError) return <ErrorState message={errorText(rolesError)} />;

  return (
    <div className="flex flex-col gap-3.5 lg:flex-row lg:items-start">
      <Card className="flex w-full flex-col gap-2 lg:w-[280px] lg:shrink-0">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-[15px] font-bold">{t("roles.listTitle")}</h2>
          <Button size="sm" variant="secondary" disabled={!online} onClick={() => setCreating(true)}>
            <Icon as={Plus} size="sm" />
            {t("roles.create")}
          </Button>
        </div>
        <ul className="flex flex-col gap-1" aria-label={t("roles.listTitle")}>
          {roles.map((role) => (
            <li key={role.id}>
              <button
                type="button"
                aria-current={selected?.id === role.id ? "true" : undefined}
                onClick={() => select(role.id)}
                className={cn(
                  "flex w-full items-center justify-between gap-2 rounded-md px-3 py-2.5 text-left text-[14px] font-semibold",
                  "hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  selected?.id === role.id && "bg-primary-soft text-primary-strong",
                )}
              >
                <span className="truncate">{roleName(role)}</span>
                {role.is_system ? (
                  <span className="text-[11px] font-bold uppercase text-muted-foreground">
                    {t("roles.system")}
                  </span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      </Card>
      <div className="min-w-0 flex-1">
        {selected ? <RoleEditor key={selected.id} role={selected} /> : null}
      </div>
      <CreateRoleDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function RoleEditor({ role }: { role: Role }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const [catalog, catalogError, limitCodes, permissions, permissionsError, loading, reloadCatalog, reload] =
    useUnit([
      $catalog,
      $catalogError,
      $limitCodes,
      $rolePermissions,
      $rolePermissionsError,
      fetchRolePermissionsFx.pending,
      fetchCatalogFx,
      fetchRolePermissionsFx,
    ]);
  const [save, saving] = useUnit([replaceRolePermissionsFx, replaceRolePermissionsFx.pending]);
  const roleName = useRoleName();
  const online = useOnline();
  const readOnly = isOwnerRole(role);

  const server = useMemo(() => toDraft(permissions), [permissions]);
  // `null` = no local edits: the editor shows the server state (also after a reload / save).
  const [edited, setEdited] = useState<PermissionsDraftRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const draft = edited ?? server;
  const setDraft = (update: (rows: PermissionsDraftRow[]) => PermissionsDraftRow[]) =>
    setEdited((rows) => update(rows ?? server));

  const groups = useMemo(() => {
    const map = new Map<string, CatalogItem[]>();
    for (const item of catalog) {
      const module = primaryModule(item.module);
      const list = map.get(module) ?? [];
      list.push(item);
      map.set(module, list);
    }
    return [...map.entries()];
  }, [catalog]);

  if (catalogError)
    return (
      <ErrorState
        message={errorText(catalogError)}
        onRetry={() => void reloadCatalog().catch(() => undefined)}
      />
    );
  if (permissionsError) {
    return (
      <ErrorState
        message={errorText(permissionsError)}
        onRetry={() => void reload(role.id).catch(() => undefined)}
      />
    );
  }

  const byCode = new Map(draft.map((r) => [r.code, r]));
  const dirty = !sameDraft(draft, server);

  const toggle = (code: string, checked: boolean) => {
    setDraft((rows) => (checked ? [...rows, { code, limit: "" }] : rows.filter((r) => r.code !== code)));
  };
  const setLimit = (code: string, limit: string) => {
    setDraft((rows) => rows.map((r) => (r.code === code ? { ...r, limit } : r)));
  };

  const onSave = async () => {
    setError(null);
    try {
      await save({ roleId: role.id, rows: draft, limitCodes });
      setEdited(null);
      toast.success(t("roles.saved"), t("roles.savedHint"));
    } catch (e) {
      setError(errorText(e));
    }
  };

  return (
    <Card className="flex flex-col gap-4">
      <RoleNameRow role={role} />
      {readOnly ? (
        <Banner tone="info" icon={Lock}>
          {t("roles.ownerReadOnly")}
        </Banner>
      ) : (
        <p className="text-small text-foreground-secondary">{t("roles.editorHint")}</p>
      )}
      {loading && permissions.length === 0 ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : catalog.length === 0 ? (
        <EmptyState icon={ShieldCheck} title={t("roles.catalogEmpty")} />
      ) : (
        <div className="flex flex-col gap-4">
          {groups.map(([module, items]) => (
            <fieldset key={module} className="m-0 flex flex-col gap-1 border-0 p-0">
              <legend className="mb-1 p-0 text-caption uppercase text-muted-foreground">
                {moduleLabel(module)}
              </legend>
              {items.map((item) => {
                const row = byCode.get(item.code);
                const checked = row !== undefined;
                const unit = limitUnitOf(item.code);
                const checkboxId = `perm-${role.id}-${item.code}`;
                return (
                  <div
                    key={item.code}
                    className="flex flex-wrap items-center gap-3 rounded-md px-2 py-1.5 hover:bg-accent"
                  >
                    <Checkbox
                      id={checkboxId}
                      checked={checked}
                      disabled={readOnly || !online}
                      onCheckedChange={(c) => toggle(item.code, c === true)}
                    />
                    <label htmlFor={checkboxId} className="flex min-w-0 flex-1 flex-col">
                      <span className="text-[14px] font-semibold">{permissionLabel(item)}</span>
                      <span className="font-mono text-[12px] text-muted-foreground">{item.code}</span>
                    </label>
                    {item.requires_limit ? (
                      <FormField
                        label={t("roles.limitLabel", { code: item.code })}
                        hideLabel
                        hint={checked && row.limit === "" ? t("roles.unlimited") : undefined}
                        className="w-[170px]"
                      >
                        {(a11y) => (
                          <DecimalInput
                            {...a11y}
                            value={row?.limit ?? ""}
                            onChange={(v) => setLimit(item.code, v)}
                            precision={unit === "percent" ? 2 : 0}
                            outputScale={2}
                            suffix={unit === "percent" ? "%" : t("roles.som")}
                            placeholder={t("roles.limitPlaceholder")}
                            disabled={readOnly || !checked || !online}
                          />
                        )}
                      </FormField>
                    ) : null}
                  </div>
                );
              })}
            </fieldset>
          ))}
        </div>
      )}
      {error ? (
        <Banner tone="destructive" icon={TriangleAlert} live="assertive">
          {error}
        </Banner>
      ) : null}
      {readOnly ? null : (
        <div className="flex justify-end gap-2">
          <Button variant="secondary" disabled={!dirty || saving} onClick={() => setEdited(null)}>
            {tc("actions.cancel")}
          </Button>
          <Button disabled={!online || !dirty || saving} onClick={() => void onSave()}>
            {t("roles.savePermissions", { role: roleName(role) })}
          </Button>
        </div>
      )}
    </Card>
  );
}

const nameSchema = z.object({ name: z.string().trim().min(1).max(50) });

function RoleNameRow({ role }: { role: Role }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const roleName = useRoleName();
  const online = useOnline();
  const rename = useUnit(renameRoleFx);
  const form = useZodForm(nameSchema, { defaultValues: { name: role.name } });
  const [error, setError] = useState<string | null>(null);

  if (role.is_system) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-h2">{roleName(role)}</h2>
        <StatusChip tone="neutral" icon={Lock}>
          {t("roles.systemNameReadOnly")}
        </StatusChip>
      </div>
    );
  }

  const submit = form.handleSubmit(async ({ name }) => {
    setError(null);
    try {
      const renamed = await rename({ roleId: role.id, name, version: role.version });
      form.reset({ name: renamed.name });
      toast.success(t("roles.renamed"));
    } catch (e) {
      setError(applyServerErrors(form, e));
    }
  });

  return (
    <form noValidate onSubmit={(e) => void submit(e)} className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-2">
        <RhfField
          control={form.control}
          name="name"
          label={t("roles.name")}
          required
          className="min-w-[220px] flex-1"
          render={({ field, control }) => <Input {...control} {...field} maxLength={50} />}
        />
        <Button type="submit" variant="secondary" disabled={!online || !form.formState.isDirty}>
          {tc("actions.save")}
        </Button>
      </div>
      {error ? (
        <Banner tone="destructive" icon={TriangleAlert} live="assertive">
          {error}
        </Banner>
      ) : null}
    </form>
  );
}

function CreateRoleDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return open ? <CreateRoleForm onClose={onClose} /> : null;
}

function CreateRoleForm({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const create = useUnit(createRoleFx);
  const online = useOnline();
  const form = useZodForm(nameSchema, { defaultValues: { name: "" } });
  const [error, setError] = useState<string | null>(null);

  const submit = form.handleSubmit(async ({ name }) => {
    setError(null);
    try {
      await create(name);
      toast.success(t("roles.created"));
      onClose();
    } catch (e) {
      setError(applyServerErrors(form, e));
    }
  });

  return (
    <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>{t("roles.createTitle")}</DialogTitle>
          <DialogDescription>{t("roles.createHint")}</DialogDescription>
        </DialogHeader>
        <form id="create-role" noValidate onSubmit={(e) => void submit(e)} className="flex flex-col gap-3">
          <RhfField
            control={form.control}
            name="name"
            label={t("roles.name")}
            required
            render={({ field, control }) => <Input {...control} {...field} maxLength={50} />}
          />
          {error ? (
            <Banner tone="destructive" icon={TriangleAlert} live="assertive">
              {error}
            </Banner>
          ) : null}
        </form>
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button type="submit" form="create-role" disabled={!online || form.formState.isSubmitting}>
            {t("roles.create")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

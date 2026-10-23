/**
 * «Toifalar» tab (20 #45–#47): name, accounting account (9410/9420/9430/6410), system mark, archive state;
 * «Yangi toifa» (name ≤ 50 + account), rename, archive / restore (`PATCH {…, version}`; 94xx ↔ 6410 is
 * refused by the server — `validation.not_allowed`).
 */
import { useUnit } from "effector-react";
import { Archive, ArchiveRestore, Pencil, Plus, Tags } from "lucide-react";
import { useState } from "react";

import { toApiError } from "@shared/api";
import { serverErrorText, useTranslation } from "@shared/i18n";
import {
  Button,
  DataTable,
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  EmptyState,
  FormField,
  Icon,
  Input,
  SimpleSelect,
  StatusChip,
  type DataTableColumn,
  type DataTableRowAction,
} from "@shared/ui";

import {
  $categories,
  $categoriesStatus,
  CATEGORY_NAME_MAX,
  EXPENSE_ACCOUNTS,
  categoriesReloadRequested,
  createCategoryFx,
  updateCategoryFx,
  type Category,
  type ExpenseAccount,
} from "../../model/index.ts";

type Editing = { mode: "create" } | { mode: "rename"; category: Category };

function isAccount(v: string): v is ExpenseAccount {
  return (EXPENSE_ACCOUNTS as readonly string[]).includes(v);
}

export function CategoriesTab({ canAct, online }: { canAct: boolean; online: boolean }) {
  const { t } = useTranslation("finance");
  const [categories, status] = useUnit([$categories, $categoriesStatus]);
  const [reload, update] = useUnit([categoriesReloadRequested, updateCategoryFx]);
  const [editing, setEditing] = useState<Editing | null>(null);
  const [error, setError] = useState<string | null>(null);

  const columns: DataTableColumn<Category>[] = [
    {
      id: "name",
      header: t("expenses.categories.columns.name"),
      cell: (c) => <span className="font-semibold">{c.name}</span>,
    },
    {
      id: "account",
      header: t("expenses.categories.columns.account"),
      cell: (c) => `${c.default_account} — ${t(`accounts.${c.default_account}`)}`,
    },
    {
      id: "state",
      header: t("expenses.categories.columns.state"),
      width: "200px",
      cell: (c) => (
        <span className="flex flex-wrap gap-1.5">
          {c.is_system ? <StatusChip tone="info">{t("expenses.categories.system")}</StatusChip> : null}
          {c.archived_at ? <StatusChip tone="neutral">{t("expenses.categories.archived")}</StatusChip> : null}
        </span>
      ),
    },
  ];

  const toggleArchive = (c: Category) => {
    setError(null);
    update({ id: c.id, body: { archived: c.archived_at === null, version: c.version } }).catch((e: unknown) =>
      setError(serverErrorText(toApiError(e))),
    );
  };

  const actions = (c: Category): DataTableRowAction<Category>[] => [
    {
      id: "rename",
      label: t("expenses.categories.rename"),
      icon: Pencil,
      onSelect: (row) => setEditing({ mode: "rename", category: row }),
    },
    c.archived_at === null
      ? { id: "archive", label: t("expenses.categories.archive"), icon: Archive, onSelect: toggleArchive }
      : {
          id: "restore",
          label: t("expenses.categories.restore"),
          icon: ArchiveRestore,
          onSelect: toggleArchive,
        },
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="min-w-0 flex-1 text-small text-foreground-secondary">
          {t("expenses.categories.subtitle")}
        </p>
        {canAct ? (
          <Button disabled={!online} onClick={() => setEditing({ mode: "create" })}>
            <Icon as={Plus} size="sm" />
            {t("expenses.categories.create")}
          </Button>
        ) : null}
      </div>
      {error ? <p className="text-small text-destructive">{error}</p> : null}
      <DataTable
        label={t("expenses.categories.title")}
        columns={columns}
        data={categories}
        getRowId={(c) => c.id}
        status={status}
        onRetry={reload}
        rowActions={canAct && online ? actions : undefined}
        minWidth={640}
        skeletonRows={4}
        empty={<EmptyState icon={Tags} title={t("expenses.categories.empty")} />}
      />
      {editing ? <CategoryDialog editing={editing} onClose={() => setEditing(null)} /> : null}
    </div>
  );
}

function CategoryDialog({ editing, onClose }: { editing: Editing; onClose: () => void }) {
  const { t } = useTranslation("finance");
  const [create, update, creating, updating] = useUnit([
    createCategoryFx,
    updateCategoryFx,
    createCategoryFx.pending,
    updateCategoryFx.pending,
  ]);
  const initial = editing.mode === "rename" ? editing.category : null;
  const [name, setName] = useState(initial?.name ?? "");
  const [account, setAccount] = useState<ExpenseAccount>(initial?.default_account ?? "9410");
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);
  const empty = name.trim() === "";

  const submit = async () => {
    setTouched(true);
    if (empty) return;
    setError(null);
    try {
      if (initial) await update({ id: initial.id, body: { name: name.trim(), version: initial.version } });
      else await create({ name: name.trim(), default_account: account });
      onClose();
    } catch (e) {
      setError(serverErrorText(toApiError(e)));
    }
  };

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {initial ? t("expenses.categories.renameTitle") : t("expenses.categories.createTitle")}
          </DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <FormField
            label={t("expenses.categories.name")}
            required
            error={touched && empty ? "validation.required" : null}
          >
            <Input
              value={name}
              maxLength={CATEGORY_NAME_MAX}
              data-testid="category-name"
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => (e.key === "Enter" ? void submit() : undefined)}
            />
          </FormField>
          {initial ? null : (
            <FormField label={t("expenses.categories.account")} required>
              <SimpleSelect
                options={EXPENSE_ACCOUNTS.map((a) => ({ value: a, label: `${a} — ${t(`accounts.${a}`)}` }))}
                value={account}
                onValueChange={(v) => (isAccount(v) ? setAccount(v) : undefined)}
              />
            </FormField>
          )}
          {error ? <p className="text-small text-destructive">{error}</p> : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t("shared.back")}
          </Button>
          <Button disabled={creating || updating} onClick={() => void submit()}>
            {t("shared.save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

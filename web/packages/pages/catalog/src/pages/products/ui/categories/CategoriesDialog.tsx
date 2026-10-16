/**
 * Minimal category management (19 §2): list, create (name + parent), rename (version), archive
 * (409 CATEGORY_HAS_PRODUCTS / validation.category_has_children). 07 has no dedicated category screen,
 * so it lives in a dialog of the product list.
 */
import { Archive, Check, Pencil, Plus, X } from "lucide-react";
import { useUnit } from "effector-react";
import { useState } from "react";

import type { ApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import type { CategoryOut } from "@shared/models";
import {
  Banner,
  Button,
  ConfirmDialog,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  FormField,
  Icon,
  Input,
  SimpleSelect,
  toast,
} from "@shared/ui";

import { $categories, $categoryNames } from "#/entities/product/index.ts";
import { apiErrorText } from "#/shared/lib/messages.ts";

import { archiveCategoryFx, createCategoryFx, updateCategoryFx } from "../../model/index.ts";

const ROOT = "root";

export function CategoriesDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation("catalog");
  const [categories, names, create, creating] = useUnit([
    $categories,
    $categoryNames,
    createCategoryFx,
    createCategoryFx.pending,
  ]);
  const [name, setName] = useState("");
  const [parent, setParent] = useState(ROOT);
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    if (name.trim() === "") {
      setError("validation.required");
      return;
    }
    create({ name: name.trim(), parent_id: parent === ROOT ? null : parent })
      .then(() => {
        setName("");
        setError(null);
        toast.success(t("categories.created"));
      })
      .catch((e: ApiError) => setError(apiErrorText(e)));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="md">
        <DialogHeader>
          <DialogTitle>{t("categories.title")}</DialogTitle>
          <DialogDescription>{t("categories.description")}</DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <FormField label={t("categories.name")} required error={error} className="flex-1">
            <Input
              value={name}
              maxLength={255}
              onChange={(e) => {
                setName(e.target.value);
                setError(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  submit();
                }
              }}
            />
          </FormField>
          <FormField label={t("categories.parent")} className="sm:w-48">
            <SimpleSelect
              options={[
                { value: ROOT, label: t("categories.root") },
                ...categories.map((c) => ({ value: c.id, label: c.name })),
              ]}
              value={parent}
              onValueChange={setParent}
            />
          </FormField>
          <Button onClick={submit} disabled={creating}>
            <Icon as={Plus} size="sm" />
            {t("categories.add")}
          </Button>
        </div>

        {categories.length === 0 ? (
          <p className="py-6 text-center text-small text-muted-foreground">{t("categories.empty")}</p>
        ) : (
          <ul
            className="flex max-h-[45vh] flex-col divide-y divide-divider overflow-y-auto rounded-lg border border-border"
            aria-label={t("categories.title")}
          >
            {categories.map((c) => (
              <CategoryRow
                key={c.id}
                category={c}
                parentName={c.parent_id ? names.get(c.parent_id) : undefined}
              />
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}

function CategoryRow({ category, parentName }: { category: CategoryOut; parentName?: string }) {
  const { t } = useTranslation("catalog");
  const [update, archive, archiving] = useUnit([
    updateCategoryFx,
    archiveCategoryFx,
    archiveCategoryFx.pending,
  ]);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(category.name);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);

  const save = () => {
    if (name.trim() === "") {
      setError("validation.required");
      return;
    }
    update({ id: category.id, body: { name: name.trim(), version: category.version } })
      .then(() => {
        setEditing(false);
        setError(null);
      })
      .catch((e: ApiError) => setError(apiErrorText(e)));
  };

  return (
    <li className="flex flex-col gap-1 px-3.5 py-2.5">
      {editing ? (
        <div className="flex items-end gap-2">
          <FormField label={t("categories.name")} hideLabel error={error} className="flex-1">
            <Input value={name} maxLength={255} onChange={(e) => setName(e.target.value)} autoFocus />
          </FormField>
          <Button size="sm" className="h-11 w-11 px-0" aria-label={t("categories.save")} onClick={save}>
            <Icon as={Check} size="sm" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-11 w-11 px-0"
            aria-label={t("categories.cancel")}
            onClick={() => {
              setEditing(false);
              setName(category.name);
              setError(null);
            }}
          >
            <Icon as={X} size="sm" />
          </Button>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <span className="min-w-0 flex-1">
            <span className="block truncate font-semibold">{category.name}</span>
            {parentName ? <span className="text-[12px] text-muted-foreground">{parentName}</span> : null}
          </span>
          <Button
            size="sm"
            variant="ghost"
            className="h-9 w-9 px-0"
            aria-label={t("categories.rename", { name: category.name })}
            onClick={() => setEditing(true)}
          >
            <Icon as={Pencil} size="sm" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-9 w-9 px-0"
            aria-label={t("categories.archive", { name: category.name })}
            onClick={() => {
              setArchiveError(null);
              setConfirm(true);
            }}
          >
            <Icon as={Archive} size="sm" />
          </Button>
        </div>
      )}
      {!editing && error ? (
        <Banner tone="destructive" icon={X}>
          {error}
        </Banner>
      ) : null}
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={t("categories.archiveTitle")}
        description={category.name}
        confirmLabel={t("categories.archiveConfirm")}
        tone="destructive"
        pending={archiving}
        error={archiveError}
        onConfirm={() =>
          archive(category.id).catch((e: ApiError) => {
            setArchiveError(apiErrorText(e));
            throw e;
          })
        }
      />
    </li>
  );
}

/**
 * Barcodes of a saved product (19 §1 `GET/POST /products/{id}/barcodes`, `DELETE …/{barcode_id}`,
 * `POST …/internal-generate` — US-M09-05). PATCH /products takes no barcode, so this block works
 * on its own endpoints; BARCODE_DUPLICATE (409) is shown on the input.
 */
import { Barcode, Plus, Trash2, WandSparkles } from "lucide-react";
import { useUnit } from "effector-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import type { BarcodeOut, ProductOut } from "@shared/models";
import { Button, ConfirmDialog, FormField, Icon, Input, StatusChip, toast } from "@shared/ui";

import { barcodeIssue } from "#/entities/product/index.ts";
import { apiErrorText, fieldMessageText } from "#/shared/lib/messages.ts";

import { addBarcodeFx, deleteBarcodeFx, generateInternalBarcodeFx } from "../../model/index.ts";
import type { ApiError } from "@shared/api";

export function Barcodes({ product, canManage }: { product: ProductOut; canManage: boolean }) {
  const { t } = useTranslation("catalog");
  const [add, remove, generate, adding, generating] = useUnit([
    addBarcodeFx,
    deleteBarcodeFx,
    generateInternalBarcodeFx,
    addBarcodeFx.pending,
    generateInternalBarcodeFx.pending,
  ]);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [toDelete, setToDelete] = useState<BarcodeOut | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const archived = product.archived_at !== null;
  const editable = canManage && !archived;

  const submit = () => {
    const issue = barcodeIssue(code);
    if (issue) {
      setError(fieldMessageText(issue));
      return;
    }
    add({ productId: product.id, body: { barcode: code.trim(), kind: "ean" } })
      .then(() => {
        setCode("");
        setError(null);
        toast.success(t("products.barcodes.added"));
      })
      .catch((e: ApiError) => setError(apiErrorText(e)));
  };

  const onGenerate = () => {
    generate(product.id)
      .then((res) => toast.success(t("products.barcodes.generated", { barcode: res.barcode })))
      .catch((e: ApiError) => toast.error(apiErrorText(e)));
  };

  return (
    <section className="flex flex-col gap-3" aria-labelledby="product-barcodes-title">
      <div className="flex items-center justify-between gap-2">
        <h3 id="product-barcodes-title" className="text-h2">
          {t("products.barcodes.title")}
        </h3>
        {editable && product.barcodes.length === 0 ? (
          <Button type="button" variant="secondary" size="sm" onClick={onGenerate} disabled={generating}>
            <Icon as={WandSparkles} size="sm" />
            {t("products.barcodes.generate")}
          </Button>
        ) : null}
      </div>

      {product.barcodes.length === 0 ? (
        <p className="text-small text-muted-foreground">{t("products.barcodes.empty")}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-divider rounded-lg border border-border">
          {product.barcodes.map((b) => (
            <li key={b.id} className="flex items-center gap-3 px-3.5 py-2.5">
              <Icon as={Barcode} size="md" className="shrink-0 text-foreground-secondary" />
              <span className="min-w-0 flex-1 truncate font-semibold tabular-nums">{b.barcode}</span>
              <StatusChip tone={b.kind === "internal" ? "info" : "neutral"}>
                {t(`products.barcodes.kind.${b.kind}`)}
              </StatusChip>
              {editable ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-9 w-9 px-0"
                  aria-label={t("products.barcodes.delete", { barcode: b.barcode })}
                  onClick={() => {
                    setDeleteError(null);
                    setToDelete(b);
                  }}
                >
                  <Icon as={Trash2} size="sm" />
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {editable ? (
        <div className="flex items-end gap-2">
          <FormField label={t("products.barcodes.new")} error={error} className="flex-1">
            <Input
              value={code}
              inputMode="numeric"
              autoComplete="off"
              maxLength={64}
              onChange={(e) => {
                setCode(e.target.value);
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
          <Button type="button" variant="secondary" onClick={submit} disabled={adding || code.trim() === ""}>
            <Icon as={Plus} size="sm" />
            {t("products.barcodes.add")}
          </Button>
        </div>
      ) : null}

      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => (open ? undefined : setToDelete(null))}
        title={t("products.barcodes.deleteTitle")}
        description={toDelete?.barcode}
        tone="destructive"
        confirmLabel={t("products.barcodes.deleteConfirm")}
        error={deleteError}
        onConfirm={() =>
          toDelete
            ? remove({ productId: product.id, barcodeId: toDelete.id }).catch((e: ApiError) => {
                setDeleteError(apiErrorText(e));
                throw e;
              })
            : undefined
        }
      />
    </section>
  );
}

/**
 * «Farqni tasdiqlash» (07 BO-03, 19 §14 post, `stock.count.post`): «Kamomad X so'm, ortiqcha Y so'm
 * hisobga olinadi». 422 COUNT_LINES_INCOMPLETE → «N ta tovar sanalmagan» and the explicit choice
 * «Sanalmaganlarni 0 deb olib tasdiqlash» (`?treat_uncounted_as_zero=true`, farq = −kutilgan).
 */
import { useUnit } from "effector-react";
import { Info, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { toApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import {
  Banner,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  toast,
} from "@shared/ui";

import { absMoney, sumMoney } from "#/shared/lib/decimal.ts";
import { errorText } from "#/shared/lib/errors.ts";

import { postCountFx, type Count, type CountTotals } from "../model/index.ts";

export function PostCountDialog({
  count,
  totals,
  open,
  onClose,
}: {
  count: Count;
  totals: CountTotals;
  open: boolean;
  onClose: () => void;
}) {
  return open ? <PostForm count={count} totals={totals} onClose={onClose} /> : null;
}

function PostForm({ count, totals, onClose }: { count: Count; totals: CountTotals; onClose: () => void }) {
  const { t } = useTranslation("warehouse");
  const [post, pending] = useUnit([postCountFx, postCountFx.pending]);
  const [incomplete, setIncomplete] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = (treatUncountedAsZero: boolean) => {
    setError(null);
    post({ id: count.id, treatUncountedAsZero })
      .then((res) => {
        toast.success(
          t("counts.post.done", { number: res.number }),
          t("counts.post.summary", {
            shortage: formatMoney(sumMoney(res.shortage_lines.map((l) => absMoney(l.amount)))),
            surplus: formatMoney(sumMoney(res.surplus_lines.map((l) => absMoney(l.amount)))),
          }),
        );
        onClose();
      })
      .catch((e: unknown) => {
        const apiError = toApiError(e);
        if (apiError.code === "COUNT_LINES_INCOMPLETE") {
          const n = apiError.params.uncounted_count;
          setIncomplete(typeof n === "number" ? n : totals.uncounted || 1);
          return;
        }
        setError(errorText(apiError));
      });
  };

  return (
    <Dialog open onOpenChange={(open) => (open || pending ? undefined : onClose())}>
      <DialogContent size="sm" role="alertdialog">
        <DialogHeader>
          <DialogTitle>{t("counts.post.title")}</DialogTitle>
          <DialogDescription>
            {t("counts.post.description", {
              shortage: formatMoney(totals.shortage),
              surplus: formatMoney(totals.surplus),
            })}
          </DialogDescription>
        </DialogHeader>
        {incomplete !== null ? (
          <Banner tone="warning" icon={TriangleAlert} live="assertive">
            {t("counts.post.incomplete", { count: incomplete })}
          </Banner>
        ) : totals.uncounted > 0 ? (
          <Banner tone="info" icon={Info}>
            {t("counts.post.uncountedHint", { count: totals.uncounted })}
          </Banner>
        ) : null}
        {error ? (
          <Banner tone="destructive" icon={TriangleAlert} live="assertive">
            {error}
          </Banner>
        ) : null}
        <DialogFooter>
          <Button variant="secondary" disabled={pending} onClick={onClose}>
            {t("actions.back")}
          </Button>
          {incomplete !== null ? (
            <Button
              variant="warning-solid"
              disabled={pending}
              aria-busy={pending || undefined}
              onClick={() => submit(true)}
            >
              {t("counts.post.treatAsZero")}
            </Button>
          ) : (
            <Button disabled={pending} aria-busy={pending || undefined} onClick={() => submit(false)}>
              {t("counts.actions.post")}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

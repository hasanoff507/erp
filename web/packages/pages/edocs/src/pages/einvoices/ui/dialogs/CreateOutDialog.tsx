/**
 * «Chiquvchi e-faktura» (07 BO-15, 18 §14a `POST /einvoices`, `einvoice.create`): a manual outgoing e-invoice
 * for a company buyer — lines (nomi, miqdor, QQSsiz narx, QQS stavkasi 12% / 0%). The server computes the
 * amounts; no posting (13 §2.24). Quantities/prices are decimal strings (qaror #57).
 */
import { useUnit } from "effector-react";
import { Info, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  Banner,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  FormField,
  Input,
  SimpleSelect,
  Icon,
} from "@shared/ui";

import { errorText } from "#/shared/lib/effect.ts";
import { useTx } from "#/shared/lib/i18n.ts";

import {
  $actionError,
  $busy,
  $dialog,
  createOutSubmitted,
  dialogOpened,
  normalizeDecimal,
  type OutLineIn,
} from "../../model/index.ts";
import { CompanyPicker } from "./CompanyPicker.tsx";

interface Draft {
  key: number;
  name: string;
  qty: string;
  price: string;
  vat: "12.00" | "0.00";
}

const blank = (key: number): Draft => ({ key, name: "", qty: "1", price: "", vat: "12.00" });

/** Draft lines → API lines, or `null` when a line is incomplete / malformed. */
export function toLines(drafts: readonly Draft[]): OutLineIn[] | null {
  const out: OutLineIn[] = [];
  for (const d of drafts) {
    const qty = normalizeDecimal(d.qty, 3);
    const price = normalizeDecimal(d.price, 4);
    if (!d.name.trim() || qty === null || price === null || /^0+\.0+$/.test(qty)) return null;
    out.push({ name: d.name.trim(), qty, price, vat_rate: d.vat });
  }
  return out.length > 0 ? out : null;
}

export function CreateOutDialog() {
  const { t } = useTx();
  const [dialog, openDialog, submit, busy, error] = useUnit([
    $dialog,
    dialogOpened,
    createOutSubmitted,
    $busy,
    $actionError,
  ]);
  const [companyId, setCompanyId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Draft[]>([blank(1)]);
  const lines = toLines(drafts);
  const update = (key: number, patch: Partial<Draft>) =>
    setDrafts((list) => list.map((d) => (d.key === key ? { ...d, ...patch } : d)));

  return (
    <Dialog open={dialog === "createOut"} onOpenChange={(next) => openDialog(next ? "createOut" : null)}>
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle>{t("dialogs.createOut")}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <CompanyPicker value={companyId} onChange={setCompanyId} />
          <div className="flex flex-col gap-2" role="group" aria-label={t("dialogs.lines")}>
            {drafts.map((d, i) => (
              <div key={d.key} className="grid grid-cols-[1fr_90px_130px_100px_44px] items-end gap-2">
                <FormField label={t("dialogs.lineName", { n: String(i + 1) })}>
                  <Input
                    value={d.name}
                    maxLength={500}
                    onChange={(e) => update(d.key, { name: e.target.value })}
                  />
                </FormField>
                <FormField label={t("detail.qty")}>
                  <Input
                    inputMode="decimal"
                    value={d.qty}
                    onChange={(e) => update(d.key, { qty: e.target.value })}
                  />
                </FormField>
                <FormField label={t("dialogs.price")}>
                  <Input
                    inputMode="decimal"
                    value={d.price}
                    onChange={(e) => update(d.key, { price: e.target.value })}
                  />
                </FormField>
                <FormField label={t("dialogs.vatRate")}>
                  <SimpleSelect
                    options={[
                      { value: "12.00", label: "12%" },
                      { value: "0.00", label: "0%" },
                    ]}
                    value={d.vat}
                    onValueChange={(v) => update(d.key, { vat: v === "0.00" ? "0.00" : "12.00" })}
                  />
                </FormField>
                <Button
                  size="icon"
                  variant="secondary"
                  aria-label={t("dialogs.removeLine")}
                  disabled={drafts.length === 1}
                  onClick={() => setDrafts((list) => list.filter((x) => x.key !== d.key))}
                >
                  <Icon as={Trash2} size="sm" />
                </Button>
              </div>
            ))}
            <Button
              variant="dashed"
              size="sm"
              onClick={() => setDrafts((list) => [...list, blank((list.at(-1)?.key ?? 0) + 1)])}
            >
              <Icon as={Plus} size="sm" />
              {t("dialogs.addLine")}
            </Button>
          </div>
          {error ? (
            <Banner tone="destructive" icon={Info}>
              {errorText(error)}
            </Banner>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => openDialog(null)}>
            {t("dialogs.close")}
          </Button>
          <Button
            disabled={busy || companyId === null || lines === null}
            data-testid="create-out-submit"
            onClick={() =>
              companyId && lines ? submit({ direction: "out", counterparty_id: companyId, lines }) : undefined
            }
          >
            {t("dialogs.create")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

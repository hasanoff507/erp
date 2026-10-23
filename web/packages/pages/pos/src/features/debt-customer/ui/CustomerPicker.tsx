/**
 * Customer pick for the POS (07 POS-02 «+ Mijoz» F3, POS-03/POS-06 «Mijoz»): local `customers` search (name
 * words, phone digits incl. the last 9 — works offline) and «+ Yangi mijoz» (name + phone → `counterparty.created`
 * in the outbox and the row in the local table at once, US-M08-05 «2–3 soniyada»). Keyboard: typing searches,
 * ↓/↑ + Enter picks, F2 (or the button) opens the quick form, Enter saves it, Esc closes. Touch ≥ 48 px.
 */
import { useUnit } from "effector-react";
import { UserPlus } from "lucide-react";
import { useEffect, useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatMoney, formatPhone } from "@shared/lib/format";
import type { CustomerRow } from "@shared/offline";
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  FormField,
  Icon,
  Input,
  Kbd,
  PhoneInput,
  cn,
} from "@shared/ui";

import {
  createQuickCustomerFx,
  searchCustomersFx,
  validateQuickCustomer,
  type QuickCustomerErrors,
  type QuickCustomerForm,
} from "../model/index.ts";

export interface CustomerPickerProps {
  selectedId: string | null;
  /** The PIN-verified cashier (actor of `counterparty.created`); null → no quick create. */
  actorUserId: string | null;
  /** `debts.create` (18 §11.1) — without it «+ Yangi mijoz» is hidden. */
  canCreate: boolean;
  /** Open with the quick form (NASIYA / «+ Yangi mijoz»). */
  startWithNew?: boolean;
  onSelect: (customer: CustomerRow | null) => void;
  onClose: () => void;
}

export function CustomerPicker({
  selectedId,
  actorUserId,
  canCreate,
  startWithNew = false,
  onSelect,
  onClose,
}: CustomerPickerProps) {
  const { t } = useTranslation("pos");
  const creating = useUnit(createQuickCustomerFx.pending);
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<CustomerRow[]>([]);
  const [active, setActive] = useState(0);
  const [quick, setQuick] = useState<QuickCustomerForm | null>(
    startWithNew && canCreate && actorUserId ? { name: "", phone: "" } : null,
  );
  const [errors, setErrors] = useState<QuickCustomerErrors>({});
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    void searchCustomersFx(query).then((r) => {
      if (!alive) return;
      setRows(r);
      setActive(0);
    });
    return () => {
      alive = false;
    };
  }, [query]);

  const openQuick = () => {
    if (!canCreate || !actorUserId) return;
    const digits = query.replace(/\D+/g, "");
    setQuick(digits.length >= 7 ? { name: "", phone: digits } : { name: query.trim(), phone: "" });
  };

  const saveQuick = async () => {
    if (!quick || !actorUserId) return;
    const found = validateQuickCustomer(quick);
    setErrors(found);
    setFailed(false);
    if (Object.keys(found).length > 0) return;
    try {
      onSelect(await createQuickCustomerFx({ form: quick, actorUserId }));
    } catch {
      setFailed(true);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="max-w-xl" data-testid="customer-picker">
        <DialogHeader>
          <DialogTitle>{quick ? t("debts.newCustomer") : t("sale.customerTitle")}</DialogTitle>
          <DialogDescription>{quick ? t("debts.newCustomerHint") : t("sale.customerHint")}</DialogDescription>
        </DialogHeader>
        {quick ? (
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              void saveQuick();
            }}
          >
            <FormField label={t("debts.customerName")} required error={errors.name ?? null}>
              <Input
                autoFocus
                className="h-12"
                maxLength={255}
                value={quick.name}
                data-testid="quick-name"
                onChange={(e) => setQuick({ ...quick, name: e.target.value })}
              />
            </FormField>
            <FormField label={t("debts.customerPhone")} required error={errors.phone ?? null}>
              <PhoneInput
                className="h-12"
                value={quick.phone}
                data-testid="quick-phone"
                onChange={(phone) => setQuick({ ...quick, phone })}
              />
            </FormField>
            {failed ? (
              <p className="text-[13px] font-bold text-destructive">{t("debts.quickFailed")}</p>
            ) : null}
            <DialogFooter>
              <Button type="button" size="pos" variant="secondary" onClick={() => setQuick(null)}>
                {t("sale.cancel")}
              </Button>
              <Button type="submit" size="pos" disabled={creating} data-testid="quick-save">
                {t("debts.quickSave")}
                <Kbd keys="Enter" inverted />
              </Button>
            </DialogFooter>
          </form>
        ) : (
          <>
            <Input
              autoFocus
              data-testid="customer-search"
              placeholder={t("sale.customerSearch")}
              value={query}
              className="h-12"
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  setActive((i) => Math.min(rows.length - 1, i + 1));
                } else if (e.key === "ArrowUp") {
                  e.preventDefault();
                  setActive((i) => Math.max(0, i - 1));
                } else if (e.key === "Enter") {
                  e.preventDefault();
                  const row = rows[active];
                  if (row) onSelect(row);
                  else openQuick();
                } else if (e.key === "F2") {
                  e.preventDefault();
                  openQuick();
                }
              }}
            />
            <ul className="flex max-h-[360px] flex-col gap-1 overflow-y-auto" role="listbox">
              {rows.length === 0 ? (
                <li className="py-6 text-center text-muted-foreground">{t("sale.customerNone")}</li>
              ) : null}
              {rows.map((c, i) => (
                <li key={c.id} role="option" aria-selected={i === active}>
                  <button
                    type="button"
                    onClick={() => onSelect(c)}
                    data-testid="customer-option"
                    aria-pressed={c.id === selectedId}
                    className={cn(
                      "flex min-h-14 w-full items-center gap-3 rounded-xl border border-border px-3 py-2 text-left hover:border-primary aria-pressed:border-primary",
                      i === active && "border-primary bg-primary-soft",
                    )}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-bold">{c.name}</span>
                      <span className="block text-[12px] text-muted-foreground">
                        {c.phone ? formatPhone(c.phone) : ""}
                        {c._local ? ` · ${t("debts.notSynced")}` : ""}
                      </span>
                    </span>
                    <span className="text-right text-[12px]">
                      {t("sale.customerDebt", {
                        amount: formatMoney(c.receivable_balance ?? "0.00", { withCurrency: false }),
                      })}
                      {c.credit_limit ? (
                        <span className="block text-muted-foreground">
                          {t("sale.customerLimit", {
                            amount: formatMoney(c.credit_limit, { withCurrency: false }),
                          })}
                        </span>
                      ) : null}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <DialogFooter>
              {canCreate && actorUserId ? (
                <Button size="pos" variant="secondary" onClick={openQuick} data-testid="quick-customer">
                  <Icon as={UserPlus} size="md" />
                  {t("debts.newCustomer")}
                  <Kbd keys="F2" />
                </Button>
              ) : null}
              <div className="grow" />
              {selectedId ? (
                <Button size="pos" variant="secondary" onClick={() => onSelect(null)}>
                  {t("sale.customerClear")}
                </Button>
              ) : null}
              <Button size="pos" variant="secondary" onClick={onClose}>
                {t("sale.cancel")}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

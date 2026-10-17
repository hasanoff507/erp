/**
 * POS-02 dialogs: manual weight (06 §1.6 c), quantity edit, receipt discount (18 §4.4 — within the cashier's
 * `discount.give` limit, above it a Manager/Owner approval: local PIN or remote request online, 18 §2.4/§9),
 * customer pick (local `customers`, 16 §1) and the void confirmation (#15).
 */
import { useUnit } from "effector-react";
import { useEffect, useMemo, useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { customers, limits, type CustomerRow, type ProductView } from "@shared/offline";
import { $isOnline } from "@shared/state/network";
import {
  Button,
  ConfirmDialog,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
} from "@shared/ui";

import {
  $draft,
  $totals,
  discountSet,
  effectiveDiscountPct,
  normalizePct,
  parseQty,
  priceLines,
  withinLimit,
  type ApprovalRef,
} from "#/entities/receipt-draft/index.ts";
import { $posCashier } from "#/entities/pos-session/index.ts";
import { ManagerApprovalDialog } from "#/features/manager-approval/index.ts";

export function QtyDialog({
  title,
  unit,
  initial,
  fractional,
  onSubmit,
  onClose,
}: {
  title: string;
  unit: string;
  initial: string;
  fractional: boolean;
  onSubmit: (qty: string) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation("pos");
  const [value, setValue] = useState(initial);
  const parsed = parseQty(value, fractional);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {fractional ? t("sale.qtyHintFractional", { unit }) : t("sale.qtyHintWhole")}
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (parsed) onSubmit(parsed);
          }}
          className="flex flex-col gap-3"
        >
          <Label htmlFor="pos-qty">{t("sale.qtyLabel")}</Label>
          <Input
            id="pos-qty"
            data-testid="qty-input"
            autoFocus
            inputMode="decimal"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="h-14 text-[22px] font-extrabold"
          />
          {!parsed && value ? <p className="text-[13px] text-destructive">{t("sale.qtyInvalid")}</p> : null}
          <DialogFooter>
            <Button type="button" size="pos" variant="secondary" onClick={onClose}>
              {t("sale.cancel")}
            </Button>
            <Button type="submit" size="pos" disabled={!parsed} data-testid="qty-submit">
              {t("sale.apply")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function WeightDialog({
  view,
  onSubmit,
  onClose,
}: {
  view: ProductView;
  onSubmit: (qty: string) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation("pos");
  return (
    <QtyDialog
      title={t("sale.weightTitle", { name: view.product.name })}
      unit={view.product.unit_code}
      initial=""
      fractional
      onSubmit={onSubmit}
      onClose={onClose}
    />
  );
}

/** Receipt discount, % of the receipt (07 POS-02 `discountPercent`, 0–100). */
export function DiscountDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation("pos");
  const [draft, totals, cashier, online, setDiscount] = useUnit([
    $draft,
    $totals,
    $posCashier,
    $isOnline,
    discountSet,
  ]);
  const [value, setValue] = useState(draft.discount?.pct.replace(/\.00$/, "") ?? "");
  const [limit, setLimit] = useState<string | null | undefined>(undefined);
  const [approving, setApproving] = useState(false);
  useEffect(() => {
    if (!cashier) return;
    void limits.value(cashier.userId, "discount.give").then(setLimit);
  }, [cashier]);

  const pct = normalizePct(value || "0");
  const preview = useMemo(
    () => (pct ? priceLines(totals.lines, { pct, approval: null }) : null),
    [pct, totals.lines],
  );
  const effective = preview ? effectiveDiscountPct(preview) : "0.00";
  const needsApproval = pct !== null && !withinLimit(effective, limit);

  const apply = (approval: ApprovalRef | null) => {
    if (!pct) return;
    setDiscount(pct === "0.00" ? null : { pct, approval });
    onClose();
  };

  if (approving && pct && preview) {
    return (
      <ManagerApprovalDialog
        kind="discount_over_limit"
        permission="discount.approve"
        amount={effective}
        context={{ requested_pct: effective, amount: preview.discount }}
        requesterId={cashier?.userId ?? null}
        reason={t("sale.discountApprovalReason", { pct: effective, limit: limit ?? "0" })}
        allowRemote={online}
        onApproved={(ref) => apply(ref)}
        onClose={() => setApproving(false)}
      />
    );
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t("sale.discountTitle")}</DialogTitle>
          <DialogDescription>
            {limit === undefined
              ? t("sale.discountNoRight")
              : limit === null
                ? t("sale.discountUnlimited")
                : t("sale.discountLimit", { limit: limit.replace(/\.0+$/, "") })}
          </DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (!pct) return;
            if (needsApproval) setApproving(true);
            else apply(null);
          }}
        >
          <Label htmlFor="pos-discount">{t("sale.discountPercent")}</Label>
          <Input
            id="pos-discount"
            data-testid="discount-input"
            autoFocus
            inputMode="decimal"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="h-14 text-[22px] font-extrabold"
          />
          {!pct ? <p className="text-[13px] text-destructive">{t("sale.discountInvalid")}</p> : null}
          {preview ? (
            <p className="text-[14px]">
              {t("sale.discountPreview", {
                amount: formatMoney(preview.discount, { withCurrency: false }),
                total: formatMoney(preview.total),
              })}
            </p>
          ) : null}
          {needsApproval ? (
            <p className="text-[13px] font-bold text-warning-strong">{t("sale.discountNeedsApproval")}</p>
          ) : null}
          <DialogFooter>
            <Button type="button" size="pos" variant="secondary" onClick={onClose}>
              {t("sale.cancel")}
            </Button>
            <Button type="submit" size="pos" disabled={!pct} data-testid="discount-apply">
              {needsApproval ? t("sale.discountAskApproval") : t("sale.apply")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function CustomerDialog({
  selectedId,
  onSelect,
  onClose,
}: {
  selectedId: string | null;
  onSelect: (c: CustomerRow | null) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation("pos");
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<CustomerRow[]>([]);
  useEffect(() => {
    let alive = true;
    void customers.search(query, { limit: 30 }).then((r) => alive && setRows(r));
    return () => {
      alive = false;
    };
  }, [query]);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{t("sale.customerTitle")}</DialogTitle>
          <DialogDescription>{t("sale.customerHint")}</DialogDescription>
        </DialogHeader>
        <Input
          autoFocus
          data-testid="customer-search"
          placeholder={t("sale.customerSearch")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="h-12"
        />
        <ul className="flex max-h-[360px] flex-col gap-1 overflow-y-auto">
          {rows.length === 0 ? (
            <li className="py-6 text-center text-muted-foreground">{t("sale.customerNone")}</li>
          ) : null}
          {rows.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => onSelect(c)}
                data-testid="customer-option"
                className="flex h-14 w-full items-center gap-3 rounded-xl border border-border px-3 text-left hover:border-primary aria-pressed:border-primary"
                aria-pressed={c.id === selectedId}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-bold">{c.name}</span>
                  <span className="block text-[12px] text-muted-foreground">{c.phone ?? ""}</span>
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
          {selectedId ? (
            <Button size="pos" variant="secondary" onClick={() => onSelect(null)}>
              {t("sale.customerClear")}
            </Button>
          ) : null}
          <Button size="pos" variant="secondary" onClick={onClose}>
            {t("sale.cancel")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function VoidConfirm({
  whole,
  pending,
  onConfirm,
  onClose,
}: {
  whole: boolean;
  pending: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation("pos");
  return (
    <ConfirmDialog
      open
      onOpenChange={(o) => !o && onClose()}
      title={t("sale.voidConfirmTitle")}
      description={whole ? t("sale.voidConfirmReceipt") : t("sale.voidConfirmLine")}
      confirmLabel={t("sale.voidConfirmYes")}
      cancelLabel={t("sale.cancel")}
      tone="destructive"
      pending={pending}
      onConfirm={onConfirm}
    />
  );
}

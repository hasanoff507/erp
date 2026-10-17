/**
 * BO-21 ④ table (07 `debts[]` — Jadval/Excel: ism, telefon, summa): typed rows or a paste from Excel, the
 * direction (customers owe me / I owe suppliers), «Saqlash» → each row becomes a posted opening debt; saved
 * rows are marked and never sent twice, failed rows show the server reason.
 */
import { CircleAlert, ClipboardPaste, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { addMoney, type Money } from "@shared/lib/money";
import {
  Banner,
  Button,
  Icon,
  Input,
  MoneyInput,
  PhoneInput,
  SegmentedControl,
  StatusChip,
  Textarea,
  translateFieldError,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";

import {
  MAX_ROWS,
  isBlank,
  newRow,
  parsePasted,
  submitRows,
  validateRow,
  type DebtDirection,
  type DebtRowDraft,
  type RowErrors,
  type RowResult,
} from "../model/index.ts";

export interface OpeningDebtsFormProps {
  /** Disabled offline / without a session. */
  disabled?: boolean;
  /** Called after a run with the number of rows saved so far. */
  onSaved?: (count: number) => void;
}

export function OpeningDebtsForm({ disabled = false, onSaved }: OpeningDebtsFormProps) {
  const { t } = useTranslation("onboarding");
  const [direction, setDirection] = useState<DebtDirection>("receivable");
  const [rows, setRows] = useState<DebtRowDraft[]>(() => [newRow(), newRow(), newRow()]);
  const [errors, setErrors] = useState<Record<string, RowErrors>>({});
  const [results, setResults] = useState<Record<string, RowResult>>({});
  const [pasting, setPasting] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const [busy, setBusy] = useState(false);
  const saved = new Set(
    Object.entries(results)
      .filter(([, r]) => r.ok)
      .map(([k]) => k),
  );
  const filled = rows.filter((r) => !isBlank(r));
  const total = addMoney("0.00" as Money, ...filled.map((r) => (r.amount || "0.00") as Money));

  const set = (key: string, patch: Partial<DebtRowDraft>) =>
    setRows((list) => list.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  const save = async () => {
    const found: Record<string, RowErrors> = {};
    for (const r of filled) {
      if (saved.has(r.key)) continue;
      const e = validateRow(r, direction);
      if (Object.keys(e).length > 0) found[r.key] = e;
    }
    setErrors(found);
    if (Object.keys(found).length > 0 || filled.length === 0) return;
    setBusy(true);
    try {
      const out = await submitRows(filled, direction, saved);
      const next = { ...results, ...out };
      setResults(next);
      onSaved?.(Object.values(next).filter((r) => r.ok).length);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3" data-testid="opening-debts">
      <SegmentedControl<DebtDirection>
        label={t("debts.direction")}
        value={direction}
        onChange={(d) => setDirection(d)}
        options={[
          { value: "receivable", label: t("debts.receivable") },
          { value: "payable", label: t("debts.payable") },
        ]}
      />
      <div className="grid grid-cols-[1fr_190px_170px_40px] gap-2 rounded-lg bg-accent px-3 py-2 text-[12px] font-bold text-muted-foreground">
        <span>{t("debts.columns.name")}</span>
        <span>{t("debts.columns.phone")}</span>
        <span className="text-right">{t("debts.columns.amount")}</span>
        <span className="sr-only">{t("debts.remove")}</span>
      </div>
      <ul className="flex flex-col gap-2">
        {rows.map((r, i) => {
          const e = errors[r.key] ?? {};
          const res = results[r.key];
          const done = res?.ok === true;
          return (
            <li key={r.key} className="flex flex-col gap-1" data-testid="opening-debt-row">
              <div className="grid grid-cols-[1fr_190px_170px_40px] items-start gap-2">
                <Input
                  aria-label={`${t("debts.columns.name")} ${i + 1}`}
                  value={r.name}
                  maxLength={255}
                  disabled={disabled || done}
                  aria-invalid={e.name ? true : undefined}
                  onChange={(ev) => set(r.key, { name: ev.target.value })}
                />
                <PhoneInput
                  aria-label={`${t("debts.columns.phone")} ${i + 1}`}
                  value={r.phone}
                  disabled={disabled || done}
                  aria-invalid={e.phone ? true : undefined}
                  onChange={(phone) => set(r.key, { phone })}
                />
                <MoneyInput
                  aria-label={`${t("debts.columns.amount")} ${i + 1}`}
                  value={r.amount}
                  disabled={disabled || done}
                  aria-invalid={e.amount ? true : undefined}
                  onChange={(amount) => set(r.key, { amount })}
                />
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  aria-label={t("debts.remove")}
                  disabled={disabled || done || rows.length <= 1}
                  onClick={() => setRows((list) => list.filter((x) => x.key !== r.key))}
                >
                  <Icon as={Trash2} size="sm" />
                </Button>
              </div>
              {Object.keys(e).length > 0 ? (
                <p className="text-small font-semibold text-destructive" role="alert">
                  {Object.values(e)
                    .map((k) => translateFieldError(k))
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              ) : null}
              {res ? (
                res.ok ? (
                  <StatusChip tone="success" className="self-start">
                    {t("debts.rowSaved")}
                  </StatusChip>
                ) : (
                  <p className="text-small font-semibold text-destructive" data-testid="opening-debt-error">
                    {errorText(res.error)}
                  </p>
                )
              ) : null}
            </li>
          );
        })}
      </ul>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          disabled={disabled || rows.length >= MAX_ROWS}
          onClick={() => setRows((list) => [...list, newRow()])}
        >
          <Icon as={Plus} size="sm" />
          {t("debts.addRow")}
        </Button>
        <Button type="button" variant="secondary" disabled={disabled} onClick={() => setPasting((v) => !v)}>
          <Icon as={ClipboardPaste} size="sm" />
          {t("debts.paste")}
        </Button>
        <div className="grow" />
        <span className="text-[13px] text-foreground-secondary" data-testid="opening-debts-total">
          {t("debts.total", { n: filled.length, amount: formatMoney(total) })}
        </span>
        <Button
          type="button"
          disabled={disabled || busy || filled.length === 0}
          onClick={() => void save()}
          data-testid="opening-debts-save"
        >
          {t("debts.save")}
        </Button>
      </div>
      {pasting ? (
        <div className="flex flex-col gap-2 rounded-lg border border-dashed border-border p-3">
          <span className="text-[13px] text-foreground-secondary">{t("debts.pasteHint")}</span>
          <Textarea
            rows={4}
            value={pasteText}
            aria-label={t("debts.paste")}
            onChange={(e) => setPasteText(e.target.value)}
            data-testid="opening-debts-paste"
          />
          <Button
            type="button"
            variant="secondary"
            className="self-end"
            disabled={!pasteText.trim()}
            onClick={() => {
              const parsed = parsePasted(pasteText);
              setRows((list) =>
                [...list.filter((r) => !isBlank(r) || results[r.key]), ...parsed].slice(0, MAX_ROWS),
              );
              setPasteText("");
              setPasting(false);
            }}
          >
            {t("debts.pasteApply")}
          </Button>
        </div>
      ) : null}
      <Banner tone="info" icon={CircleAlert}>
        {t("debts.note")}
      </Banner>
    </div>
  );
}

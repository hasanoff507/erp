/** Search a company counterparty (B2B buyer, `kind='company'`) — `GET /counterparties?kind=company&search=`. */
import { useUnit } from "effector-react";
import { Search } from "lucide-react";
import { useState } from "react";

import { Button, FormField, Icon, Input, cn } from "@shared/ui";

import { useTx } from "#/shared/lib/i18n.ts";

import { $companies, companiesSearched, searchCompaniesFx } from "../../model/index.ts";

export function CompanyPicker({ value, onChange }: { value: string | null; onChange: (id: string) => void }) {
  const { t } = useTx();
  const [items, pending, search] = useUnit([$companies, searchCompaniesFx.pending, companiesSearched]);
  const [query, setQuery] = useState("");
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-end gap-2">
        <FormField label={t("dialogs.company")} className="flex-1">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => (e.key === "Enter" ? search(query) : undefined)}
            placeholder={t("dialogs.companyPlaceholder")}
          />
        </FormField>
        <Button
          variant="secondary"
          disabled={pending}
          onClick={() => search(query)}
          aria-label={t("dialogs.searchCompany")}
        >
          <Icon as={Search} size="sm" />
        </Button>
      </div>
      <ul className="flex flex-col gap-1" aria-label={t("dialogs.companies")}>
        {items.map((c) => (
          <li key={c.id}>
            <button
              type="button"
              aria-pressed={value === c.id}
              onClick={() => onChange(c.id)}
              className={cn(
                "flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-[13px]",
                value === c.id ? "border-primary bg-primary-soft" : "border-border hover:bg-accent",
              )}
            >
              <span className="font-semibold">{c.name}</span>
              <span className="text-foreground-secondary">{c.stir ?? t("dialogs.noStir")}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

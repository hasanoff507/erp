/**
 * BO-21 ③ (07 `method`, `openingStockMethod`): Qo'lda → catalog product form, Excel/CSV → the
 * catalog's import flow embedded through the shell slot (pages never import each other, 24 §1),
 * Foto (AI-03) → Bosqich 6. ③b opening stock (optional): Excel/CSV (`kind=opening_stock`, shell slot)
 * or manual stock-opening lines — `OpeningStockSection`.
 */
import { useUnit } from "effector-react";
import { Camera, CircleCheck, FileSpreadsheet, PenLine, type LucideIcon } from "lucide-react";
import type { ComponentType } from "react";
import { Link } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { Banner, Button, Card, Icon, cn } from "@shared/ui";

import {
  $importedCount,
  $productsMethod,
  nextClicked,
  productsImported,
  productsMethodSelected,
  type OpeningStockImportSlotProps,
  type ProductImportSlotProps,
  type ProductsMethod,
} from "../../model/index.ts";
import { StepFooter } from "../footer/StepFooter.tsx";
import { OpeningStockSection } from "./OpeningStockSection.tsx";

const METHODS: readonly { id: ProductsMethod; icon: LucideIcon }[] = [
  { id: "manual", icon: PenLine },
  { id: "import", icon: FileSpreadsheet },
  { id: "photo", icon: Camera },
];

export interface ProductsStepProps {
  productImport?: ComponentType<ProductImportSlotProps>;
  manualProductHref?: string | null;
  openingStockImport?: ComponentType<OpeningStockImportSlotProps>;
}

export function ProductsStep({
  productImport: ProductImport,
  manualProductHref,
  openingStockImport,
}: ProductsStepProps) {
  const { t } = useTranslation("onboarding");
  const [method, imported, select, onImported, next] = useUnit([
    $productsMethod,
    $importedCount,
    productsMethodSelected,
    productsImported,
    nextClicked,
  ]);

  const available = (id: ProductsMethod) =>
    id === "manual" ? Boolean(manualProductHref) : id === "import" ? ProductImport !== undefined : false;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[14px] text-foreground-secondary">{t("products.intro")}</p>
      <div role="group" aria-label={t("products.methodLabel")} className="grid gap-3 md:grid-cols-3">
        {METHODS.map(({ id, icon }) => {
          const selected = method === id;
          const disabled = !available(id);
          return (
            <button
              key={id}
              type="button"
              aria-pressed={selected}
              disabled={disabled}
              onClick={() => select(selected ? null : id)}
              className={cn(
                "flex flex-col items-start gap-1.5 rounded-xl border bg-card p-4 text-left transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                "disabled:cursor-not-allowed disabled:opacity-60",
                selected ? "border-2 border-primary bg-primary-soft" : "border-input hover:bg-accent",
              )}
            >
              <Icon as={icon} size="lg" className="text-primary" />
              <span className="text-[15px] font-extrabold">{t(`products.methods.${id}.title`)}</span>
              <span className="text-[13px] text-foreground-secondary">
                {t(`products.methods.${id}.text`)}
              </span>
              {id === "photo" ? (
                <span className="text-[12px] text-muted-foreground">{t("products.photoLater")}</span>
              ) : id === "import" && disabled ? (
                <span className="text-[12px] text-muted-foreground">{t("products.importUnavailable")}</span>
              ) : null}
            </button>
          );
        })}
      </div>

      {imported !== null ? (
        <Banner tone="success" icon={CircleCheck}>
          {t("products.imported", { count: imported })}
        </Banner>
      ) : null}

      {method === "manual" && manualProductHref ? (
        <Card className="flex flex-wrap items-center gap-3">
          <p className="min-w-0 flex-1 text-[14px] text-foreground-secondary">{t("products.manualHint")}</p>
          <Button asChild>
            <Link to={manualProductHref}>{t("products.openManual")}</Link>
          </Button>
        </Card>
      ) : null}
      {method === "import" && ProductImport ? (
        <Card className="p-4 md:p-5">
          <ProductImport embedded onDone={(result) => onImported(result.createdProductCount)} />
        </Card>
      ) : null}

      <OpeningStockSection openingStockImport={openingStockImport} />

      <StepFooter primaryType="button" onPrimary={() => next()} autoFocusPrimary />
    </div>
  );
}

/**
 * Tovarlarni import qilish — Excel/CSV (US-M04-04, 19 §6). Route `/app/catalog/products/import`
 * (inside the catalog area; 07 has no own route for it — see the W3 report). Permission
 * `catalog.manage` (19 §6 for kind=products).
 */
import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { useCan } from "@shared/state/permissions";
import { Button, Icon, NoPermissionState } from "@shared/ui";

import { ImportProductsFlow } from "#/features/import-products/index.ts";

const PRODUCTS_PATH = "/app/catalog/products";

function ProductImportPage() {
  const { t } = useTranslation("catalog");
  const canImport = useCan({ permission: "catalog.manage" });
  if (!canImport) return <NoPermissionState />;

  return (
    <div className="flex max-w-5xl flex-col gap-[18px]">
      <div className="flex flex-wrap items-center gap-2.5">
        <Button variant="ghost" size="sm" asChild>
          <Link to={PRODUCTS_PATH}>
            <Icon as={ArrowLeft} size="sm" />
            {t("import.back")}
          </Link>
        </Button>
      </div>
      <div>
        <p className="text-small text-foreground-secondary">{t("import.subtitle")}</p>
      </div>
      <ImportProductsFlow
        doneAction={
          <Button asChild>
            <Link to={PRODUCTS_PATH}>{t("import.done.toProducts")}</Link>
          </Button>
        }
      />
    </div>
  );
}

export const ProductImport = {
  route: "catalog/products/import",
  titleKey: "catalog:import.title",
  Page: ProductImportPage,
} as const;

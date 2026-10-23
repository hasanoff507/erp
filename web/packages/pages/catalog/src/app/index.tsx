/**
 * @pages/catalog — Tovarlar, narxlar, yorliqlar (M09). Package router (24 §1): route objects relative
 * to the back-office root `/app`.
 *
 * - BO-05 `/app/catalog/prices` — narxlar va narx tarixi (07).
 * - `/app/catalog/products[/new|/:productId]` — tovarlar katalogi (19 §1–§3; no own route in 07).
 * - `/app/catalog/products/import` — Excel/CSV import (19 §6, US-M04-04).
 * BO-18 `/app/catalog/labels` is not built yet (shell shows "Tez orada").
 *
 * Also exports `ImportProductsFlow` for the onboarding wizard (BO-21 ③a). Page packages do not
 * import each other (24 §1), so the shell hands it to @pages/billing.
 */
import type { RouteObject } from "react-router-dom";

import type { RouteHandle } from "@shared/models";

import { ProductImport } from "#/pages/product-import/ui/page/Page.tsx";
import { Prices } from "#/pages/prices/ui/page/Page.tsx";
import { Products } from "#/pages/products/ui/page/Page.tsx";

export {
  ImportProductsFlow,
  type ImportProductsFlowProps,
  type ImportProductsResult,
} from "#/features/import-products/index.ts";

export const routes: RouteObject[] = [
  {
    path: Prices.route,
    element: <Prices.Page />,
    handle: { titleKey: Prices.titleKey } satisfies RouteHandle,
  },
  {
    path: ProductImport.route,
    element: <ProductImport.Page />,
    handle: { titleKey: ProductImport.titleKey } satisfies RouteHandle,
  },
  ...Products.routes.map((path) => ({
    path,
    element: <Products.Page />,
    handle: { titleKey: Products.titleKey } satisfies RouteHandle,
  })),
];

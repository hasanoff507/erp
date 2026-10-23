/**
 * @pages/edocs — E-faktura markazi (BO-15; M07, M10): kiruvchi va chiquvchi e-faktura, kiruvchi e-TTN,
 * e-ishonchnomalar, E-IMZO imzolash (`@shared/lib/eimzo`). Package router (24 §1): routes relative to `/app`.
 * Each screen lives in src/pages/<screen>/{model/{events,stores,effects,connections,types,lib},ui}.
 */
import type { RouteObject } from "react-router-dom";

import type { RouteHandle } from "@shared/models";

import { EInvoices } from "#/pages/einvoices/ui/page/Page.tsx";

export const routes: RouteObject[] = [EInvoices].map((screen) => ({
  path: screen.route,
  element: <screen.Page />,
  handle: { titleKey: screen.titleKey } satisfies RouteHandle,
}));

import { useEffect } from "react";
import { useLocation, useMatches } from "react-router-dom";

import { i18next, useTranslation } from "@shared/i18n";
import type { RouteHandle } from "@shared/models";

import { navItemForPath } from "../../sidebar/nav-items.ts";

function isRouteHandle(handle: unknown): handle is RouteHandle {
  return typeof handle === "object" && handle !== null && "titleKey" in handle;
}

/**
 * Topbar title (06 §1.9: screen name without ID): the deepest route `handle.titleKey`, otherwise the
 * sidebar item the path belongs to. Also mirrors it into document.title.
 */
export function usePageTitle(): string {
  const { t } = useTranslation();
  const matches = useMatches();
  const { pathname } = useLocation();

  const handle = [...matches]
    .reverse()
    .map((m) => m.handle)
    .find(isRouteHandle);
  const navItem = navItemForPath(pathname);
  const translate = i18next.t.bind(i18next) as (key: string) => string;
  const title = handle?.titleKey ? translate(handle.titleKey) : navItem ? t(`nav.items.${navItem.key}`) : "";

  useEffect(() => {
    document.title = title ? `${title} · ERP` : "ERP";
  }, [title]);

  return title;
}

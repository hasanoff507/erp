/**
 * Back-office layout — 08 §6.2, 06 §1.9, mockup Bo02Dashboard.dc.html.
 * ≥1024px: sidebar always open (260px); 768–1023px: icon rail (w-16); <768px: off-canvas drawer over
 * the content (burger in the topbar). Content padding px-7 py-6; density `compact`.
 * The drawer is a plain fixed panel (no scroll-lock <style> injection — strict CSP, qaror #57).
 */
import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Outlet } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { Button, Icon } from "@shared/ui";

import { Sidebar } from "../../sidebar/Sidebar.tsx";
import { useDocumentAttributes } from "../document-attributes.ts";

import { Topbar } from "./Topbar.tsx";

export function BackOfficeLayout() {
  useDocumentAttributes({ density: "compact", theme: null });
  const { t } = useTranslation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!drawerOpen) return;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [drawerOpen]);

  return (
    <div className="flex min-h-dvh bg-background">
      <aside className="sticky top-0 hidden h-dvh shrink-0 md:block">
        <Sidebar variant="rail" />
      </aside>

      {drawerOpen ? (
        <div
          className="fixed inset-0 z-overlay flex md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label={t("nav.label")}
        >
          <div className="relative h-full shadow-dialog">
            <Sidebar variant="drawer" onNavigate={() => setDrawerOpen(false)} />
          </div>
          <button
            type="button"
            className="flex-1 bg-overlay/55"
            aria-label={t("topbar.closeMenu")}
            onClick={() => setDrawerOpen(false)}
          />
          <Button
            ref={closeRef}
            variant="outline"
            size="icon"
            className="absolute right-3 top-3"
            aria-label={t("topbar.closeMenu")}
            onClick={() => setDrawerOpen(false)}
          >
            <Icon as={X} size="lg" />
          </Button>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenMenu={() => setDrawerOpen(true)} />
        <main id="main" className="flex-1 px-4 py-6 md:px-7">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

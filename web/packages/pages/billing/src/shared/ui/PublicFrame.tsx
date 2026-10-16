import { useEffect, type ReactNode } from "react";

import { useTranslation } from "@shared/i18n";
import { LogoMark } from "@shared/ui";

import { LanguageToggle } from "./LanguageToggle.tsx";

/**
 * Full page without sidebar for the public routes (/install, /recover, /invite — 08 §6.2): BO-01
 * header (logo, «ERP», tagline, UZ · RU) and a centred column.
 */
export function PublicFrame({
  title,
  children,
  width = "narrow",
}: {
  title: string;
  children: ReactNode;
  width?: "narrow" | "wide";
}) {
  const { t } = useTranslation();
  useEffect(() => {
    document.title = `${title} · ERP`;
  }, [title]);

  return (
    <div className="flex min-h-dvh flex-col bg-background px-4 pb-8 pt-4 sm:px-12">
      <header className="flex items-center gap-2.5">
        <LogoMark size={38} />
        <div>
          <div className="text-[16px] font-extrabold">{t("app.name")}</div>
          <div className="text-[12px] text-foreground-secondary">{t("app.tagline")}</div>
        </div>
        <div className="grow" />
        <LanguageToggle />
      </header>
      <main
        className={
          width === "narrow"
            ? "mx-auto flex w-full max-w-[440px] grow flex-col justify-center gap-4 py-6"
            : "mx-auto flex w-full max-w-[880px] grow flex-col gap-4 py-6"
        }
      >
        {children}
      </main>
    </div>
  );
}

/**
 * BO-01 right-hand product panel (mockup Bo01Kirish.dc.html «Mahsulot haqida»): dark ink card,
 * five feature rows, price box «99 000 so'm/oy — Hammasi ichida» (single tariff, qaror #22).
 * Hidden below 1024px so the form stays first on phones.
 */
import { FileText, Receipt, Shield, Sparkles, Users, type LucideIcon } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { Icon } from "@shared/ui";

const FEATURES: readonly { key: "fiscal" | "einvoice" | "debts" | "vat" | "ai"; icon: LucideIcon }[] = [
  { key: "fiscal", icon: Receipt },
  { key: "einvoice", icon: FileText },
  { key: "debts", icon: Users },
  { key: "vat", icon: Shield },
  { key: "ai", icon: Sparkles },
];

/** Plan price is a decimal string like every money value (qaror #26); display-only formatting. */
const MONTHLY_PRICE = "99000.00";

export function PromoPanel() {
  const { t } = useTranslation("auth");

  return (
    <aside
      aria-label={t("promo.label")}
      className="hidden min-w-0 flex-[1_1_520px] flex-col gap-[22px] rounded-[24px] bg-sidebar px-11 py-10 text-sidebar-accent-foreground lg:flex"
    >
      <div className="flex flex-col gap-2.5">
        <span className="self-start rounded-full bg-sidebar-accent px-3 py-1.5 text-[12px] font-bold text-sidebar-ring">
          {t("promo.badge")}
        </span>
        <h2 className="text-[30px] font-extrabold leading-tight">{t("promo.title")}</h2>
        <p className="text-[15px] leading-relaxed text-sidebar-foreground">{t("promo.text")}</p>
      </div>

      <ul className="flex flex-col gap-3">
        {FEATURES.map(({ key, icon }) => (
          <li key={key} className="flex items-start gap-3.5 rounded-xl bg-sidebar-accent/70 px-3.5 py-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-sidebar-accent text-sidebar-ring">
              <Icon as={icon} size="md" />
            </span>
            <span className="flex flex-col gap-0.5">
              <span className="text-[15px] font-bold">{t(`promo.features.${key}.title`)}</span>
              <span className="text-[13px] text-sidebar-foreground">{t(`promo.features.${key}.text`)}</span>
            </span>
          </li>
        ))}
      </ul>

      <div className="mt-auto flex flex-wrap items-center gap-4 rounded-[18px] bg-primary-soft px-[22px] py-5 text-foreground">
        <div className="flex flex-[1_1_220px] flex-col gap-1">
          <span className="text-[30px] font-extrabold tabular-nums text-primary-strong">
            {formatMoney(MONTHLY_PRICE)}
            <span className="text-[16px] font-bold">{t("promo.perMonth")}</span>
          </span>
          <span className="text-[15px] font-extrabold">{t("promo.priceTitle")}</span>
        </div>
        <span className="flex-[1_1_200px] text-[13px] leading-normal text-foreground-secondary">
          {t("promo.priceText")}
        </span>
      </div>
    </aside>
  );
}

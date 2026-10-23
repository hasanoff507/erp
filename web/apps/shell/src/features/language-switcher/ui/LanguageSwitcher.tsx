/**
 * language-switcher — «UZ · RU» segmented control, same place on every screen (06 §1.4, 08 §6.2):
 * active segment = foreground background + white text. Changes only the UI language, never receipts.
 */
import { changeLanguage, isUiLanguage, useTranslation, type UiLanguage } from "@shared/i18n";
import { SegmentedControl } from "@shared/ui";

export function LanguageSwitcher({ density = "compact" }: { density?: "compact" | "touch" }) {
  const { t, i18n } = useTranslation();
  const value: UiLanguage = isUiLanguage(i18n.resolvedLanguage) ? i18n.resolvedLanguage : "uz";

  return (
    <SegmentedControl<UiLanguage>
      label={t("lang.groupLabel")}
      value={value}
      density={density}
      onChange={(lang) => {
        void changeLanguage(lang);
      }}
      options={[
        { value: "uz", label: t("lang.uz") },
        { value: "ru", label: t("lang.ru") },
      ]}
    />
  );
}

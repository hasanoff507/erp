import { changeLanguage, isUiLanguage, useTranslation, type UiLanguage } from "@shared/i18n";
import { SegmentedControl } from "@shared/ui";

/** «UZ · RU» (06 §1.4) — same control as the shell's language switcher, local to the public pages. */
export function LanguageToggle() {
  const { t, i18n } = useTranslation();
  const value: UiLanguage = isUiLanguage(i18n.resolvedLanguage) ? i18n.resolvedLanguage : "uz";
  return (
    <SegmentedControl<UiLanguage>
      label={t("lang.groupLabel")}
      value={value}
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

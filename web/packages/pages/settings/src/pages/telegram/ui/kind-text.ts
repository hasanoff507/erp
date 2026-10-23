import { useTranslation } from "@shared/i18n";

/** Event kind → «title» / «description» (`settings:telegram.kinds.*`); an unknown kind shows its code. */
export function useKindText() {
  const { t, i18n } = useTranslation("settings");
  const tr = t as (k: string) => string;
  return (kind: string) => {
    const base = `telegram.kinds.${kind}`;
    return i18n.exists(`${base}.title`, { ns: "settings" })
      ? { title: tr(`${base}.title`), description: tr(`${base}.description`) }
      : { title: kind, description: "" };
  };
}

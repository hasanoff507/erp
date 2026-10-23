/** `useTranslation("edocs")` with string keys (keys are built from API enums — statuses, reasons). */
import { useTranslation } from "@shared/i18n";

export type Tx = (key: string, options?: Record<string, unknown>) => string;

export function useTx(): { t: Tx; exists: (key: string) => boolean } {
  const { t, i18n } = useTranslation("edocs");
  return {
    t: t as unknown as Tx,
    exists: (key: string) => i18n.exists(`edocs:${key}`),
  };
}

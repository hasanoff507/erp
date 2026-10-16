import { useUnit } from "effector-react";
import { Check } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatDate } from "@shared/lib/format";
import { formatPhone } from "@shared/lib/phone";
import { $session } from "@shared/state/session";
import { Button, Icon } from "@shared/ui";

import {
  $account,
  $method,
  $otp,
  $signup,
  $step,
  $storeDraft,
  stepEditRequested,
} from "../../model/index.ts";

/** «1-bosqich bajarildi: …  [O'zgartirish]» on ②; «Do'kon yaratildi: …» on ③–⑥ (mockup Bo21Royxat). */
export function Summary() {
  const { t } = useTranslation("onboarding");
  const [step, account, otp, method, signup, store, session, edit] = useUnit([
    $step,
    $account,
    $otp,
    $method,
    $signup,
    $storeDraft,
    $session,
    stepEditRequested,
  ]);

  let content: string | null = null;
  let label: string | null = null;
  if (step === "store" && account) {
    label = t("summary.account");
    content = [
      account.ownerName,
      formatPhone(account.phone),
      otp ? t(`summary.codeVia.${otp.channel}`) : null,
      method === "google" ? t("summary.google") : t("summary.passwordSet"),
    ]
      .filter(Boolean)
      .join(" · ");
  } else if (step !== "account" && step !== "store") {
    const name = store?.storeName ?? session?.tenant.name ?? null;
    if (name) {
      label = t("summary.store");
      content = [name, signup ? t("summary.trialUntil", { date: formatDate(signup.trial_ends_at) }) : null]
        .filter(Boolean)
        .join(" · ");
    }
  }
  if (!content || !label) return null;

  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card px-3.5 py-2.5">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-success-soft text-success">
        <Icon as={Check} size="sm" />
      </span>
      <span className="min-w-0 grow text-[13px] text-foreground-secondary">
        <b className="text-foreground">{label}</b> <span className="tabular-nums">{content}</span>
      </span>
      {step === "store" ? (
        <Button type="button" size="sm" variant="secondary" onClick={() => edit("account")}>
          {t("wizard.change")}
        </Button>
      ) : null}
    </div>
  );
}

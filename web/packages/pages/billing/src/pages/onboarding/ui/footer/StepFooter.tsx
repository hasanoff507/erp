import { useTranslation } from "@shared/i18n";
import { Button, Kbd } from "@shared/ui";

export interface StepFooterProps {
  onBack?: () => void;
  onSkip?: () => void;
  primaryLabel?: string;
  primaryDisabled?: boolean;
  pending?: boolean;
  /** `submit` inside a <form> (Enter submits, 07 «Klaviatura»); `button` otherwise. */
  primaryType?: "submit" | "button";
  onPrimary?: () => void;
  /** Focus «Davom» on steps without inputs, so Enter goes to the next step. */
  autoFocusPrimary?: boolean;
}

/** «Orqaga» · «O'tkazib yuborish» · «Keyingi bosqich [Enter]» · «Davom» (mockup Bo21Royxat). */
export function StepFooter({
  onBack,
  onSkip,
  primaryLabel,
  primaryDisabled = false,
  pending = false,
  primaryType = "submit",
  onPrimary,
  autoFocusPrimary = false,
}: StepFooterProps) {
  const { t } = useTranslation("onboarding");
  return (
    <div className="mt-2 flex flex-wrap items-center gap-3">
      {onBack ? (
        <Button type="button" variant="secondary" onClick={onBack} disabled={pending}>
          {t("wizard.back")}
        </Button>
      ) : null}
      <div className="grow" />
      {onSkip ? (
        <Button type="button" variant="ghost" onClick={onSkip} disabled={pending}>
          {t("wizard.skip")}
        </Button>
      ) : null}
      <span className="hidden items-center gap-1.5 text-[12px] text-muted-foreground sm:inline-flex">
        {t("wizard.nextHint")}
        <Kbd keys="Enter" />
      </span>
      <Button
        type={primaryType}
        onClick={onPrimary}
        disabled={primaryDisabled || pending}
        autoFocus={autoFocusPrimary}
        aria-busy={pending || undefined}
        className="px-7"
      >
        {primaryLabel ?? t("wizard.next")}
      </Button>
    </div>
  );
}

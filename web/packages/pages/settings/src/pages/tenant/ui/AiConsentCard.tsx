import { useUnit } from "effector-react";
import { ExternalLink, ShieldCheck, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatDateTime } from "@shared/lib/date";
import {
  Banner,
  Button,
  Card,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Icon,
  StatusChip,
  Switch,
  toast,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import { $aiTerms, $lastConsent, createConsentFx, type TenantSettings } from "../model/index.ts";

/**
 * «Ma'lumotni AI xizmatiga (chet elga) uzatishga rozilik» (07 BO-14 `aiCrossBorderEnabled`, qaror #61):
 * owner only; turning it on shows the consent text of the current `ai_cross_border` terms version;
 * saved only through POST /tenant/consents — never through PATCH /tenant/settings.
 */
export function AiConsentCard({ settings }: { settings: TenantSettings }) {
  const { t } = useTranslation("settings");
  const [terms, lastConsent] = useUnit([$aiTerms, $lastConsent]);
  const online = useOnline();
  const [dialog, setDialog] = useState<"give" | "withdraw" | null>(null);
  const enabled = settings.settings.ai_cross_border_enabled;

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-start gap-3">
        <Switch
          id="ai-cross-border"
          checked={enabled}
          disabled={!online || terms === null}
          onCheckedChange={(next) => setDialog(next ? "give" : "withdraw")}
          className="mt-0.5"
        />
        <label htmlFor="ai-cross-border" className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="text-[14px] font-bold">{t("tenant.ai.label")}</span>
          <span className="text-[12px] text-muted-foreground">{t("tenant.ai.hint")}</span>
        </label>
        <StatusChip tone={enabled ? "success" : "neutral"} icon={enabled ? ShieldCheck : undefined}>
          {enabled ? t("tenant.ai.given") : t("tenant.ai.notGiven")}
        </StatusChip>
      </div>
      {lastConsent?.at ? (
        <p className="text-[12px] text-foreground-secondary">
          {t("tenant.ai.lastChange", {
            at: formatDateTime(lastConsent.at),
            version: lastConsent.terms_version,
          })}
        </p>
      ) : null}
      {terms === null ? (
        <p className="text-[12px] text-muted-foreground">{t("tenant.ai.termsUnavailable")}</p>
      ) : null}
      <p className="text-[12px] text-muted-foreground">{t("tenant.ai.maskingNote")}</p>
      {dialog && terms ? (
        <ConsentDialog
          accept={dialog === "give"}
          termsVersion={terms.version}
          termsUrl={terms.text_url}
          effectiveFrom={terms.effective_from}
          onClose={() => setDialog(null)}
        />
      ) : null}
    </Card>
  );
}

function ConsentDialog({
  accept,
  termsVersion,
  termsUrl,
  effectiveFrom,
  onClose,
}: {
  accept: boolean;
  termsVersion: string;
  termsUrl: string;
  effectiveFrom: string;
  onClose: () => void;
}) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const [save, pending] = useUnit([createConsentFx, createConsentFx.pending]);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    try {
      await save({ accepted: accept, termsVersion });
      toast.success(accept ? t("tenant.ai.givenToast") : t("tenant.ai.withdrawnToast"));
      onClose();
    } catch (e) {
      setError(errorText(e));
    }
  };

  return (
    <Dialog open onOpenChange={(o) => (o || pending ? undefined : onClose())}>
      <DialogContent size="md">
        <DialogHeader>
          <DialogTitle>{accept ? t("tenant.ai.giveTitle") : t("tenant.ai.withdrawTitle")}</DialogTitle>
          <DialogDescription>
            {accept ? t("tenant.ai.giveText") : t("tenant.ai.withdrawText")}
          </DialogDescription>
        </DialogHeader>
        {accept ? (
          <div className="flex flex-col gap-1.5 rounded-lg bg-accent px-4 py-3 text-[13px]">
            <span>
              {t("tenant.ai.termsVersion", { version: termsVersion, date: formatDate(effectiveFrom) })}
            </span>
            <a
              href={termsUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 font-semibold"
            >
              {t("tenant.ai.readTerms")}
              <Icon as={ExternalLink} size="sm" />
            </a>
          </div>
        ) : null}
        {error ? (
          <Banner tone="destructive" icon={TriangleAlert} live="assertive">
            {error}
          </Banner>
        ) : null}
        <DialogFooter>
          <Button variant="secondary" disabled={pending} onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button
            variant={accept ? "default" : "destructive"}
            disabled={pending}
            onClick={() => void submit()}
          >
            {accept ? t("tenant.ai.giveConfirm") : t("tenant.ai.withdrawConfirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

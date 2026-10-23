/**
 * `/recover` (BO-01 «Parolni unutdim») and `/invite` («Taklif kodi bor») — the SPA pages the
 * server-rendered AS login page links to (backend auth/api/login_page.py RECOVERY_PATH / INVITE_PATH).
 * Flow and invite-code constraints: features/credential-set/model.
 */
import { useUnit } from "effector-react";
import { Info } from "lucide-react";
import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

import { loginStartUrl } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { Banner } from "@shared/ui";

import { challengeFromLink } from "#/features/credential-set/model/index.ts";
import { CredentialSetFlow } from "#/features/credential-set/ui/CredentialSetFlow.tsx";
import { PublicFrame } from "#/shared/ui/PublicFrame.tsx";

import { inviteModel, recoverModel } from "../model/index.ts";

function BackToLogin() {
  const { t } = useTranslation("onboarding");
  return (
    <p className="text-center text-[14px]">
      <a href={loginStartUrl({ returnTo: "/" })}>{t("credentials.toLogin")}</a>
    </p>
  );
}

function RecoverPage() {
  const { t } = useTranslation("onboarding");
  const mounted = useUnit(recoverModel.pageMounted);
  useEffect(() => {
    mounted({ challengeId: null });
  }, [mounted]);
  return (
    <PublicFrame title={t("recover.title")}>
      <div className="flex flex-col gap-1.5">
        <h1 className="text-[28px] font-extrabold leading-tight">{t("recover.title")}</h1>
        <p className="text-[14px] text-foreground-secondary">{t("recover.subtitle")}</p>
      </div>
      <CredentialSetFlow model={recoverModel} doneText={t("recover.done")} />
      <BackToLogin />
    </PublicFrame>
  );
}

function InvitePage() {
  const { t } = useTranslation("onboarding");
  const [params] = useSearchParams();
  const challengeId = challengeFromLink(params.get("challenge_id"));
  const [mounted, stage] = useUnit([inviteModel.pageMounted, inviteModel.$stage]);
  useEffect(() => {
    mounted({ challengeId });
  }, [mounted, challengeId]);
  return (
    <PublicFrame title={t("invite.title")}>
      <div className="flex flex-col gap-1.5">
        <h1 className="text-[28px] font-extrabold leading-tight">{t("invite.title")}</h1>
        <p className="text-[14px] text-foreground-secondary">{t("invite.subtitle")}</p>
      </div>
      {challengeId === null && stage === "invite" ? (
        <Banner tone="info" icon={Info}>
          {t("invite.hint")}
        </Banner>
      ) : null}
      <CredentialSetFlow model={inviteModel} doneText={t("invite.done")} />
      <BackToLogin />
    </PublicFrame>
  );
}

export const Recover = {
  route: "/recover",
  titleKey: "onboarding:recover.title",
  Page: RecoverPage,
} as const;
export const Invite = { route: "/invite", titleKey: "onboarding:invite.title", Page: InvitePage } as const;

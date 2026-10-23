/**
 * BO-21 ① (07 fields `signupMethod`, `phone`, `otp`, `password`, `ownerName`; 14 §4.2, §2.2).
 * Phone path: phone → «Kod olish» (Telegram bot first, SMS fallback) → 6-digit code (auto-verified
 * when complete) → password + name. Google path (`?method=google` after the callback): the Google
 * identity waits server-side, so only the phone (+ code) and the name are asked.
 */
import { useUnit } from "effector-react";
import { CircleCheck, Info, MessageSquare, Send, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { loginStartUrl } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { formatPhone, nationalDigits, toE164 } from "@shared/lib/phone";
import { googleStartUrl, telegramBotLink } from "@shared/lib/runtime-config";
import {
  Banner,
  Button,
  FormField,
  Icon,
  OtpInput,
  PasswordInput,
  PhoneInput,
  StatusChip,
  Input,
} from "@shared/ui";
import { RhfField, useZodForm, z, zPhone } from "@shared/ui/form";

import { errorText, fieldError } from "#/shared/lib/errors.ts";

import {
  $account,
  $method,
  $otp,
  $otpError,
  $resendIn,
  $signupError,
  $signupFailure,
  accountSubmitted,
  formatCountdown,
  methodSelected,
  otpCodeSubmitted,
  otpRequested,
  phoneChanged,
  requestOtpFx,
  verifyOtpFx,
} from "../../model/index.ts";
import { StepFooter } from "../footer/StepFooter.tsx";

const ownerName = z.string().trim().min(2).max(100);
const phoneSchema = z.object({
  phone: zPhone(),
  password: z.string().min(8, { message: "validation.password_too_short?min=8" }).max(128),
  ownerName,
});
const googleSchema = z.object({ phone: zPhone(), password: z.string(), ownerName });

function OtpBlock() {
  const { t } = useTranslation("onboarding");
  const [otp, otpError, resendIn, requesting, verifying, submitCode, resend] = useUnit([
    $otp,
    $otpError,
    $resendIn,
    requestOtpFx.pending,
    verifyOtpFx.pending,
    otpCodeSubmitted,
    otpRequested,
  ]);
  const [typed, setTyped] = useState<{ id: string; code: string }>({ id: "", code: "" });
  if (!otp) return null;
  const code = typed.id === otp.challengeId ? typed.code : "";
  const bot = telegramBotLink();

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-background/60 p-4">
      <p role="status" className="flex items-start gap-2 text-[14px]">
        <Icon
          as={otp.channel === "telegram" ? Send : MessageSquare}
          size="md"
          className="mt-0.5 shrink-0 text-info"
        />
        {otp.channel === "telegram"
          ? t("account.sentTelegram", { phone: formatPhone(otp.phone) })
          : t("account.sentSms", { phone: formatPhone(otp.phone) })}
      </p>
      {otp.telegramNotLinked ? (
        <p className="text-[13px] text-foreground-secondary">
          {t("account.telegramNotLinked")}{" "}
          {bot ? (
            <a href={bot.href} target="_blank" rel="noreferrer" className="font-bold">
              {t("account.telegramBotLink")} ({bot.label})
            </a>
          ) : null}
        </p>
      ) : null}

      {otp.verified ? (
        <StatusChip tone="success" icon={CircleCheck} className="self-start">
          {t("account.verified")}
        </StatusChip>
      ) : (
        <FormField
          label={t("account.otp")}
          required
          hint={verifying ? t("account.verifying") : t("account.otpHint")}
          error={otpError ? errorText(otpError) : null}
        >
          {(a11y) => (
            <OtpInput
              {...a11y}
              label={t("account.otp")}
              value={code}
              autoFocus
              disabled={verifying}
              onChange={(value) => setTyped({ id: otp.challengeId, code: value })}
              onComplete={(value) => submitCode(value)}
            />
          )}
        </FormField>
      )}

      {otp.verified ? null : (
        <Button
          type="button"
          variant="link"
          className="self-start"
          disabled={resendIn > 0 || requesting}
          onClick={() => resend(otp.phone)}
        >
          {resendIn > 0 ? t("account.resendIn", { time: formatCountdown(resendIn) }) : t("account.resend")}
        </Button>
      )}
    </div>
  );
}

function AccountForm() {
  const { t } = useTranslation("onboarding");
  const [
    method,
    account,
    otp,
    otpError,
    signupError,
    failure,
    requesting,
    selectMethod,
    request,
    changePhone,
    submit,
  ] = useUnit([
    $method,
    $account,
    $otp,
    $otpError,
    $signupError,
    $signupFailure,
    requestOtpFx.pending,
    methodSelected,
    otpRequested,
    phoneChanged,
    accountSubmitted,
  ]);
  const google = method === "google";
  const googleHref = googleStartUrl({ returnTo: "/" });
  const form = useZodForm(google ? googleSchema : phoneSchema, {
    defaultValues: {
      phone: account ? nationalDigits(account.phone) : "",
      password: account?.password ?? "",
      ownerName: account?.ownerName ?? "",
    },
  });
  const [verifyFirst, setVerifyFirst] = useState(false);

  const sendCode = async () => {
    if (await form.trigger("phone")) request(toE164(form.getValues("phone")));
  };

  const onSubmit = form.handleSubmit((values) => {
    const phone = toE164(values.phone);
    if (!otp?.verified || otp.phone !== phone) {
      setVerifyFirst(true);
      return;
    }
    setVerifyFirst(false);
    submit({ phone, ownerName: values.ownerName.trim(), password: google ? null : values.password });
  });

  // An OTP request error without a code on screen belongs under the phone field.
  const phoneServerError =
    fieldError(signupError, "phone") ?? (otpError && !otp ? errorText(otpError) : null);

  return (
    <form className="flex flex-col gap-4" onSubmit={(e) => void onSubmit(e)} noValidate>
      {google ? (
        <Banner tone="info" icon={Info}>
          {t("account.googleReturned")}{" "}
          <button type="button" className="font-bold underline" onClick={() => selectMethod("phone")}>
            {t("account.usePhoneInstead")}
          </button>
        </Banner>
      ) : googleHref ? (
        // Full-page navigation (like «Kirish»): GET /auth/google/start → Google → /auth/google/callback.
        // Hidden when this deployment has no Google sign-in (runtime config `googleEnabled`).
        <div role="group" aria-label={t("account.methodLabel")} className="flex flex-wrap gap-2.5">
          <Button
            type="button"
            variant="secondary"
            aria-pressed="true"
            className="border-primary bg-primary-soft"
          >
            {t("account.methodPhone")}
          </Button>
          <Button asChild variant="secondary">
            <a href={googleHref}>
              <span aria-hidden="true" className="font-extrabold text-info">
                G
              </span>
              {t("account.methodGoogle")}
            </a>
          </Button>
        </div>
      ) : null}

      {failure === "google_expired" ? (
        <Banner tone="warning" icon={TriangleAlert} live="assertive">
          {t("account.googleExpired")}
        </Banner>
      ) : null}
      {failure === "phone_taken" ? (
        <Banner
          tone="destructive"
          icon={TriangleAlert}
          live="assertive"
          action={
            <span className="flex gap-2">
              <Button asChild size="sm" variant="secondary">
                <a href={loginStartUrl({ returnTo: "/" })}>{t("account.login")}</a>
              </Button>
              <Button asChild size="sm" variant="secondary">
                <Link to="/recover">{t("account.recover")}</Link>
              </Button>
            </span>
          }
        >
          {t("account.phoneTaken")}
        </Banner>
      ) : null}
      {failure === "otp_stale" ? (
        <Banner tone="warning" icon={TriangleAlert} live="assertive">
          {t("account.otpStale")}
        </Banner>
      ) : null}

      <div className="flex flex-wrap items-end gap-3">
        <RhfField
          control={form.control}
          name="phone"
          label={t("account.phone")}
          required
          className="min-w-[240px] flex-1"
          render={({ field, control, fieldState }) => (
            <PhoneInput
              {...control}
              aria-invalid={control["aria-invalid"] ?? (phoneServerError ? true : undefined)}
              name={field.name}
              ref={field.ref}
              value={field.value}
              onBlur={field.onBlur}
              onChange={(digits) => {
                field.onChange(digits);
                changePhone(digits);
              }}
              data-invalid={fieldState.invalid || undefined}
            />
          )}
        />
        {otp ? null : (
          <Button type="button" onClick={() => void sendCode()} disabled={requesting} aria-busy={requesting}>
            {t("account.sendCode")}
          </Button>
        )}
      </div>
      {phoneServerError ? (
        <p role="alert" className="-mt-2 text-small font-semibold text-destructive">
          {phoneServerError}
        </p>
      ) : null}

      <OtpBlock />
      {verifyFirst && !otp?.verified ? (
        <p role="alert" className="text-small font-semibold text-destructive">
          {t("account.verifyFirst")}
        </p>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        {google ? null : (
          <RhfField
            control={form.control}
            name="password"
            label={t("account.password")}
            required
            hint={t("account.passwordHint")}
            render={({ field, control }) => (
              <PasswordInput {...control} {...field} maxLength={128} autoComplete="new-password" />
            )}
          />
        )}
        <RhfField
          control={form.control}
          name="ownerName"
          label={t("account.ownerName")}
          required
          render={({ field, control }) => (
            <Input
              {...control}
              {...field}
              maxLength={100}
              autoComplete="name"
              placeholder={t("account.ownerNamePlaceholder")}
            />
          )}
        />
      </div>
      {fieldError(signupError, "password", "owner_name") ? (
        <p role="alert" className="text-small font-semibold text-destructive">
          {fieldError(signupError, "password", "owner_name")}
        </p>
      ) : null}
      {signupError && failure === "general" ? (
        <Banner tone="destructive" icon={TriangleAlert} live="assertive">
          {errorText(signupError)}
        </Banner>
      ) : null}

      <StepFooter primaryLabel={t("wizard.next")} />
      <p className="text-[14px] text-foreground-secondary">
        {t("account.haveAccount")} <a href={loginStartUrl({ returnTo: "/" })}>{t("account.login")}</a>
      </p>
    </form>
  );
}

/** The schema depends on the method (no password on the Google path) → a fresh form per method. */
export function AccountStep() {
  const method = useUnit($method);
  return <AccountForm key={method} />;
}

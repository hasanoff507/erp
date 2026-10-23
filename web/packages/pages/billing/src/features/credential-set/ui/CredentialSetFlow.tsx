/**
 * /recover: phone → code; /invite: phone + code type + code (or a link with challenge_id) → new password and/or PIN (whatever `credential_kinds` allows) → done. Used by
 * /recover and /invite (model: ../model). An existing user's accepted invite ends at «sign in». Enter submits each stage.
 */
import { useUnit } from "effector-react";
import { CircleCheck, LogIn, MessageSquare, RotateCcw, Send, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { loginStartUrl } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { formatPhone, toE164 } from "@shared/lib/phone";
import { telegramBotLink } from "@shared/lib/runtime-config";
import {
  Banner,
  Button,
  Card,
  FormField,
  Icon,
  OtpInput,
  PasswordInput,
  PhoneInput,
  SimpleSelect,
} from "@shared/ui";
import { RhfField, useZodForm, z, zPhone } from "@shared/ui/form";

import { errorText, fieldError } from "#/shared/lib/errors.ts";

import {
  INVITE_CODE_PURPOSES,
  type CredentialKind,
  type CredentialSetModel,
  type InviteCodePurpose,
} from "../model/index.ts";

const phoneSchema = z.object({ phone: zPhone() });

/**
 * /invite without a link: phone + «Kod turi» + the 6-digit code from the owner's message →
 * POST /auth/otp/verify {phone, purpose, code} (latest open challenge for that phone + purpose).
 */
function InviteStage({ model }: { model: CredentialSetModel }) {
  const { t } = useTranslation("onboarding");
  const [error, pending, submit] = useUnit([model.$error, model.$pending, model.inviteCodeSubmitted]);
  const [purpose, setPurpose] = useState<InviteCodePurpose>("invite");
  const [code, setCode] = useState("");
  const form = useZodForm(phoneSchema, { defaultValues: { phone: "" } });
  const verify = (value: string) =>
    void form.handleSubmit(({ phone }) => submit({ phone: toE164(phone), purpose, code: value }))();

  return (
    <form
      className="flex flex-col gap-4"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        verify(code);
      }}
    >
      <RhfField
        control={form.control}
        name="phone"
        label={t("credentials.phone")}
        required
        render={({ field, control }) => (
          <PhoneInput
            {...control}
            name={field.name}
            ref={field.ref}
            value={field.value}
            onBlur={field.onBlur}
            onChange={field.onChange}
            autoFocus
          />
        )}
      />
      <FormField label={t("credentials.codeType")} required hint={t("credentials.codeTypeHint")}>
        {(a11y) => (
          <SimpleSelect
            {...a11y}
            value={purpose}
            onValueChange={(v) => setPurpose(v as InviteCodePurpose)}
            options={INVITE_CODE_PURPOSES.map((value) => ({
              value,
              label: t(`credentials.codeTypes.${value}`),
            }))}
          />
        )}
      </FormField>
      <FormField
        label={t("credentials.code")}
        required
        hint={t("credentials.codeHint")}
        error={error ? (fieldError(error, "phone") ?? errorText(error)) : null}
      >
        {(a11y) => (
          <OtpInput
            {...a11y}
            label={t("credentials.code")}
            value={code}
            onChange={setCode}
            onComplete={verify}
            disabled={pending}
          />
        )}
      </FormField>
      <Button type="submit" disabled={pending || code.length !== 6} aria-busy={pending}>
        {t("credentials.verify")}
      </Button>
      <p className="text-[13px] text-foreground-secondary">
        {t("invite.noCode")} <Link to="/recover">{t("invite.noCodeLink")}</Link>
      </p>
    </form>
  );
}

function PhoneStage({ model }: { model: CredentialSetModel }) {
  const { t } = useTranslation("onboarding");
  const [error, pending, submit] = useUnit([model.$error, model.$pending, model.phoneSubmitted]);
  const form = useZodForm(phoneSchema, { defaultValues: { phone: "" } });
  const onSubmit = form.handleSubmit(({ phone }) => submit(toE164(phone)));
  return (
    <form className="flex flex-col gap-4" onSubmit={(e) => void onSubmit(e)} noValidate>
      <RhfField
        control={form.control}
        name="phone"
        label={t("credentials.phone")}
        required
        render={({ field, control }) => (
          <PhoneInput
            {...control}
            name={field.name}
            ref={field.ref}
            value={field.value}
            onBlur={field.onBlur}
            onChange={field.onChange}
            autoFocus
          />
        )}
      />
      {error ? (
        <Banner tone="destructive" icon={TriangleAlert} live="assertive">
          {fieldError(error, "phone") ?? errorText(error)}
        </Banner>
      ) : null}
      <Button type="submit" disabled={pending} aria-busy={pending}>
        {t("credentials.sendCode")}
      </Button>
    </form>
  );
}

function CodeStage({ model }: { model: CredentialSetModel }) {
  const { t } = useTranslation("onboarding");
  const [challenge, error, pending, submit, resend] = useUnit([
    model.$challenge,
    model.$error,
    model.$pending,
    model.codeSubmitted,
    model.resendRequested,
  ]);
  const [code, setCode] = useState("");
  if (!challenge) return null;
  const bot = telegramBotLink();
  const sent =
    challenge.phone === null
      ? t("credentials.sentLinked")
      : challenge.channel === "telegram"
        ? t("credentials.sentTelegram", { phone: formatPhone(challenge.phone) })
        : t("credentials.sentSms", { phone: formatPhone(challenge.phone) });

  return (
    <form
      className="flex flex-col gap-4"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit(code);
      }}
    >
      <p role="status" className="flex items-start gap-2 text-[14px]">
        <Icon
          as={challenge.channel === "telegram" ? Send : MessageSquare}
          size="md"
          className="mt-0.5 shrink-0 text-info"
        />
        {sent}
      </p>
      {challenge.telegramNotLinked && bot ? (
        <p className="text-[13px] text-foreground-secondary">
          {t("credentials.telegramNotLinked")}{" "}
          <a href={bot.href} target="_blank" rel="noreferrer" className="font-bold">
            {bot.label}
          </a>
        </p>
      ) : null}
      <FormField
        label={t("credentials.code")}
        required
        hint={t("credentials.codeHint")}
        error={error ? errorText(error) : null}
      >
        {(a11y) => (
          <OtpInput
            {...a11y}
            label={t("credentials.code")}
            value={code}
            onChange={setCode}
            onComplete={(value) => submit(value)}
            autoFocus
            disabled={pending}
          />
        )}
      </FormField>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={pending || code.length !== 6} aria-busy={pending}>
          {t("credentials.verify")}
        </Button>
        {challenge.phone !== null ? (
          <Button type="button" variant="link" disabled={pending} onClick={() => resend()}>
            {t("credentials.resend")}
          </Button>
        ) : null}
      </div>
    </form>
  );
}

const PIN = /^[0-9]{4,6}$/;

function credentialsSchema(kinds: readonly CredentialKind[], pinMessage: string) {
  const needsPassword = kinds.length === 1 && kinds[0] === "password";
  const needsPin = kinds.length === 1 && kinds[0] === "pin";
  return z
    .object({ password: z.string(), passwordConfirm: z.string(), pin: z.string() })
    .superRefine((v, ctx) => {
      const password = v.password !== "" || needsPassword;
      if (kinds.includes("password") && password) {
        if (v.password.length < 8)
          ctx.addIssue({
            code: "custom",
            path: ["password"],
            message: "validation.password_too_short?min=8",
          });
        else if (v.password.length > 128)
          ctx.addIssue({ code: "custom", path: ["password"], message: "validation.max_length" });
        if (v.passwordConfirm !== v.password)
          ctx.addIssue({
            code: "custom",
            path: ["passwordConfirm"],
            message: "validation.password_mismatch",
          });
      }
      if (kinds.includes("pin") && (v.pin !== "" || needsPin) && !PIN.test(v.pin)) {
        ctx.addIssue({ code: "custom", path: ["pin"], message: pinMessage });
      }
      // invite: password and/or PIN — at least one (backend credentials.py `_validate`).
      if (kinds.length > 1 && v.password === "" && v.pin === "") {
        ctx.addIssue({ code: "custom", path: ["password"], message: "validation.required" });
      }
    });
}

function CredentialsStage({ model }: { model: CredentialSetModel }) {
  const { t } = useTranslation("onboarding");
  const [session, error, pending, submit] = useUnit([
    model.$session,
    model.$error,
    model.$pending,
    model.credentialsSubmitted,
  ]);
  const kinds = session?.kinds ?? ["password"];
  const form = useZodForm(credentialsSchema(kinds, t("credentials.pinFormat")), {
    defaultValues: { password: "", passwordConfirm: "", pin: "" },
  });
  const onSubmit = form.handleSubmit((v) =>
    submit({
      ...(kinds.includes("password") && v.password !== "" ? { password: v.password } : {}),
      ...(kinds.includes("pin") && v.pin !== "" ? { pin: v.pin } : {}),
    }),
  );
  const serverField = fieldError(error, "password", "pin");

  return (
    <form className="flex flex-col gap-4" onSubmit={(e) => void onSubmit(e)} noValidate>
      {kinds.includes("password") ? (
        <>
          <RhfField
            control={form.control}
            name="password"
            label={t("credentials.password")}
            required={kinds.length === 1}
            hint={t("credentials.passwordHint")}
            render={({ field, control }) => (
              <PasswordInput {...control} {...field} maxLength={128} autoComplete="new-password" autoFocus />
            )}
          />
          <RhfField
            control={form.control}
            name="passwordConfirm"
            label={t("credentials.passwordConfirm")}
            required={kinds.length === 1}
            render={({ field, control }) => (
              <PasswordInput {...control} {...field} maxLength={128} autoComplete="new-password" />
            )}
          />
        </>
      ) : null}
      {kinds.includes("pin") ? (
        <RhfField
          control={form.control}
          name="pin"
          label={t("credentials.pin")}
          required={kinds.length === 1}
          hint={t("credentials.pinHint")}
          render={({ field, control }) => (
            <PasswordInput
              {...control}
              {...field}
              inputMode="numeric"
              maxLength={6}
              autoComplete="off"
              autoFocus={!kinds.includes("password")}
            />
          )}
        />
      ) : null}
      {error ? (
        <Banner tone="destructive" icon={TriangleAlert} live="assertive">
          {serverField ?? errorText(error)}
        </Banner>
      ) : null}
      <Button type="submit" disabled={pending} aria-busy={pending}>
        {t("credentials.save")}
      </Button>
    </form>
  );
}

/** Final state: a success message + «Tizimga kirish» (AS login start). */
function SignInNext({ text }: { text: string }) {
  const { t } = useTranslation("onboarding");
  return (
    <div className="flex flex-col gap-4">
      <Banner tone="success" icon={CircleCheck} live="assertive">
        {text}
      </Banner>
      <Button asChild>
        <a href={loginStartUrl({ returnTo: "/" })}>
          <Icon as={LogIn} size="md" />
          {t("credentials.login")}
        </a>
      </Button>
    </div>
  );
}

export function CredentialSetFlow({ model, doneText }: { model: CredentialSetModel; doneText: string }) {
  const { t } = useTranslation("onboarding");
  const [stage, expired, restart] = useUnit([model.$stage, model.$sessionExpired, model.restarted]);

  return (
    <Card className="flex flex-col gap-4">
      {expired ? (
        <Banner tone="warning" icon={RotateCcw} live="assertive">
          {t("credentials.sessionExpired")}
        </Banner>
      ) : null}
      {stage === "phone" ? <PhoneStage model={model} /> : null}
      {stage === "invite" ? <InviteStage model={model} /> : null}
      {stage === "code" ? <CodeStage model={model} /> : null}
      {stage === "credentials" ? <CredentialsStage model={model} /> : null}
      {stage === "done" ? <SignInNext text={doneText} /> : null}
      {/* An existing user's invite (invite_accepted, no credential_token): sign in as usual. */}
      {stage === "accepted" ? <SignInNext text={t("invite.accepted")} /> : null}
      {stage === "code" || stage === "credentials" ? (
        <Button type="button" variant="link" className="self-start" onClick={() => restart()}>
          {t("credentials.startOver")}
        </Button>
      ) : null}
    </Card>
  );
}

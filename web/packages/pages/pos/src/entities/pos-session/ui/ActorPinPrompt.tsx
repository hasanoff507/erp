/**
 * Online PIN re-prompt (device-auth.md §4, `actor_not_verified`): the cashier types the PIN again, `POST
 * /auth/pin/verify` binds her to the device session, the waiting REST call is retried by the interceptor.
 * Mounted once by the POS shell (b3-pos-sale bootstrap) — also used by POS screens' REST writes.
 */
import { useUnit } from "effector-react";
import { CircleAlert, KeyRound } from "lucide-react";
import { useEffect, useState } from "react";

import { api, toApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { storePinVerifier } from "@shared/offline";
import {
  Banner,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Icon,
} from "@shared/ui";

import { $actorPrompt, registerActorPrompt, settleActorPrompt } from "../model/actor-prompt.ts";
import { $posCashier } from "../model/index.ts";
import { PinPad } from "./PinPad.tsx";

type PromptError = "invalid" | "locked" | "busy" | "failed";

export function ActorPinPrompt() {
  const { t } = useTranslation("pos");
  const [prompt, cashier] = useUnit([$actorPrompt, $posCashier]);
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<PromptError | null>(null);

  useEffect(() => registerActorPrompt(), []);
  if (!prompt) return null;

  const submit = async () => {
    if (pin.length < 4 || busy) return;
    setBusy(true);
    try {
      const out = await api.auth.pinVerify({ user_id: prompt.userId, pin });
      if (out.pin_local_hash) await storePinVerifier(prompt.userId, out.pin_local_hash);
      setPin("");
      setError(null);
      settleActorPrompt(true);
    } catch (e) {
      const code = toApiError(e).code;
      setPin("");
      setError(
        code === "PIN_INVALID"
          ? "invalid"
          : code === "ACCOUNT_LOCKED"
            ? "locked"
            : code === "RATE_LIMITED"
              ? "busy"
              : "failed",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : settleActorPrompt(false))}>
      <DialogContent size="sm" data-testid="actor-pin-prompt">
        <DialogHeader>
          <DialogTitle>{t("login.actorPrompt.title")}</DialogTitle>
          <DialogDescription>
            {t("login.actorPrompt.text", { name: cashier?.fullName ?? "" })}
          </DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col items-center gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <input
            type="password"
            inputMode="numeric"
            autoComplete="off"
            aria-label={t("login.pinLabel")}
            data-testid="actor-pin"
            maxLength={6}
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
            className="sr-only"
            autoFocus
          />
          <PinPad
            value={pin}
            onChange={setPin}
            disabled={busy}
            label={t("login.pinLabel")}
            backspaceLabel={t("login.backspace")}
          />
          {error ? (
            <Banner tone="destructive" icon={CircleAlert} live="assertive" className="w-full">
              {t(`login.actorPrompt.errors.${error}`)}
            </Banner>
          ) : null}
        </form>
        <DialogFooter>
          <Button variant="secondary" size="lg" onClick={() => settleActorPrompt(false)}>
            {t("login.actorPrompt.cancel")}
          </Button>
          <Button
            size="lg"
            disabled={pin.length < 4 || busy}
            onClick={() => void submit()}
            data-testid="actor-pin-submit"
          >
            <Icon as={KeyRound} size="md" />
            {t("login.signIn")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

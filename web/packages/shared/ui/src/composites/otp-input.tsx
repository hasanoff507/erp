/**
 * OtpInput — 6-digit confirmation code (BO-21 step 1, 14 OTP via Telegram/SMS). One box per digit
 * (48×52, text-h2, tabular-nums), paste of the whole code fills every box, Backspace on an empty box
 * goes back, ←/→ move. `onComplete` fires once all digits are present. The first box carries
 * `autocomplete="one-time-code"` (iOS/Android SMS autofill).
 */
import { useRef, type ClipboardEvent, type KeyboardEvent } from "react";

import { useTranslation } from "@shared/i18n";
import { onlyDigits } from "@shared/lib/phone";

import { cn } from "#/lib/cn.ts";

export interface OtpInputProps {
  value: string;
  onChange: (value: string) => void;
  onComplete?: (value: string) => void;
  length?: number;
  disabled?: boolean;
  autoFocus?: boolean;
  /** Group label (default "Tasdiqlash kodi"). */
  label?: string;
  id?: string;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
  className?: string;
}

export function OtpInput({
  value,
  onChange,
  onComplete,
  length = 6,
  disabled = false,
  autoFocus = false,
  label,
  id,
  className,
  ...aria
}: OtpInputProps) {
  const { t } = useTranslation("common");
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const digits = onlyDigits(value).slice(0, length);

  const focusAt = (i: number) => refs.current[Math.max(0, Math.min(length - 1, i))]?.focus();

  const commit = (next: string) => {
    const clean = onlyDigits(next).slice(0, length);
    onChange(clean);
    if (clean.length === length) onComplete?.(clean);
  };

  const setDigitAt = (index: number, typed: string) => {
    const incoming = onlyDigits(typed);
    if (incoming === "") return;
    // Typing several characters at once (autofill) behaves like paste from this position.
    const next = (digits.slice(0, index) + incoming).slice(0, length);
    commit(next + digits.slice(next.length));
    focusAt(index + incoming.length);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>, index: number) => {
    if (event.key === "Backspace") {
      event.preventDefault();
      if (digits.charAt(index)) {
        commit(digits.slice(0, index) + digits.slice(index + 1));
      } else if (index > 0) {
        commit(digits.slice(0, index - 1) + digits.slice(index));
        focusAt(index - 1);
      }
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      focusAt(index - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      focusAt(index + 1);
    }
  };

  const onPaste = (event: ClipboardEvent<HTMLInputElement>) => {
    event.preventDefault();
    const pasted = onlyDigits(event.clipboardData.getData("text")).slice(0, length);
    if (pasted === "") return;
    commit(pasted);
    focusAt(pasted.length);
  };

  return (
    <div
      role="group"
      id={id}
      aria-label={label ?? t("ui.otp.label")}
      aria-describedby={aria["aria-describedby"]}
      className={cn("flex gap-2", className)}
    >
      {Array.from({ length }, (_, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          type="text"
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          maxLength={length}
          autoFocus={autoFocus && i === 0}
          disabled={disabled}
          aria-label={t("ui.otp.digit", { n: i + 1 })}
          aria-invalid={aria["aria-invalid"]}
          value={digits.charAt(i)}
          onChange={(e) => setDigitAt(i, e.target.value.replace(digits.charAt(i), ""))}
          onKeyDown={(e) => onKeyDown(e, i)}
          onPaste={onPaste}
          onFocus={(e) => e.target.select()}
          className={cn(
            "h-[52px] w-12 rounded-lg border border-input bg-card text-center text-h2 font-extrabold tabular-nums text-foreground",
            "focus-visible:border-primary focus-visible:shadow-focus-soft focus-visible:outline-none",
            "aria-[invalid=true]:border-destructive disabled:cursor-not-allowed disabled:text-disabled-foreground",
          )}
        />
      ))}
    </div>
  );
}

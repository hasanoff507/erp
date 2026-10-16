/**
 * PasswordInput — Input with a show/hide icon button (aria-pressed, translated aria-label).
 * `autoComplete` defaults to "new-password" (signup/reset); pass "current-password" where needed.
 */
import { Eye, EyeOff } from "lucide-react";
import { useState, type Ref } from "react";

import { useTranslation } from "@shared/i18n";

import { Input, type InputProps } from "#/components/ui/input.tsx";
import { Icon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

export interface PasswordInputProps extends Omit<InputProps, "type"> {
  ref?: Ref<HTMLInputElement>;
}

export function PasswordInput({ className, autoComplete = "new-password", ...props }: PasswordInputProps) {
  const { t } = useTranslation("common");
  const [visible, setVisible] = useState(false);
  return (
    <div className={cn("relative flex w-full", className)}>
      <Input type={visible ? "text" : "password"} autoComplete={autoComplete} className="pr-12" {...props} />
      <button
        type="button"
        aria-pressed={visible}
        aria-label={visible ? t("ui.password.hide") : t("ui.password.show")}
        onClick={() => setVisible((v) => !v)}
        disabled={props.disabled}
        className="absolute right-1 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-md text-foreground-secondary hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
      >
        <Icon as={visible ? EyeOff : Eye} size="md" />
      </button>
    </div>
  );
}

/**
 * «Javobgar shaxs» (moddiy javobgar — kamomad 4730 ga, 13 §2.11 / §2.12): none, the current user, or a
 * staff member. The staff directory (`GET /admin/users`) needs `settings.users`; without it only
 * «Belgilanmagan» and the current user are offered.
 */
import { useUnit } from "effector-react";

import { useTranslation } from "@shared/i18n";
import { $user } from "@shared/state/session";
import { SimpleSelect } from "@shared/ui";

import { $staff } from "../model/index.ts";

export const NO_RESPONSIBLE = "none";

export interface ResponsibleSelectProps {
  value: string | null;
  onChange: (userId: string | null) => void;
  id?: string;
  disabled?: boolean;
  "aria-describedby"?: string;
}

export function ResponsibleSelect({ value, onChange, ...props }: ResponsibleSelectProps) {
  const { t } = useTranslation("warehouse");
  const [me, staff] = useUnit([$user, $staff]);
  const options = [
    { value: NO_RESPONSIBLE, label: t("responsible.none") },
    ...(me ? [{ value: me.id, label: t("responsible.me", { name: me.full_name }) }] : []),
    ...staff.filter((s) => s.user_id !== me?.id).map((s) => ({ value: s.user_id, label: s.name })),
  ];
  return (
    <SimpleSelect
      {...props}
      options={options}
      value={value ?? NO_RESPONSIBLE}
      onValueChange={(v) => onChange(v === NO_RESPONSIBLE ? null : v)}
    />
  );
}

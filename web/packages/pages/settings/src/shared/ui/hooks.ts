import { useUnit } from "effector-react";
import { useCallback } from "react";

import { useTranslation } from "@shared/i18n";
import { $isOnline } from "@shared/state/network";

import { systemRoleKey, type RoleLike } from "../lib/roles.ts";

/** Writes need the network (06: offline — "faqat ko'rish"). */
export function useOnline(): boolean {
  return useUnit($isOnline);
}

/** System roles in the UI language (`common:user.roles.*`), custom roles by their own name. */
export function useRoleName(): (role: RoleLike) => string {
  const { t } = useTranslation("common");
  return useCallback(
    (role: RoleLike) => {
      const key = systemRoleKey(role);
      return key ? t(`user.roles.${key}`) : role.name;
    },
    [t],
  );
}

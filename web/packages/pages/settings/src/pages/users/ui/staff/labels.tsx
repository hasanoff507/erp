import { useUnit } from "effector-react";
import { useCallback } from "react";

import { useTranslation } from "@shared/i18n";
import { StatusChip } from "@shared/ui";

import { useRoleName } from "#/shared/ui/hooks.ts";

import { $branches, $inviteChannels, $roles, staffDisplayStatus, type Staff } from "../../model/index.ts";

/** Role / branch names of a staff row ("Kassir, Omborchi" · "Barcha filiallar"). */
export function useStaffLabels() {
  const { t } = useTranslation("settings");
  const [roles, branches] = useUnit([$roles, $branches]);
  const roleName = useRoleName();

  const rolesOf = useCallback(
    (staff: Staff) =>
      staff.role_ids
        .map((id) => roles.find((r) => r.id === id))
        .filter((r) => r !== undefined)
        .map(roleName)
        .join(", ") || "—",
    [roles, roleName],
  );

  const branchesOf = useCallback(
    (staff: Staff) => {
      if (branches.length > 1 && branches.every((b) => staff.branch_ids.includes(b.id))) {
        return t("users.table.allBranches");
      }
      return (
        staff.branch_ids
          .map((id) => branches.find((b) => b.id === id)?.name)
          .filter((n): n is string => n !== undefined)
          .join(", ") || "—"
      );
    },
    [branches, t],
  );

  return { roles: rolesOf, branches: branchesOf };
}

/**
 * Faol / Bloklangan / Taklif yuborildi (· Telegram|SMS when created in this visit) / Taklif yuborilgan
 * (membership `invited`: an existing user who has not redeemed the invite code yet).
 */
export function StaffStatusChip({ staff }: { staff: Staff }) {
  const { t } = useTranslation("settings");
  const channels = useUnit($inviteChannels);
  const status = staffDisplayStatus(staff);
  if (status === "blocked")
    return (
      <StatusChip tone="destructive" dot>
        {t("users.status.blocked")}
      </StatusChip>
    );
  if (status === "active")
    return (
      <StatusChip tone="success" dot>
        {t("users.status.active")}
      </StatusChip>
    );
  if (status === "pending")
    return (
      <StatusChip tone="info" dot>
        {t("users.status.pending")}
      </StatusChip>
    );
  const channel = channels[staff.user_id];
  return (
    <StatusChip tone="info" dot>
      {channel ? t(`users.status.invitedVia.${channel}`) : t("users.status.invited")}
    </StatusChip>
  );
}

import { useUnit } from "effector-react";
import { Ban, KeyRound, LockOpen, MonitorSmartphone, Pencil, RotateCcwKey } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatDateTime } from "@shared/lib/date";
import { formatPhone } from "@shared/lib/phone";
import { $user } from "@shared/state/session";
import {
  Avatar,
  Button,
  EmptyState,
  ErrorState,
  Icon,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  StatusChip,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $selectedUser,
  $userDevices,
  $userDevicesError,
  fetchUserDevicesFx,
  staffActionsFor,
  staffName,
  userSelected,
  type Staff,
} from "../../model/index.ts";
import { SessionsPanel } from "../sessions/SessionsPanel.tsx";
import type { StaffActionKind } from "./StaffActionDialog.tsx";
import { StaffStatusChip, useStaffLabels } from "./labels.tsx";

/** Staff detail (mockup Bo11 right panel): actions, active sessions and the user's devices. */
export function StaffSheet({
  onAction,
  onEdit,
}: {
  onAction: (kind: StaffActionKind, staff: Staff) => void;
  onEdit: (staff: Staff) => void;
}) {
  const { t } = useTranslation("settings");
  const [staff, me, select] = useUnit([$selectedUser, $user, userSelected]);
  const online = useOnline();
  const labels = useStaffLabels();

  const isSelf = staff !== null && me?.id === staff.user_id;
  const allowed = staff ? staffActionsFor(staff) : null;

  return (
    <Sheet open={staff !== null} onOpenChange={(open) => (open ? undefined : select(null))}>
      <SheetContent wide>
        {staff ? (
          <>
            <SheetHeader>
              <div className="flex items-center gap-3">
                <Avatar name={staffName(staff)} size={36} />
                <div className="min-w-0">
                  <SheetTitle>{staffName(staff)}</SheetTitle>
                  <SheetDescription>
                    {formatPhone(staff.phone)} · {labels.roles(staff)} · {labels.branches(staff)}
                  </SheetDescription>
                </div>
              </div>
            </SheetHeader>
            <SheetBody className="flex flex-col gap-5">
              <div className="flex flex-wrap items-center gap-2">
                <StaffStatusChip staff={staff} />
                <span className="text-small text-foreground-secondary">
                  {staff.last_login_at
                    ? t("users.table.lastLoginAt", { at: formatDateTime(staff.last_login_at) })
                    : t("users.table.neverLoggedIn")}
                </span>
              </div>

              <div className="flex flex-wrap gap-2" role="group" aria-label={t("users.actions.groupLabel")}>
                <Button variant="secondary" size="sm" disabled={!online} onClick={() => onEdit(staff)}>
                  <Icon as={Pencil} size="sm" />
                  {t("users.actions.edit")}
                </Button>
                {allowed?.resetCredentials ? (
                  <>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={!online}
                      onClick={() => onAction("resetPin", staff)}
                    >
                      <Icon as={KeyRound} size="sm" />
                      {t("users.actions.resetPin")}
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={!online}
                      onClick={() => onAction("resetPassword", staff)}
                    >
                      <Icon as={RotateCcwKey} size="sm" />
                      {t("users.actions.resetPassword")}
                    </Button>
                  </>
                ) : null}
                {allowed?.unblock ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={!online}
                    onClick={() => onAction("unblock", staff)}
                  >
                    <Icon as={LockOpen} size="sm" />
                    {t("users.actions.unblock")}
                  </Button>
                ) : (
                  <Button
                    variant="destructive-outline"
                    size="sm"
                    disabled={!online || isSelf}
                    title={isSelf ? t("users.actions.cannotBlockSelf") : undefined}
                    onClick={() => onAction("block", staff)}
                  >
                    <Icon as={Ban} size="sm" />
                    {t("users.actions.block")}
                  </Button>
                )}
              </div>
              {isSelf ? (
                <p className="text-[12px] text-muted-foreground">{t("users.actions.cannotBlockSelf")}</p>
              ) : null}

              <SessionsPanel />
              <UserDevices />
            </SheetBody>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function UserDevices() {
  const { t } = useTranslation("settings");
  const [devices, error, loading, user, reload] = useUnit([
    $userDevices,
    $userDevicesError,
    fetchUserDevicesFx.pending,
    $selectedUser,
    fetchUserDevicesFx,
  ]);
  return (
    <section className="flex flex-col gap-2.5" aria-label={t("users.userDevices.title")}>
      <h3 className="text-[15px] font-bold">{t("users.userDevices.title")}</h3>
      {error ? (
        <ErrorState
          message={errorText(error)}
          onRetry={() => (user ? void reload(user.user_id).catch(() => undefined) : undefined)}
          className="py-6"
        />
      ) : devices.length === 0 ? (
        <EmptyState
          icon={MonitorSmartphone}
          title={loading ? t("users.userDevices.loading") : t("users.userDevices.empty")}
          className="py-6"
        />
      ) : (
        <ul className="flex flex-col divide-y divide-divider">
          {devices.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center gap-2 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="text-[14px] font-bold">{d.cash_register_name ?? t(`devices.kind.${d.kind}`)}</p>
                <p className="text-[12px] text-muted-foreground">
                  {[t(`devices.kind.${d.kind}`), d.app_version ? `v${d.app_version}` : null]
                    .filter(Boolean)
                    .join(" · ")}
                  {d.last_sync_at
                    ? ` · ${t("devices.lastSync", { at: formatDateTime(d.last_sync_at) })}`
                    : ""}
                </p>
              </div>
              {d.revoked_at ? (
                <StatusChip tone="destructive">{t("devices.status.revoked")}</StatusChip>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

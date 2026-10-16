import { useUnit } from "effector-react";
import { UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { useCan } from "@shared/state/permissions";
import { Button, Icon, NoPermissionState, Tabs, TabsContent, TabsList, TabsTrigger } from "@shared/ui";

import { PageHeader } from "#/shared/ui/PageHeader.tsx";
import { useOnline } from "#/shared/ui/hooks.ts";

import { USERS_TABS, pageMounted, type UsersTab } from "../../model/index.ts";
import { DevicesTab } from "../devices/DevicesTab.tsx";
import { RolesTab } from "../roles/RolesTab.tsx";
import { SessionsTab } from "../sessions/SessionsTab.tsx";
import { CreateStaffDialog } from "../staff/StaffDialogs.tsx";
import { StaffTab } from "../staff/StaffTab.tsx";

function isTab(value: string | null): value is UsersTab {
  return value !== null && (USERS_TABS as readonly string[]).includes(value);
}

/**
 * BO-11 — Foydalanuvchilar, huquqlar va sessiyalar (07, route /app/settings/users). Tabs: Xodimlar,
 * Rollar, Sessiyalar (`settings.users`, owner) and Qurilmalar (`devices.revoke`, owner/manager).
 * The active tab lives in `?tab=`. useEffect only fires pageMounted (24 §2).
 */
function UsersPage() {
  const { t } = useTranslation("settings");
  const canUsers = useCan({ permission: "settings.users" });
  const canDevices = useCan({ permission: "devices.revoke" });
  const online = useOnline();
  const mounted = useUnit(pageMounted);
  const [params, setParams] = useSearchParams();
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    mounted({ manageUsers: canUsers });
  }, [mounted, canUsers]);

  const available = USERS_TABS.filter((tab) => (tab === "devices" ? canDevices : canUsers));
  const requested = params.get("tab");
  const tab: UsersTab | undefined =
    isTab(requested) && available.includes(requested) ? requested : available[0];

  const header = (
    <PageHeader
      title={t("users.title")}
      description={t("users.description")}
      actions={
        canUsers ? (
          <Button disabled={!online} onClick={() => setAdding(true)}>
            <Icon as={UserPlus} size="sm" />
            {t("users.add")}
          </Button>
        ) : null
      }
    />
  );

  if (!tab) {
    return (
      <div className="flex flex-col gap-[18px]">
        {header}
        <NoPermissionState />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-[18px]">
      {header}
      <Tabs value={tab} onValueChange={(value) => setParams({ tab: value }, { replace: true })}>
        <TabsList aria-label={t("users.tabs.label")}>
          {available.map((key) => (
            <TabsTrigger key={key} value={key}>
              {t(`users.tabs.${key}`)}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="staff" className="mt-3.5">
          <StaffTab onAdd={() => setAdding(true)} />
        </TabsContent>
        <TabsContent value="roles" className="mt-3.5">
          <RolesTab />
        </TabsContent>
        <TabsContent value="devices" className="mt-3.5">
          <DevicesTab />
        </TabsContent>
        <TabsContent value="sessions" className="mt-3.5">
          <SessionsTab />
        </TabsContent>
      </Tabs>
      <CreateStaffDialog open={adding} onOpenChange={setAdding} />
    </div>
  );
}

export const Users = {
  route: "settings/users",
  titleKey: "settings:users.title",
  Page: UsersPage,
} as const;

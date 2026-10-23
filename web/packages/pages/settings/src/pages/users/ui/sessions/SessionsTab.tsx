import { useUnit } from "effector-react";
import { MonitorSmartphone } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatPhone } from "@shared/lib/phone";
import { Card, EmptyState, FormField, NativeSelect } from "@shared/ui";

import { $sessionsUserId, $staff, sessionsUserChanged, staffName } from "../../model/index.ts";
import { SessionsPanel } from "./SessionsPanel.tsx";

/**
 * BO-11 «Sessiyalar» tab (06 §4): login sessions of a chosen staff member (there is no tenant-wide
 * session list in 14 §18.2 — one user at a time, `GET /admin/users/{id}/sessions`).
 */
export function SessionsTab() {
  const { t } = useTranslation("settings");
  const [staff, userId, change] = useUnit([$staff, $sessionsUserId, sessionsUserChanged]);

  const options = [
    { value: "", label: t("users.sessions.pickUser") },
    ...staff.map((s) => ({ value: s.user_id, label: `${staffName(s)} · ${formatPhone(s.phone)}` })),
  ];

  return (
    <Card className="flex flex-col gap-4">
      <FormField label={t("users.sessions.user")} className="max-w-md">
        <NativeSelect
          options={options}
          value={userId ?? ""}
          onChange={(e) => change(e.target.value === "" ? null : e.target.value)}
          wrapperClassName="w-full"
        />
      </FormField>
      {userId ? (
        <SessionsPanel />
      ) : (
        <EmptyState icon={MonitorSmartphone} title={t("users.sessions.pickUserHint")} className="py-6" />
      )}
    </Card>
  );
}

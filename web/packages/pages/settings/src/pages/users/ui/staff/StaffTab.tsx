import { useUnit } from "effector-react";
import { Ban, KeyRound, LockOpen, Pencil, RotateCcwKey, UserPlus, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDateTime } from "@shared/lib/date";
import { formatPhone } from "@shared/lib/phone";
import { $user } from "@shared/state/session";
import {
  Avatar,
  Button,
  DataTable,
  EmptyState,
  Icon,
  NoPermissionState,
  SearchInput,
  type DataTableColumn,
  type DataTableRowAction,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $selectedUserId,
  $staff,
  $staffCursor,
  $staffError,
  $staffLoaded,
  fetchStaffFx,
  staffActionsFor,
  staffDisplayStatus,
  staffName,
  staffLoadMore,
  staffReloadRequested,
  userSelected,
  type Staff,
} from "../../model/index.ts";
import { StaffActionDialog, type PendingStaffAction, type StaffActionKind } from "./StaffActionDialog.tsx";
import { EditStaffDialog } from "./StaffDialogs.tsx";
import { StaffSheet } from "./StaffSheet.tsx";
import { StaffStatusChip, useStaffLabels } from "./labels.tsx";

/** BO-11 «Xodimlar» tab: list (cursor), detail sheet, row actions. */
export function StaffTab({ onAdd }: { onAdd: () => void }) {
  const { t } = useTranslation("settings");
  const [staff, cursor, loaded, error, loading, me, selectedId, loadMore, reload, select] = useUnit([
    $staff,
    $staffCursor,
    $staffLoaded,
    $staffError,
    fetchStaffFx.pending,
    $user,
    $selectedUserId,
    staffLoadMore,
    staffReloadRequested,
    userSelected,
  ]);
  const labels = useStaffLabels();
  const online = useOnline();
  const [query, setQuery] = useState("");
  const [action, setAction] = useState<PendingStaffAction | null>(null);
  const [editing, setEditing] = useState<Staff | null>(null);

  const visible = useMemo(() => {
    const q = query.trim().toLocaleLowerCase();
    if (!q) return staff;
    return staff.filter(
      (s) => staffName(s).toLocaleLowerCase().includes(q) || s.phone.includes(q.replace(/\s/g, "")),
    );
  }, [staff, query]);

  // Search is client-side over the loaded rows: while a query is typed, the remaining cursor pages
  // are loaded one by one so the result covers the whole staff list (a store has tens of members).
  const searching = query.trim() !== "";
  useEffect(() => {
    if (searching && cursor !== null && !loading && !error) loadMore();
  }, [searching, cursor, loading, error, loadMore]);

  const counts = useMemo(() => {
    const by = { active: 0, blocked: 0, invited: 0 };
    for (const s of staff) {
      const status = staffDisplayStatus(s);
      by[status === "pending" ? "invited" : status] += 1;
    }
    return by;
  }, [staff]);

  if (error?.status === 403) return <NoPermissionState />;

  const onAction = (kind: StaffActionKind, row: Staff) => setAction({ kind, staff: row });

  const columns: DataTableColumn<Staff>[] = [
    {
      id: "person",
      header: t("users.table.person"),
      cell: (s) => (
        <div className="flex min-w-0 items-center gap-2.5">
          <Avatar name={staffName(s)} />
          <div className="min-w-0">
            <p className="truncate text-[14px] font-bold">
              {staffName(s)}
              {me?.id === s.user_id ? ` ${t("users.table.you")}` : ""}
            </p>
            <p className="text-[12px] tabular-nums text-muted-foreground">{formatPhone(s.phone)}</p>
          </div>
        </div>
      ),
    },
    {
      id: "roles",
      header: t("users.table.rolesBranches"),
      cell: (s) => (
        <div className="min-w-0">
          <p className="text-[14px] font-semibold">{labels.roles(s)}</p>
          <p className="text-[12px] text-muted-foreground">{labels.branches(s)}</p>
        </div>
      ),
    },
    {
      id: "status",
      header: t("users.table.status"),
      cell: (s) => <StaffStatusChip staff={s} />,
      width: "190px",
    },
    {
      id: "lastLogin",
      header: t("users.table.lastLogin"),
      cell: (s) => (s.last_login_at ? formatDateTime(s.last_login_at) : "—"),
      width: "150px",
    },
  ];

  const rowActions = (s: Staff): DataTableRowAction<Staff>[] => {
    if (!online) return [];
    const isSelf = me?.id === s.user_id;
    const allowed = staffActionsFor(s);
    const list: DataTableRowAction<Staff>[] = [
      { id: "edit", label: t("users.actions.edit"), icon: Pencil, onSelect: setEditing },
    ];
    if (allowed.resetCredentials) {
      list.push(
        {
          id: "pin",
          label: t("users.actions.resetPin"),
          icon: KeyRound,
          onSelect: (r) => onAction("resetPin", r),
        },
        {
          id: "password",
          label: t("users.actions.resetPassword"),
          icon: RotateCcwKey,
          onSelect: (r) => onAction("resetPassword", r),
        },
      );
    }
    if (allowed.unblock) {
      list.push({
        id: "unblock",
        label: t("users.actions.unblock"),
        icon: LockOpen,
        onSelect: (r) => onAction("unblock", r),
      });
    } else if (!isSelf) {
      list.push({
        id: "block",
        label: t("users.actions.block"),
        icon: Ban,
        destructive: true,
        onSelect: (r) => onAction("block", r),
      });
    }
    return list;
  };

  const onlyOwner = loaded && staff.length <= 1;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <SearchInput
          onSearch={setQuery}
          delay={0}
          placeholder={t("users.table.search")}
          aria-label={t("users.table.search")}
          className="w-full max-w-xs"
        />
        <p className="text-small text-foreground-secondary" aria-live="polite">
          {t(cursor !== null ? "users.table.countsPartial" : "users.table.counts", {
            total: staff.length,
            ...counts,
          })}
        </p>
      </div>
      <DataTable
        label={t("users.tabs.staff")}
        columns={columns}
        data={visible}
        getRowId={(s) => s.user_id}
        status={error ? "error" : loading && !loaded ? "loading" : "idle"}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={reload}
        onRowClick={(s) => select(s.user_id)}
        selectedRowId={selectedId}
        rowActions={rowActions}
        pagination={
          cursor !== null
            ? { kind: "cursor", hasMore: true, loadingMore: loading, onLoadMore: loadMore }
            : undefined
        }
        empty={<EmptyState icon={Users} title={t("users.table.noResults")} />}
      />
      {onlyOwner ? (
        <EmptyState
          icon={Users}
          title={t("users.empty.title")}
          description={t("users.empty.description")}
          action={
            <Button size="sm" onClick={onAdd} disabled={!online}>
              <Icon as={UserPlus} size="sm" />
              {t("users.add")}
            </Button>
          }
        />
      ) : null}
      <StaffSheet onAction={onAction} onEdit={setEditing} />
      <StaffActionDialog action={action} onClose={() => setAction(null)} />
      <EditStaffDialog staff={editing} onClose={() => setEditing(null)} />
    </div>
  );
}

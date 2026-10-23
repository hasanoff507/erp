import { useUnit } from "effector-react";
import { Ban, MonitorSmartphone, Plus, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { toApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { useCan } from "@shared/state/permissions";
import {
  Banner,
  Button,
  Checkbox,
  DataTable,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  EmptyState,
  FormField,
  Icon,
  NativeSelect,
  NoPermissionState,
  StatusChip,
  Textarea,
  buttonVariants,
  toast,
  type DataTableColumn,
} from "@shared/ui";

import { DeviceSyncCell } from "#/features/device-sync-health/index.ts";
import { errorText } from "#/shared/lib/errors.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $branches,
  $deviceFilters,
  $devices,
  $devicesError,
  $devicesLoaded,
  $devicesTotal,
  DEVICE_PAGE_SIZE,
  canRevokeDevice,
  deviceFiltersChanged,
  devicesPageChanged,
  devicesReloadRequested,
  devicesTabOpened,
  fetchDevicesFx,
  needsPendingConfirmation,
  revokeDeviceFx,
  type DeviceKind,
  type TenantDevice,
} from "../../model/index.ts";

const KINDS: readonly DeviceKind[] = ["web", "android", "onec_agent"];

/**
 * BO-11 «Qurilmalar» (qaror #56, 20 #29a/#29b): tenant devices with last sync and unsent events;
 * "Bekor qilish" (devices.revoke) asks for a reason and, when the device still has unsent events,
 * offers sync.drain first and requires the explicit «yo'qolishi mumkin» confirmation.
 */
export function DevicesTab() {
  const { t } = useTranslation("settings");
  const [
    devices,
    total,
    loaded,
    error,
    loading,
    filters,
    branches,
    opened,
    changeFilters,
    changePage,
    reload,
  ] = useUnit([
    $devices,
    $devicesTotal,
    $devicesLoaded,
    $devicesError,
    fetchDevicesFx.pending,
    $deviceFilters,
    $branches,
    devicesTabOpened,
    deviceFiltersChanged,
    devicesPageChanged,
    devicesReloadRequested,
  ]);
  const canRevoke = useCan({ permission: "devices.revoke" });
  const online = useOnline();
  const [revoking, setRevoking] = useState<TenantDevice | null>(null);

  useEffect(() => {
    opened();
  }, [opened]);

  if (error?.status === 403) return <NoPermissionState />;

  const branchName = (id: string | null) => branches.find((b) => b.id === id)?.name ?? "—";

  const columns: DataTableColumn<TenantDevice>[] = [
    {
      id: "device",
      header: t("devices.table.device"),
      cell: (d) => (
        <div className="min-w-0">
          <p className="text-[14px] font-bold">{d.cash_register_name ?? t(`devices.kind.${d.kind}`)}</p>
          <p className="text-[12px] text-muted-foreground">
            {[
              t(`devices.kind.${d.kind}`),
              d.app_version ? `v${d.app_version}` : null,
              branchName(d.branch_id),
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
      ),
    },
    {
      // --- Bosqich 3 settings: device-auth slice --- sync health (16 §3.1, §6)
      id: "sync",
      header: t("devices.table.lastSync"),
      cell: (d) => <DeviceSyncCell device={d} />,
      width: "210px",
    },
    {
      id: "pending",
      header: t("devices.table.pending"),
      numeric: true,
      width: "130px",
      cell: (d) =>
        needsPendingConfirmation(d) ? (
          <StatusChip tone="warning">
            {t("devices.pendingCount", { count: d.outbox_pending_count ?? 0 })}
          </StatusChip>
        ) : (
          (d.outbox_pending_count ?? 0).toString()
        ),
    },
    {
      id: "status",
      header: t("devices.table.status"),
      width: "140px",
      cell: (d) =>
        d.revoked_at ? (
          <StatusChip tone="destructive">{t("devices.status.revoked")}</StatusChip>
        ) : (
          <StatusChip tone="success" dot>
            {t("devices.status.active")}
          </StatusChip>
        ),
    },
    {
      id: "actions",
      header: t("devices.table.actions"),
      hideHeader: true,
      width: "150px",
      cell: (d) =>
        canRevoke && canRevokeDevice(d) ? (
          <Button variant="destructive-outline" size="sm" disabled={!online} onClick={() => setRevoking(d)}>
            <Icon as={Ban} size="sm" />
            {t("devices.revoke")}
          </Button>
        ) : d.kind === "onec_agent" && !d.revoked_at ? (
          <span className="text-[12px] text-muted-foreground">{t("devices.onecAgentHint")}</span>
        ) : null,
    },
  ];

  const branchOptions = [
    { value: "", label: t("devices.filters.allBranches") },
    ...branches.map((b) => ({ value: b.id, label: b.name })),
  ];
  const kindOptions = [
    { value: "", label: t("devices.filters.allKinds") },
    ...KINDS.map((k) => ({ value: k, label: t(`devices.kind.${k}`) })),
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <FormField label={t("devices.filters.branch")}>
          <NativeSelect
            options={branchOptions}
            value={filters.branchId ?? ""}
            onChange={(e) => changeFilters({ branchId: e.target.value || null })}
          />
        </FormField>
        <FormField label={t("devices.filters.kind")}>
          <NativeSelect
            options={kindOptions}
            value={filters.kind ?? ""}
            onChange={(e) => changeFilters({ kind: (e.target.value || null) as DeviceKind | null })}
          />
        </FormField>
        <label className="flex h-[42px] items-center gap-2 text-[14px] font-semibold">
          <Checkbox
            checked={filters.includeRevoked}
            onCheckedChange={(c) => changeFilters({ includeRevoked: c === true })}
          />
          {t("devices.filters.includeRevoked")}
        </label>
        <div className="grow" />
        <Link to="/install" className={buttonVariants({ variant: "secondary", size: "sm" })}>
          <Icon as={Plus} size="sm" />
          {t("devices.addNew")}
        </Link>
      </div>
      <DataTable
        label={t("users.tabs.devices")}
        columns={columns}
        data={devices}
        getRowId={(d) => d.id}
        status={error ? "error" : loading && !loaded ? "loading" : "idle"}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={reload}
        minWidth={760}
        pagination={
          total > DEVICE_PAGE_SIZE
            ? { kind: "page", page: filters.page, size: DEVICE_PAGE_SIZE, total, onPageChange: changePage }
            : undefined
        }
        empty={<EmptyState icon={MonitorSmartphone} title={t("devices.empty")} />}
      />
      {revoking ? <RevokeDeviceDialog device={revoking} onClose={() => setRevoking(null)} /> : null}
    </div>
  );
}

function RevokeDeviceDialog({ device, onClose }: { device: TenantDevice; onClose: () => void }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const revoke = useUnit(revokeDeviceFx);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [confirmLoss, setConfirmLoss] = useState(false);
  // The server may report unsent events the list did not show yet (VALIDATION_ERROR on confirm_pending_loss).
  const [pendingCount, setPendingCount] = useState<number | null>(
    needsPendingConfirmation(device) ? (device.outbox_pending_count ?? 0) : null,
  );
  const [error, setError] = useState<string | null>(null);
  const needsConfirm = pendingCount !== null;
  const name = device.cash_register_name ?? t(`devices.kind.${device.kind}`);

  const [busy, setBusy] = useState(false);

  const run = async () => {
    setError(null);
    if (reason.trim() === "") {
      setReasonError("validation.required");
      return;
    }
    setBusy(true);
    try {
      await revoke({ deviceId: device.id, reason, confirmPendingLoss: needsConfirm && confirmLoss });
      toast.success(t("devices.revoked", { name }));
      onClose();
    } catch (e) {
      const apiError = toApiError(e);
      const pendingDetail = apiError.details.some((d) => d.field.endsWith("confirm_pending_loss"));
      if (pendingDetail) {
        const count = apiError.params.outbox_pending_count;
        setPendingCount(typeof count === "number" ? count : 0);
        setConfirmLoss(false);
        setError(t("devices.pendingAppeared"));
      } else {
        setError(errorText(apiError));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => (open || busy ? undefined : onClose())}>
      <DialogContent size="sm" role="alertdialog">
        <DialogHeader>
          <DialogTitle>{t("devices.confirm.title")}</DialogTitle>
          <DialogDescription>{t("devices.confirm.description", { name })}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          {needsConfirm ? (
            <Banner tone="warning" icon={TriangleAlert} live="assertive">
              <p>{t("devices.pendingWarning", { count: pendingCount })}</p>
              <p className="mt-1 font-normal">{t("devices.syncDrainHint")}</p>
            </Banner>
          ) : null}
          <FormField label={t("devices.reason")} required error={reasonError}>
            {(a11y) => (
              <Textarea
                {...a11y}
                value={reason}
                maxLength={1000}
                rows={3}
                placeholder={t("devices.reasonPlaceholder")}
                onChange={(e) => {
                  setReason(e.target.value);
                  setReasonError(null);
                }}
              />
            )}
          </FormField>
          {needsConfirm ? (
            <label className="flex items-start gap-2.5 text-[14px] font-semibold">
              <Checkbox
                checked={confirmLoss}
                onCheckedChange={(c) => setConfirmLoss(c === true)}
                className="mt-0.5"
              />
              {t("devices.confirmPendingLoss")}
            </label>
          ) : null}
          {error ? (
            <Banner tone="destructive" icon={TriangleAlert} live="assertive">
              {error}
            </Banner>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="secondary" disabled={busy} onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button
            variant="destructive"
            disabled={busy || (needsConfirm && !confirmLoss)}
            onClick={() => void run()}
          >
            {t("devices.revokeConfirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

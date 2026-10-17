import { useUnit } from "effector-react";
import {
  CircleAlert,
  KeyRound,
  Monitor,
  PackageOpen,
  RefreshCw,
  Settings2,
  Smartphone,
  Store,
  UserRound,
  WifiOff,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { currentPlatform, isStandalone } from "@shared/lib/platform";
import { $isOnline } from "@shared/state/network";
import { $branches, $permissions, $session, $subscriptionRestriction } from "@shared/state/session";
import {
  Avatar,
  Banner,
  Button,
  EmptyState,
  FormField,
  Icon,
  Kbd,
  MoneyInput,
  NativeSelect,
  Skeleton,
  StatusChip,
  cn,
} from "@shared/ui";

import {
  $posCashier,
  $posDevice,
  $posDeviceForeign,
  $posLoaded,
  PinPad,
  cashierLocked,
  posSessionStarted,
} from "#/entities/pos-session/index.ts";
import { digitKeys, useHotkeys } from "#/shared/lib/use-hotkeys.ts";
import { cardRecoveryRequested } from "#/features/card-payment/index.ts";
import { CashierActions } from "#/features/cashier-session/index.ts";

import {
  $device,
  $openError,
  $openingCash,
  $pinError,
  $registerError,
  $registers,
  $selectedStaff,
  $shiftPlan,
  $staff,
  $step,
  adoptSessionDeviceFx,
  loginOpened,
  openShiftFx,
  openShiftPressed,
  openingCashChanged,
  pinSubmitted,
  registerBranchChanged,
  registerFx,
  registerSubmitted,
  staffBack,
  staffPicked,
  staffReloadRequested,
  verifyPinFx,
} from "../../model/index.ts";

export const POS_SALE_PATH = "/pos/sale";
export const POS_EQUIPMENT_PATH = "/pos/settings/devices";
export const POS_WAREHOUSE_PATH = "/pos/warehouse";
export const WAREHOUSE_MENU = [
  { key: "receive", to: "/pos/warehouse/receive" },
  { key: "transfer", to: "/pos/warehouse/transfer" },
  { key: "stocktake", to: "/pos/warehouse/stocktake" },
] as const;

/** POS-01 — Kassaga kirish / Smena ochish (07, route /pos/login; maket Pos01Kirish.dc.html). */
function PosLoginPage() {
  const { t } = useTranslation("pos");
  const navigate = useNavigate();
  const [loaded, posDevice, posCashier, session, restriction] = useUnit([
    $posLoaded,
    $posDevice,
    $posCashier,
    $session,
    $subscriptionRestriction,
  ]);
  const [step, device, online, foreign] = useUnit([$step, $device, $isOnline, $posDeviceForeign]);

  useEffect(() => {
    posSessionStarted();
  }, []);

  useEffect(() => {
    // SEC-07: another session's device — nothing of the cached POS data is read
    if (!loaded || foreign) return;
    if (!posDevice && session?.device?.id) {
      const branchName = session.branches.find((b) => b.id === session.device?.branch_id)?.name ?? null;
      void adoptSessionDeviceFx({ device: session.device, branchName });
      return;
    }
    loginOpened({ device: posDevice, cashier: posCashier });
    // re-run only when the POS session identity changes, not on every cashier field update
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, foreign, posDevice?.deviceId, posCashier?.userId]);

  const [params] = useSearchParams();
  const next = params.get("next");
  useEffect(() => {
    // `?next=` from the POS guard — only a POS path (no open redirect)
    const target = next?.startsWith("/pos/") && !next.startsWith("/pos/login") ? next : POS_SALE_PATH;
    if (step === "done") void navigate(target, { replace: true });
    // no `shift.open` (Omborchi) → the warehouse hub (contracts/pos-wh-routes.md)
    if (step === "warehouse") void navigate(POS_WAREHOUSE_PATH, { replace: true });
  }, [step, navigate, next]);

  const restricted =
    restriction !== null || session?.sub_status === "restricted" || session?.sub_status === "closed";

  return (
    <section
      data-testid="pos-login"
      className="mx-auto flex h-full min-h-0 w-full max-w-[1100px] flex-col gap-4 overflow-y-auto"
    >
      <header className="flex flex-wrap items-center gap-3 rounded-2xl border border-border bg-card px-5 py-4 shadow-raised">
        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-soft text-primary-strong">
          <Icon as={Store} size="lg" />
        </span>
        <div className="flex min-w-0 flex-col">
          <span className="text-[13px] font-semibold text-muted-foreground">{t("login.branchRegister")}</span>
          <span className="truncate text-[17px] font-extrabold" data-testid="pos-login-branch">
            {device
              ? [device.branchName, device.cashRegisterName].filter(Boolean).join(" · ") ||
                t("login.deviceBound")
              : t("login.notRegistered")}
          </span>
          {device ? (
            <span className="text-[12px] text-muted-foreground">{t("login.deviceBound")}</span>
          ) : null}
        </div>
        <div className="grow" />
        <StatusChip tone={online ? "success" : "warning"} dot icon={online ? undefined : WifiOff}>
          {online ? t("login.onlineCheck") : t("login.offlineCheck")}
        </StatusChip>
        <Button asChild variant="secondary" size="pos">
          <Link to={POS_EQUIPMENT_PATH}>
            <Icon as={Settings2} size="md" />
            {t("login.equipment")}
          </Link>
        </Button>
      </header>

      <IosNotice />

      {restricted ? (
        <Banner tone="destructive" icon={CircleAlert} live="assertive">
          <span className="flex flex-wrap items-center gap-3">
            {t("login.subscriptionRestricted")}
            <Button asChild variant="destructive" size="sm">
              <a href="/login?reason=subscription_expired">{t("login.exportData")}</a>
            </Button>
          </span>
        </Banner>
      ) : null}

      {foreign ? (
        <div
          className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-6 shadow-raised"
          data-testid="pos-foreign"
        >
          <Banner tone="destructive" icon={CircleAlert} live="assertive">
            {t("login.foreign")}
          </Banner>
          <CashierActions
            onLock={() => cashierLocked()}
            onCardBlocked={() => cardRecoveryRequested()}
            deviceId={posDevice?.deviceId ?? null}
          />
        </div>
      ) : (
        <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[1fr_1fr]">
          <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-6 shadow-raised">
            <StepTitle n={1} title={step === "register" ? t("login.register.title") : t("login.pinStep")} />
            {step === "loading" || !loaded ? <Skeleton className="h-64 w-full" /> : null}
            {step === "register" ? <RegisterDevice /> : null}
            {step === "await_staff" ? <AwaitStaff /> : null}
            {step === "staff" ? <StaffPicker disabled={restricted} /> : null}
            {step === "pin" ? <PinStep disabled={restricted} /> : null}
            {(step === "shift" || step === "busy" || step === "warehouse" || step === "done") &&
            posCashier ? (
              <SignedIn />
            ) : null}
          </div>
          <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-6 shadow-raised">
            <StepTitle n={2} title={t("login.shiftStep")} subtitle={t("login.afterPin")} />
            <ShiftStep />
          </div>
        </div>
      )}
    </section>
  );
}

function StepTitle({ n, title, subtitle }: { n: number; title: string; subtitle?: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-foreground text-[14px] font-extrabold text-background">
        {n}
      </span>
      <h2 className="text-[18px] font-extrabold">{title}</h2>
      {subtitle ? <span className="text-[13px] text-muted-foreground">{subtitle}</span> : null}
    </div>
  );
}

function IosNotice() {
  const { t } = useTranslation(["pos", "onboarding"]);
  if (currentPlatform() !== "ios") return null;
  return (
    <Banner tone={isStandalone() ? "info" : "warning"} icon={Smartphone}>
      <span className="flex flex-col gap-1" data-testid="pos-login-ios">
        <span className="font-bold">{t("onboarding:install.ios.title")}</span>
        {isStandalone() ? null : (
          <span>
            {t("onboarding:install.ios.steps.safari")} → {t("onboarding:install.ios.steps.share")} →{" "}
            {t("onboarding:install.ios.steps.add")}
          </span>
        )}
        <span>{t("onboarding:install.ios.posNote")}</span>
      </span>
    </Banner>
  );
}

function RegisterDevice() {
  const { t } = useTranslation("pos");
  const [permissions, branches, registers, error, pending] = useUnit([
    $permissions,
    $branches,
    $registers,
    $registerError,
    registerFx.pending,
  ]);
  const [branchId, setBranchId] = useState("");
  const [registerId, setRegisterId] = useState("");
  const canManage = permissions.includes("cash_register.manage");
  const branch = branchId || branches[0]?.id || "";

  useEffect(() => {
    if (canManage && branch) registerBranchChanged(branch);
  }, [canManage, branch]);

  if (!canManage) {
    return (
      <EmptyState
        icon={Monitor}
        title={t("login.register.needManager")}
        description={t("login.register.needManagerHint")}
      />
    );
  }
  const selected = registerId || registers[0]?.id || "";
  const errorKey = error?.details.some((d) => d.messageKey === "validation.device_bound_to_other_register")
    ? "login.register.boundToOther"
    : error
      ? "login.register.failed"
      : null;
  return (
    <form
      className="flex flex-col gap-4"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (selected) registerSubmitted(selected);
      }}
    >
      <p className="text-[14px] text-muted-foreground">{t("login.register.intro")}</p>
      <FormField label={t("login.register.branch")} required>
        <NativeSelect
          value={branch}
          onChange={(e) => {
            setBranchId(e.target.value);
            setRegisterId("");
          }}
          options={branches.map((b) => ({ value: b.id, label: b.name }))}
        />
      </FormField>
      <FormField label={t("login.register.cashRegister")} required>
        <NativeSelect
          value={selected}
          data-testid="register-select"
          onChange={(e) => setRegisterId(e.target.value)}
          options={registers.map((r) => ({ value: r.id, label: r.name }))}
        />
      </FormField>
      {registers.length === 0 ? (
        <Banner tone="warning" icon={CircleAlert}>
          {t("login.register.noRegisters")}
        </Banner>
      ) : null}
      {errorKey ? (
        <Banner tone="destructive" icon={CircleAlert} live="assertive">
          {t(errorKey)}
        </Banner>
      ) : null}
      <Button type="submit" size="pos-cta" disabled={!selected || pending} data-testid="register-submit">
        {t("login.register.submit")}
      </Button>
    </form>
  );
}

function AwaitStaff() {
  const { t } = useTranslation("pos");
  return (
    <EmptyState
      icon={RefreshCw}
      title={t("login.awaitStaff.title")}
      description={t("login.awaitStaff.description")}
      action={
        <Button variant="secondary" size="pos" onClick={() => staffReloadRequested()}>
          {t("login.awaitStaff.reload")}
        </Button>
      }
    />
  );
}

function StaffPicker({ disabled }: { disabled: boolean }) {
  const { t } = useTranslation("pos");
  const staff = useUnit($staff);
  useHotkeys(
    digitKeys((d) => {
      const row = staff["123456789".indexOf(d)];
      if (row && !disabled) staffPicked(row.user_id);
    }),
  );
  return (
    <div className="flex flex-col gap-3">
      <p className="text-[14px] text-muted-foreground">{t("login.pickStaff")}</p>
      <ul className="grid gap-2 sm:grid-cols-2" data-testid="staff-list">
        {staff.map((row, i) => (
          <li key={row.user_id}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => staffPicked(row.user_id)}
              className="flex h-16 w-full items-center gap-3 rounded-xl border border-border bg-card px-4 text-left hover:bg-accent disabled:opacity-60"
            >
              <Avatar name={row.full_name} size={36} />
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-[15px] font-bold">{row.full_name}</span>
                <span className="truncate text-[12px] text-muted-foreground">
                  {row.role_codes.map((c) => t(`login.roles.${c}`, { defaultValue: c })).join(", ")}
                </span>
              </span>
              {i < 9 ? <Kbd keys={String(i + 1)} className="ml-auto" /> : null}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PinStep({ disabled }: { disabled: boolean }) {
  const { t } = useTranslation("pos");
  const [user, error, busy] = useUnit([$selectedStaff, $pinError, verifyPinFx.pending]);
  const [pin, setPin] = useState("");
  const submit = () => {
    if (pin.length >= 4 && !busy && !disabled) {
      pinSubmitted(pin);
      setPin("");
    }
  };
  useHotkeys(
    [
      ...digitKeys((d) => setPin((p) => (p.length < 6 ? p + d : p))),
      { key: "Backspace", handler: () => setPin((p) => p.slice(0, -1)) },
      { key: "Enter", handler: submit },
      { key: "Escape", handler: () => (pin ? setPin("") : staffBack()) },
    ],
    !disabled,
  );
  const errorText = error
    ? error.reason === "invalid"
      ? error.attemptsLeft !== null
        ? t("login.pinErrors.invalidLeft", { left: error.attemptsLeft })
        : t("login.pinErrors.invalid")
      : error.reason === "locked"
        ? t("login.pinErrors.locked", {
            minutes:
              error.retryAfterS !== null
                ? Math.max(1, Math.ceil(error.retryAfterS / 60))
                : lockMinutes(error.lockedUntil),
          })
        : t(`login.pinErrors.${error.reason}`)
    : null;
  return (
    <div className="flex flex-col items-center gap-4">
      <div className="flex w-full items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => staffBack()}>
          {t("login.changeUser")}
        </Button>
        <span className="flex items-center gap-2 text-[15px] font-bold" data-testid="pin-user">
          <Icon as={UserRound} size="md" />
          {user?.full_name}
        </span>
      </div>
      <span className="text-[13px] font-semibold text-muted-foreground">
        {t("login.pinLabel")} · {t("login.pinHint", { n: pin.length })}
      </span>
      <PinPad
        value={pin}
        onChange={setPin}
        disabled={disabled || busy}
        label={t("login.pinLabel")}
        backspaceLabel={t("login.backspace")}
      />
      {errorText ? (
        <Banner tone="destructive" icon={CircleAlert} live="assertive" className="w-full">
          <span data-testid="pin-error">{errorText}</span>
        </Banner>
      ) : null}
      <Button
        size="pos-cta"
        className="w-full"
        disabled={pin.length < 4 || busy || disabled}
        onClick={submit}
        data-testid="pin-submit"
      >
        <Icon as={KeyRound} size="md" />
        {t("login.signIn")}
        <Kbd keys="Enter" inverted />
      </Button>
      <div className="flex w-full items-center justify-between text-[13px]">
        <Link to="/recover" className="font-semibold text-primary hover:underline">
          {t("login.forgot")}
        </Link>
        <span className="flex items-center gap-1 text-muted-foreground">
          <Kbd keys="Esc" /> {t("login.clear")}
        </span>
      </div>
    </div>
  );
}

function lockMinutes(until: string | null): number {
  if (!until) return 1;
  const ms = new Date(until).getTime() - Date.now();
  return Math.max(1, Math.ceil(ms / 60_000));
}

function SignedIn() {
  const { t } = useTranslation("pos");
  const [cashier, device] = useUnit([$posCashier, $posDevice]);
  if (!cashier) return null;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3 rounded-xl border border-success-border bg-success-soft px-4 py-3">
        <Avatar name={cashier.fullName} size={36} />
        <div className="flex flex-col">
          <span className="text-[15px] font-extrabold" data-testid="signed-in-cashier">
            {cashier.fullName}
          </span>
          <span className="text-[12px] text-success-strong">
            {cashier.via === "online" ? t("login.verifiedOnline") : t("login.verifiedLocal")}
          </span>
        </div>
      </div>
      <CashierActions
        onLock={() => cashierLocked()}
        onCardBlocked={() => cardRecoveryRequested()}
        deviceId={device?.deviceId ?? null}
      />
    </div>
  );
}

function ShiftStep() {
  const { t } = useTranslation("pos");
  const navigate = useNavigate();
  const [step, plan, cash, error, pending, online] = useUnit([
    $step,
    $shiftPlan,
    $openingCash,
    $openError,
    openShiftFx.pending,
    $isOnline,
  ]);
  useHotkeys([{ key: "Enter", allowInInput: true, handler: () => openShiftPressed() }], step === "shift");

  if (step === "busy") {
    return (
      <Banner tone="destructive" icon={CircleAlert} live="assertive">
        {t("login.shiftBusy")}
      </Banner>
    );
  }
  if (step === "warehouse") {
    return (
      <div className="flex flex-col gap-3" data-testid="warehouse-menu">
        <p className="text-[14px] text-muted-foreground">{t("login.warehouse.hint")}</p>
        {WAREHOUSE_MENU.map((item) => (
          <Button key={item.key} variant="secondary" size="pos" onClick={() => void navigate(item.to)}>
            <Icon as={PackageOpen} size="md" />
            {t(`login.warehouse.${item.key}`)}
          </Button>
        ))}
      </div>
    );
  }
  if (step !== "shift" || plan?.kind !== "open") {
    return <p className="text-[14px] text-muted-foreground">{t("login.shiftAfterPin")}</p>;
  }
  return (
    <form
      className="flex flex-col gap-4"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        openShiftPressed();
      }}
    >
      <p className="text-[14px] text-muted-foreground">{t("login.shiftIntro", { number: plan.shiftNo })}</p>
      <FormField label={t("login.openingCash")} required hint={t("login.openingCashHint")}>
        <MoneyInput
          value={cash}
          onChange={(v) => openingCashChanged(v)}
          className="h-14 text-[22px] font-extrabold"
          data-testid="opening-cash"
        />
      </FormField>
      {!online ? (
        <Banner tone="warning" icon={WifiOff}>
          {t("login.offlineShift")}
        </Banner>
      ) : null}
      {error ? (
        <Banner tone="destructive" icon={CircleAlert} live="assertive">
          {t("login.openFailed")}
        </Banner>
      ) : null}
      <Button
        type="submit"
        size="pos-cta"
        disabled={pending}
        className={cn("w-full")}
        data-testid="open-shift"
      >
        {t("login.openShift")}
        <Kbd keys="Enter" inverted />
      </Button>
    </form>
  );
}

export const PosLogin = { route: "login", titleKey: "pos:login.title", Page: PosLoginPage } as const;

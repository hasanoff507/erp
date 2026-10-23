/**
 * BO-12 «Karta terminallari» (07 BO-12; 18 §16a.5; qaror #71): terminals of the selected branch, bind /
 * edit / disable / archive (`cash_register.manage`). Fields are device data only (TID, MID, LAN address, agent
 * device) — the form has no card field of any kind. Disabling/archiving a terminal with an unresolved
 * attempt → `CARD_OUTCOME_UNKNOWN` (server).
 */
import { useUnit } from "effector-react";
import { Archive, CreditCard, Pencil, Plus, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { useTranslation } from "@shared/i18n";
import {
  Banner,
  Button,
  Card,
  ConfirmDialog,
  DataTable,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  EmptyState,
  Icon,
  Input,
  NativeSelect,
  StatusChip,
  Switch,
  toast,
  type DataTableColumn,
  type DataTableRowAction,
} from "@shared/ui";
import { Controller, RhfField, useZodForm, z } from "@shared/ui/form";

import { errorText } from "#/shared/lib/errors.ts";
import { applyServerErrors } from "#/shared/lib/form.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $cardTerminals,
  $cardTerminalsError,
  ADAPTERS,
  cardTerminalsOpened,
  cardTerminalsReloadRequested,
  createCardTerminalFx,
  fetchCardTerminalsFx,
  isPrivateIpv4,
  updateCardTerminalFx,
  type CardTerminal,
} from "../model/index.ts";
import { HealthChip, dyn } from "./parts.tsx";

export interface RegisterOption {
  id: string;
  name: string;
}

export function CardTerminalsCard({
  branchId,
  registers,
  canManage,
}: {
  branchId: string;
  registers: readonly RegisterOption[];
  canManage: boolean;
}) {
  const { t: tt } = useTranslation("settings");
  const t = dyn(tt);
  const [terminals, error, loading, open, reload] = useUnit([
    $cardTerminals,
    $cardTerminalsError,
    fetchCardTerminalsFx.pending,
    cardTerminalsOpened,
    cardTerminalsReloadRequested,
  ]);
  const online = useOnline();
  const [editing, setEditing] = useState<CardTerminal | "new" | null>(null);
  const [archiving, setArchiving] = useState<CardTerminal | null>(null);

  useEffect(() => {
    open(branchId);
  }, [open, branchId]);

  const registerName = (id: string | null | undefined) => registers.find((r) => r.id === id)?.name ?? "—";

  const columns: DataTableColumn<CardTerminal>[] = [
    {
      id: "name",
      header: t("cardTerminals.fields.name"),
      cell: (term) => (
        <div className="min-w-0">
          <p className="text-[14px] font-bold">
            {term.name}
            {term.is_default ? (
              <span className="ml-2 text-[12px] font-semibold text-muted-foreground">
                {t("cardTerminals.default")}
              </span>
            ) : null}
          </p>
          <p className="text-[12px] text-muted-foreground">
            {t(`cardTerminals.adapter.${term.adapter}`)} · {term.vendor}
            {term.model ? ` ${term.model}` : ""}
          </p>
        </div>
      ),
    },
    {
      id: "register",
      header: t("cardTerminals.fields.register"),
      cell: (term) => registerName(term.cash_register_id),
    },
    {
      id: "tid",
      header: t("cardTerminals.fields.tid"),
      cell: (term) => (
        <span className="text-[13px] tabular-nums">
          {term.tid ?? "—"}
          {term.host ? <span className="block text-[12px] text-muted-foreground">{term.host}</span> : null}
        </span>
      ),
    },
    {
      id: "health",
      header: t("cardTerminals.fields.health"),
      cell: (term) => <HealthChip terminal={term} />,
    },
    {
      id: "status",
      header: t("cardTerminals.fields.status"),
      cell: (term) => (
        <StatusChip tone={term.status === "active" ? "success" : "neutral"} dot>
          {t(`cardTerminals.status.${term.status}`)}
        </StatusChip>
      ),
    },
  ];

  const rowActions = (term: CardTerminal): DataTableRowAction<CardTerminal>[] =>
    canManage && online && term.status !== "archived"
      ? [
          { id: "edit", label: t("cardTerminals.edit"), icon: Pencil, onSelect: setEditing },
          {
            id: "archive",
            label: t("cardTerminals.archive"),
            icon: Archive,
            destructive: true,
            onSelect: setArchiving,
          },
        ]
      : [];

  return (
    <Card className="flex flex-col gap-3" data-testid="card-terminals">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="flex items-center gap-2 text-[15px] font-bold">
          <Icon as={CreditCard} size="sm" />
          {t("cardTerminals.title")}
        </h2>
        <div className="grow" />
        {canManage ? (
          <Button
            size="sm"
            variant="secondary"
            disabled={!online || registers.length === 0}
            onClick={() => setEditing("new")}
          >
            <Icon as={Plus} size="sm" />
            {t("cardTerminals.add")}
          </Button>
        ) : null}
      </div>
      <p className="text-[12px] text-muted-foreground">{t("cardTerminals.description")}</p>
      <DataTable
        label={t("cardTerminals.title")}
        columns={columns}
        data={terminals}
        getRowId={(term) => term.id}
        status={error ? "error" : loading && terminals.length === 0 ? "loading" : "idle"}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={reload}
        rowActions={rowActions}
        minWidth={760}
        skeletonRows={1}
        empty={<EmptyState icon={CreditCard} title={t("cardTerminals.empty")} />}
      />
      {editing ? (
        <TerminalDialog
          branchId={branchId}
          registers={registers}
          terminal={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      ) : null}
      {archiving ? (
        <ArchiveDialog
          terminal={archiving}
          registerName={registerName(archiving.cash_register_id)}
          onClose={() => setArchiving(null)}
        />
      ) : null}
    </Card>
  );
}

const schema = z
  .object({
    cash_register_id: z.string().min(1),
    name: z.string().trim().min(2).max(100),
    vendor: z.string().regex(/^[a-z0-9_]{2,32}$/),
    model: z.string().max(100),
    adapter: z.enum(ADAPTERS),
    driver: z.string().regex(/^[a-z0-9_]{2,40}$/),
    agent_id: z.string(),
    local_id: z.string().max(100),
    host: z.string().max(15),
    port: z.string().regex(/^(|[0-9]{1,5})$/),
    vendor_terminal_ref: z.string().max(64),
    tid: z.string().regex(/^(|[0-9A-Za-z]{1,16})$/),
    mid: z.string().regex(/^(|[0-9A-Za-z]{1,20})$/),
    is_default: z.boolean(),
  })
  .superRefine((v, ctx) => {
    if (v.adapter === "agent_ecr") {
      for (const key of ["agent_id", "local_id", "host"] as const) {
        if (!v[key]) ctx.addIssue({ code: "custom", path: [key], message: "validation.required" });
      }
    }
    if (v.host && !isPrivateIpv4(v.host)) {
      ctx.addIssue({ code: "custom", path: ["host"], message: "validation.private_ipv4_required" });
    }
    if (v.adapter === "cloud" && !v.vendor_terminal_ref) {
      ctx.addIssue({ code: "custom", path: ["vendor_terminal_ref"], message: "validation.required" });
    }
    if (v.adapter !== "fake" && !v.tid)
      ctx.addIssue({ code: "custom", path: ["tid"], message: "validation.required" });
  });
type FormValues = z.infer<typeof schema>;

const orNull = (v: string): string | null => (v.trim() === "" ? null : v.trim());
/** "8080" → 8080 (a TCP port, not money — digits only, validated by the schema). */
const portNumber = (digits: string): number =>
  [...digits].reduce((n, d) => n * 10 + "0123456789".indexOf(d), 0);

function TerminalDialog({
  branchId,
  registers,
  terminal,
  onClose,
}: {
  branchId: string;
  registers: readonly RegisterOption[];
  terminal: CardTerminal | null;
  onClose: () => void;
}) {
  const { t: tt } = useTranslation("settings");
  const t = dyn(tt);
  const { t: tc } = useTranslation("common");
  const [create, update] = useUnit([createCardTerminalFx, updateCardTerminalFx]);
  const online = useOnline();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useZodForm(schema, {
    defaultValues: {
      cash_register_id: terminal?.cash_register_id ?? registers[0]?.id ?? "",
      name: terminal?.name ?? "",
      vendor: terminal?.vendor ?? "",
      model: terminal?.model ?? "",
      adapter: terminal?.adapter ?? "agent_ecr",
      driver: terminal?.driver ?? "",
      agent_id: terminal?.agent_id ?? "",
      local_id: terminal?.local_id ?? "",
      host: terminal?.host ?? "",
      port: terminal?.port != null ? String(terminal.port) : "",
      vendor_terminal_ref: terminal?.vendor_terminal_ref ?? "",
      tid: terminal?.tid ?? "",
      mid: terminal?.mid ?? "",
      is_default: terminal?.is_default ?? true,
    },
  });
  const adapter = form.watch("adapter");

  const submit = form.handleSubmit(async (v: FormValues) => {
    setFormError(null);
    const device = {
      cash_register_id: v.cash_register_id,
      name: v.name.trim(),
      model: orNull(v.model),
      agent_id: v.adapter === "agent_ecr" ? orNull(v.agent_id) : null,
      local_id: v.adapter === "agent_ecr" ? orNull(v.local_id) : null,
      host: orNull(v.host),
      port: v.port ? portNumber(v.port) : null,
      vendor_terminal_ref: orNull(v.vendor_terminal_ref),
      tid: orNull(v.tid),
      mid: orNull(v.mid),
      is_default: v.is_default,
    };
    try {
      if (terminal) {
        await update({ id: terminal.id, body: { ...device, version: terminal.version } });
        toast.success(t("cardTerminals.saved"));
      } else {
        await create({
          ...device,
          branch_id: branchId,
          vendor: v.vendor,
          adapter: v.adapter,
          driver: v.driver,
        });
        toast.success(t("cardTerminals.created"));
      }
      onClose();
    } catch (error) {
      setFormError(applyServerErrors(form, error));
    }
  });

  const text = (name: keyof FormValues, label: string, props: Record<string, unknown> = {}) => (
    <RhfField
      control={form.control}
      name={name}
      label={label}
      render={({ field, control }) => (
        <Input {...control} {...field} value={String(field.value ?? "")} autoComplete="off" {...props} />
      )}
    />
  );

  return (
    <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent size="md">
        <DialogHeader>
          <DialogTitle>
            {terminal ? t("cardTerminals.editTitle") : t("cardTerminals.dialogTitle")}
          </DialogTitle>
          <DialogDescription>{t("cardTerminals.noCardData")}</DialogDescription>
        </DialogHeader>
        <form
          id="card-terminal-form"
          noValidate
          onSubmit={(e) => void submit(e)}
          className="grid gap-3 sm:grid-cols-2"
        >
          <Controller
            control={form.control}
            name="cash_register_id"
            render={({ field }) => (
              <label className="flex flex-col gap-1 text-[13px] font-semibold">
                {t("cardTerminals.fields.register")}
                <NativeSelect
                  value={field.value}
                  onChange={(e) => field.onChange(e.target.value)}
                  options={registers.map((r) => ({ value: r.id, label: r.name }))}
                />
              </label>
            )}
          />
          {text("name", t("cardTerminals.fields.name"), { maxLength: 100 })}
          <Controller
            control={form.control}
            name="adapter"
            render={({ field }) => (
              <label className="flex flex-col gap-1 text-[13px] font-semibold">
                {t("cardTerminals.fields.adapter")}
                <NativeSelect
                  value={field.value}
                  disabled={terminal !== null}
                  onChange={(e) => field.onChange(e.target.value)}
                  options={ADAPTERS.map((a) => ({ value: a, label: t(`cardTerminals.adapter.${a}`) }))}
                />
              </label>
            )}
          />
          {text("vendor", t("cardTerminals.fields.vendor"), { maxLength: 32, disabled: terminal !== null })}
          {text("driver", t("cardTerminals.fields.driver"), { maxLength: 40, disabled: terminal !== null })}
          {text("model", t("cardTerminals.fields.model"), { maxLength: 100 })}
          {adapter === "agent_ecr" ? (
            <>
              {text("agent_id", t("cardTerminals.fields.agentId"))}
              {text("local_id", t("cardTerminals.fields.localId"), { maxLength: 100 })}
            </>
          ) : null}
          {adapter === "agent_ecr" || adapter === "cloud" ? (
            <>
              {text("host", t("cardTerminals.fields.host"), {
                maxLength: 15,
                inputMode: "decimal",
                placeholder: "192.168.1.40",
              })}
              {text("port", t("cardTerminals.fields.port"), { maxLength: 5, inputMode: "numeric" })}
            </>
          ) : null}
          {adapter === "cloud"
            ? text("vendor_terminal_ref", t("cardTerminals.fields.vendorTerminalRef"), { maxLength: 64 })
            : null}
          {text("tid", t("cardTerminals.fields.tid"), { maxLength: 16 })}
          {text("mid", t("cardTerminals.fields.mid"), { maxLength: 20 })}
          <Controller
            control={form.control}
            name="is_default"
            render={({ field }) => (
              <label className="flex items-center gap-2 text-[13px] font-semibold sm:col-span-2">
                <Switch checked={field.value} onCheckedChange={field.onChange} />
                {t("cardTerminals.fields.isDefault")}
              </label>
            )}
          />
          <p className="text-[12px] text-muted-foreground sm:col-span-2">
            {adapter === "fake" ? t("cardTerminals.fakeHint") : t("cardTerminals.hostHint")}
          </p>
          {formError ? (
            <Banner tone="destructive" icon={TriangleAlert} live="assertive" className="sm:col-span-2">
              {formError}
            </Banner>
          ) : null}
        </form>
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button type="submit" form="card-terminal-form" disabled={!online || form.formState.isSubmitting}>
            {tc("actions.save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ArchiveDialog({
  terminal,
  registerName,
  onClose,
}: {
  terminal: CardTerminal;
  registerName: string;
  onClose: () => void;
}) {
  const { t: tt } = useTranslation("settings");
  const t = dyn(tt);
  const update = useUnit(updateCardTerminalFx);
  const [error, setError] = useState<string | null>(null);
  return (
    <ConfirmDialog
      open
      onOpenChange={(o) => (o ? undefined : onClose())}
      title={t("cardTerminals.archiveTitle")}
      description={t("cardTerminals.archiveHint", { name: registerName })}
      confirmLabel={t("cardTerminals.archive")}
      tone="destructive"
      error={error}
      onConfirm={async () => {
        setError(null);
        try {
          await update({ id: terminal.id, body: { status: "archived", version: terminal.version } });
          toast.success(t("cardTerminals.archived"));
        } catch (e) {
          setError(errorText(e));
          throw e;
        }
      }}
    />
  );
}

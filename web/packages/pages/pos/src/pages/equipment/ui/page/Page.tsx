/**
 * POS-16 — Uskunalar sozlamasi (07 POS-16, maket Pos16Uskunalar.dc.html; route /pos/settings/devices).
 * Sections: Chek printeri (transport radio, LAN address, paper, codepage, render mode, «Printerni aniqlash»,
 * «Sinov chek»), Skaner sinovi, Tarozi shtrix-kodi (read-only), Do'kon agenti (status, pairing code), Karta
 * terminali (`TerminalPairingSection` of features/card-payment), Katalog ko'rinishi. Device-local — no
 * permission needed (07); «Saqlash» Enter, Esc back.
 */
import { useUnit } from "effector-react";
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  CreditCard,
  LayoutGrid,
  Printer,
  ScanLine,
  Scale,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import type { PrinterRenderMode, PrinterTransport } from "@shared/lib/printer";
import { $agentStatus } from "@shared/state/device";
import {
  Banner,
  Button,
  Card,
  Icon,
  Input,
  Kbd,
  Label,
  NativeSelect,
  RadioCard,
  RadioGroup,
  SegmentedControl,
  StatusChip,
  type LucideIcon,
} from "@shared/ui";

import { TerminalPairingSection } from "#/features/card-payment/index.ts";
import { $posDevice, usePosPermission } from "#/entities/pos-session/index.ts";
import { WhScreen, trimQty } from "#/features/wh-scan/index.ts";
import { tashkentTime } from "#/shared/lib/dates.ts";
import { dyn } from "#/shared/lib/i18n-errors.ts";
import { useBarcodeWedge } from "#/shared/lib/use-barcode-wedge.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";

import {
  $autoDetected,
  $available,
  $busy,
  $catalogView,
  $detectError,
  $form,
  $formErrors,
  $justSaved,
  $lastTest,
  $pairState,
  $templates,
  LAN_TRANSPORTS,
  TRANSPORT_ORDER,
  agentCheckRequested,
  catalogViewChanged,
  describeScan,
  detectRequested,
  equipmentOpened,
  lanAddressChanged,
  pairRequested,
  paperWidthChanged,
  renderModeChanged,
  saveRequested,
  scaleRows,
  testRequested,
  transportChanged,
  transportEnabled,
  type ScanTestResult,
} from "../../model/index.ts";

const BO_SETTINGS = "/app/settings/tenant";

function Section({ icon, title, status, children, testId }: {
  icon: LucideIcon; title: string; status?: ReactNode; children: ReactNode; testId?: string;
}) {
  return (
    <Card className="flex flex-col gap-3 p-4" data-testid={testId}>
      <header className="flex items-center gap-2">
        <Icon as={icon} size="md" className="text-muted-foreground" />
        <h2 className="flex-1 text-[16px] font-extrabold">{title}</h2>
        {status}
      </header>
      {children}
    </Card>
  );
} // prettier-ignore

function EquipmentPage() {
  const { t } = useTranslation("pos");
  const navigate = useNavigate();
  const [busy, justSaved, formErrors] = useUnit([$busy, $justSaved, $formErrors]);

  useEffect(() => {
    equipmentOpened();
  }, []);

  useHotkeys([
    { key: "Enter", handler: () => saveRequested() },
    { key: "Escape", allowInInput: true, handler: () => navigate(-1) },
  ]);

  return (
    <WhScreen
      title={t("equipment.title")}
      subtitle={t("equipment.subtitle")}
      onBack={() => navigate(-1)}
      testId="pos-equipment"
      actions={
        <Button
          size="pos"
          onClick={() => saveRequested()}
          disabled={busy.saving || formErrors.length > 0}
          data-testid="equipment-save"
        >
          {t("equipment.save")}
          <Kbd keys="Enter" inverted />
        </Button>
      }
    >
      {justSaved ? (
        <Banner tone="success" icon={CheckCircle2} className="mb-3">
          {t("equipment.saved")}
        </Banner>
      ) : null}
      <div className="grid gap-4 xl:grid-cols-2">
        <PrinterSection />
        <div className="flex flex-col gap-4">
          <ScannerSection />
          <ScaleSection />
          <AgentSection />
          <CardSection />
          <CatalogViewSection />
        </div>
      </div>
    </WhScreen>
  );
}

function PrinterSection() {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const [form, available, auto, busy, lastTest, detectError, formErrors] = useUnit([
    $form, $available, $autoDetected, $busy, $lastTest, $detectError, $formErrors,
  ]); // prettier-ignore
  const lanPort = form.transport ? LAN_TRANSPORTS[form.transport] : undefined;
  const ios = available.length === 1 && available[0] === "cloud";
  const status = lastTest ? (
    <StatusChip tone={lastTest.ok ? "success" : "destructive"} dot>
      {t("equipment.printer.lastTest", { time: tashkentTime(lastTest.at) })}
    </StatusChip>
  ) : form.transport ? null : (
    <StatusChip tone="neutral">{t("equipment.printer.notConfigured")}</StatusChip>
  );
  return (
    <Section icon={Printer} title={t("equipment.printer.title")} status={status} testId="equipment-printer">
      {ios ? (
        <Banner tone="info" icon={Printer}>
          {t("equipment.printer.iosNote")}
        </Banner>
      ) : null}
      <div>
        <Label>{t("equipment.printer.transport")}</Label>
        <RadioGroup
          value={form.transport ?? ""}
          onValueChange={(v) => transportChanged(v as PrinterTransport)}
          className="mt-1 grid gap-2 sm:grid-cols-2"
          aria-label={t("equipment.printer.transport")}
        >
          {TRANSPORT_ORDER.map((tr) => {
            const enabled = transportEnabled(tr, available);
            return (
              <RadioCard
                key={tr}
                value={tr}
                disabled={!enabled}
                data-testid={`transport-${tr}`}
                title={t(`equipment.printer.transports.${tr}`)}
                description={
                  enabled ? t(`equipment.printer.transportNotes.${tr}`) : t("equipment.printer.unavailable")
                }
              />
            );
          })}
        </RadioGroup>
        <p className="mt-1 text-[12px] text-muted-foreground">
          {auto
            ? t("equipment.printer.auto", { transport: t(`equipment.printer.transports.${auto}`) })
            : form.transport
              ? null
              : t("equipment.printer.autoNone")}
        </p>
      </div>
      {lanPort !== undefined ? (
        <div>
          <Label htmlFor="printer-lan">{t("equipment.printer.lanAddress")}</Label>
          <Input
            id="printer-lan"
            value={form.lanAddress ?? ""}
            maxLength={32}
            placeholder={lanPort === 9100 ? t("equipment.printer.lanPlaceholder") : "192.168.1.50"}
            onChange={(e) => lanAddressChanged(e.target.value)}
            className="h-12 font-mono"
          />
          {formErrors.includes("lan_address_invalid") ? (
            <p className="mt-1 text-[12px] text-destructive-strong">{t("equipment.printer.lanInvalid")}</p>
          ) : null}
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <Label>{t("equipment.printer.paperWidth")}</Label>
          <SegmentedControl
            label={t("equipment.printer.paperWidth")}
            density="touch"
            value={String(form.paperWidth) as "58" | "80"}
            onChange={(v) => paperWidthChanged(v === "80" ? 80 : 58)}
            options={[
              { value: "58", label: t("equipment.printer.paper58") },
              { value: "80", label: t("equipment.printer.paper80") },
            ]}
          />
        </div>
        <div>
          <Label htmlFor="printer-codepage">{t("equipment.printer.codepage")}</Label>
          <NativeSelect
            id="printer-codepage"
            value="cp866"
            onChange={() => undefined}
            options={[{ value: "cp866", label: t("equipment.printer.codepageCp866") }]}
            wrapperClassName="w-full"
            className="h-12"
          />
        </div>
        <div>
          <Label htmlFor="printer-render">{t("equipment.printer.renderMode")}</Label>
          <NativeSelect
            id="printer-render"
            value={form.renderMode}
            onChange={(e) => renderModeChanged(e.target.value as PrinterRenderMode)}
            options={[
              { value: "auto", label: t("equipment.printer.renderAutoNote") },
              { value: "text", label: t("equipment.printer.renderModes.text") },
              { value: "raster", label: t("equipment.printer.renderModes.raster") },
            ]}
            wrapperClassName="w-full"
            className="h-12"
          />
        </div>
      </div>
      <p className="rounded-lg bg-accent p-3 text-[12px] text-foreground-secondary">
        {t("equipment.printer.hint")}
      </p>
      {detectError && detectError !== "cancelled" ? (
        <Banner tone="warning" icon={AlertTriangle}>
          {t(`equipment.printer.errors.${detectError}`)}
        </Banner>
      ) : null}
      {lastTest ? (
        <Banner
          tone={lastTest.ok ? "success" : "destructive"}
          icon={lastTest.ok ? CheckCircle2 : AlertTriangle}
        >
          <span data-testid="printer-test-result">
            {lastTest.ok
              ? t("equipment.printer.testOk", {
                  mode: t(`equipment.printer.testModes.${lastTest.mode ?? "text"}`),
                })
              : t(`equipment.printer.errors.${lastTest.code ?? "write_failed"}`)}
          </span>
        </Banner>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button
          size="pos"
          variant="secondary"
          disabled={busy.detecting}
          onClick={() => detectRequested()}
          data-testid="printer-detect"
        >
          {busy.detecting ? t("equipment.printer.detecting") : t("equipment.printer.detect")}
        </Button>
        <Button
          size="pos"
          disabled={busy.testing || formErrors.length > 0}
          onClick={() => testRequested()}
          data-testid="printer-test"
        >
          {t("equipment.printer.test")}
        </Button>
      </div>
    </Section>
  );
}

function ScannerSection() {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const templates = useUnit($templates);
  const [last, setLast] = useState<ScanTestResult | null>(null);
  const [previous, setPrevious] = useState<ScanTestResult | null>(null);
  const [value, setValue] = useState("");
  const ref = useRef<HTMLInputElement | null>(null);
  const accept = (code: string) => {
    if (!code.trim()) return;
    setPrevious(last);
    setLast(describeScan(code, templates));
    setValue("");
  };
  useBarcodeWedge(accept);
  const kindLabel = (r: ScanTestResult) => t(`equipment.scanner.kinds.${r.kind}`);
  return (
    <Section
      icon={ScanLine}
      title={t("equipment.scanner.title")}
      status={
        <StatusChip tone="success" dot>
          {t("equipment.scanner.listening")}
        </StatusChip>
      }
      testId="equipment-scanner"
    >
      <Input
        ref={ref}
        aria-label={t("equipment.scanner.title")}
        placeholder={t("equipment.scanner.placeholder")}
        value={value}
        maxLength={256}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
            accept(value);
          }
        }}
        className="h-12 font-mono"
      />
      {last ? (
        <div className="text-[14px]" data-testid="scanner-result">
          <p className="font-bold">
            {t("equipment.scanner.result", { kind: kindLabel(last), code: last.code })}
          </p>
          {last.weight ? (
            <p className="text-muted-foreground">
              PLU {last.weight.productCode} ·{" "}
              {last.weight.valueKind === "WEIGHT"
                ? `${trimQty(last.weight.value)} kg`
                : `${formatMoney(last.weight.value)}`}
            </p>
          ) : null}
        </div>
      ) : null}
      {previous ? (
        <p className="text-[12px] text-muted-foreground">
          {t("equipment.scanner.previous", { kind: kindLabel(previous) })}
        </p>
      ) : null}
    </Section>
  );
}

function ScaleSection() {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const templates = useUnit($templates);
  const canManage = usePosPermission("catalog.manage");
  const rows = scaleRows(templates);
  return (
    <Section
      icon={Scale}
      title={t("equipment.scale.title")}
      status={
        <span className="font-mono text-[12px] text-muted-foreground">{t("equipment.scale.format")}</span>
      }
      testId="equipment-scale"
    >
      <ul className="flex flex-col gap-2">
        {rows.map((r) => (
          <li key={r.prefixes.join(",")} className="rounded-lg border border-border p-3 text-[14px]">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-primary-soft px-2 py-0.5 font-mono font-bold text-primary-strong">
                {r.prefixes.join(", ")}
              </span>
              <span className="font-semibold">{t(`equipment.scale.kinds.${r.kind}`)}</span>
              {!r.enabled ? <StatusChip tone="neutral">{t("equipment.scale.disabled")}</StatusChip> : null}
            </div>
            <p className="text-[12px] text-muted-foreground">
              {t("equipment.scale.row", { plu: r.itemLen, value: r.valueLen })} · {r.example} →{" "}
              {r.kind === "WEIGHT" ? `${trimQty(r.decoded)} kg` : formatMoney(r.decoded)}
            </p>
          </li>
        ))}
      </ul>
      <p className="text-[12px] text-muted-foreground">{t("equipment.scale.readOnly")}</p>
      {canManage ? (
        <a className="text-[13px] font-semibold text-primary underline" href={BO_SETTINGS}>
          {t("equipment.scale.edit")}
        </a>
      ) : null}
    </Section>
  );
}

function AgentSection() {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const [agent, pairState, busy] = useUnit([$agentStatus, $pairState, $busy]);
  const [code, setCode] = useState("");
  const tone = agent.status === "online" ? "success" : agent.status === "offline" ? "destructive" : "neutral";
  return (
    <Section
      icon={Cpu}
      title={t("equipment.agentBlock.title")}
      status={
        <StatusChip tone={tone} dot>
          <span data-testid="agent-status">{t(`equipment.agent.states.${agent.status}`)}</span>
        </StatusChip>
      }
      testId="equipment-agent"
    >
      <dl className="grid grid-cols-2 gap-1 text-[13px]">
        <dt className="text-muted-foreground">{t("equipment.agentBlock.version")}</dt>
        <dd>{agent.version ?? "—"}</dd>
        <dt className="text-muted-foreground">{t("equipment.agentBlock.lastSeen")}</dt>
        <dd>{agent.checked_at ? tashkentTime(agent.checked_at) : "—"}</dd>
      </dl>
      {agent.status === "unpaired" || agent.status === "not_installed" || pairState !== "idle" ? (
        <div className="flex flex-col gap-2">
          <Label htmlFor="agent-pair">{t("equipment.agentBlock.pairCode")}</Label>
          <div className="flex gap-2">
            <Input
              id="agent-pair"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))}
              className="h-12 w-40 text-center font-mono text-[20px] tracking-[0.3em]"
            />
            <Button
              size="pos"
              variant="secondary"
              disabled={code.length !== 6 || busy.pairing}
              onClick={() => pairRequested(code)}
            >
              {t("equipment.agentBlock.pair")}
            </Button>
          </div>
          {pairState === "paired" ? (
            <p className="text-[13px] text-success-strong">{t("equipment.agentBlock.paired")}</p>
          ) : pairState === "no_device" ? (
            <p className="text-[13px] text-destructive-strong">{t("equipment.agentBlock.noDevice")}</p>
          ) : pairState === "error" ? (
            <p className="text-[13px] text-destructive-strong">{t("equipment.agent.errors.unreachable")}</p>
          ) : null}
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button size="pos" variant="secondary" onClick={() => agentCheckRequested()}>
          {t("equipment.agentBlock.check")}
        </Button>
        <span className="text-[12px] text-muted-foreground">{t("equipment.agentBlock.manage")}</span>
      </div>
    </Section>
  );
}

function CardSection() {
  const { t } = useTranslation("pos");
  const device = useUnit($posDevice);
  const canManage = usePosPermission("cash_register.manage");
  return (
    <Section icon={CreditCard} title={t("equipment.card.title")} testId="equipment-card">
      {device?.cashRegisterId ? (
        <TerminalPairingSection
          cashRegisterId={device.cashRegisterId}
          branchId={device.branchId}
          canManage={canManage}
        />
      ) : (
        <p className="text-[13px] text-muted-foreground">{t("equipment.card.noRegister")}</p>
      )}
    </Section>
  );
}

function CatalogViewSection() {
  const { t } = useTranslation("pos");
  const view = useUnit($catalogView);
  return (
    <Section icon={LayoutGrid} title={t("equipment.catalogView.title")}>
      <SegmentedControl
        label={t("equipment.catalogView.title")}
        density="touch"
        value={view}
        onChange={(v) => catalogViewChanged(v)}
        options={[
          { value: "grid", label: t("equipment.catalogView.grid") },
          { value: "list", label: t("equipment.catalogView.list") },
        ]}
      />
    </Section>
  );
}

export const Equipment = {
  route: "settings/devices",
  titleKey: "pos:equipment.title",
  Page: EquipmentPage,
} as const;

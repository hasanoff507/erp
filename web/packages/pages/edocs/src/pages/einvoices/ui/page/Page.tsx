/**
 * BO-15 — Kiruvchi va chiquvchi e-faktura markazi (07, route /app/einvoices; 06 §6 wireframe).
 * Page actions «Chek asosida e-faktura», «Chiquvchi e-faktura» (`einvoice.create`); tabs Kiruvchi · Chiquvchi ·
 * E-TTN · E-ishonchnomalar with counts; KPI cards (incoming of the month, awaiting signature, deferred VAT credit,
 * outgoing not sent); the E-IMZO key (owner, role, valid to — 21 §5; production signer ⛔ 26 #118).
 * Offline: view only — signing needs E-IMZO and the operator. useEffect only fires pageMounted (24 §2).
 */
import { useUnit } from "effector-react";
import {
  CircleAlert,
  FilePlus2,
  FileText,
  Hourglass,
  KeyRound,
  ReceiptText,
  Send,
  WifiOff,
} from "lucide-react";
import { useEffect } from "react";

import { formatDate, formatMoney } from "@shared/lib/format";
import { $isOnline } from "@shared/state/network";
import { useCan } from "@shared/state/permissions";
import {
  Banner,
  Button,
  Card,
  FormField,
  KpiCard,
  NoPermissionState,
  SimpleSelect,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Icon,
} from "@shared/ui";

import { errorText, todayIso } from "#/shared/lib/effect.ts";
import { useTx } from "#/shared/lib/i18n.ts";

import {
  $actionError,
  $dialog,
  $keyId,
  $keys,
  $keysError,
  $kpis,
  $notice,
  $tab,
  $tabCounts,
  TABS,
  actionErrorDismissed,
  dialogOpened,
  isTab,
  keyChosen,
  noticeDismissed,
  pageMounted,
  tabChanged,
} from "../../model/index.ts";
import { CreateOutDialog } from "../dialogs/CreateOutDialog.tsx";
import { FromReceiptDialog } from "../dialogs/FromReceiptDialog.tsx";
import { DetailSheet } from "../detail/DetailSheet.tsx";
import { EttnTab } from "../ettn/EttnTab.tsx";
import { InboundTab } from "../inbound/InboundTab.tsx";
import { OutboundTab } from "../outbound/OutboundTab.tsx";
import { PoaTab } from "../poa/PoaTab.tsx";

const m0 = (v: string) => formatMoney(v, { precision: 0 });

function Kpis() {
  const { t } = useTx();
  const kpis = useUnit($kpis);
  if (!kpis) return null;
  return (
    <div className="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-4" data-testid="einvoice-kpis">
      <KpiCard
        label={t("kpi.incoming")}
        value={String(kpis.inCount)}
        icon={FileText}
        tone="primary"
        note={t("kpi.incomingNote", { total: m0(kpis.inTotal), vat: m0(kpis.inVat) })}
      />
      <KpiCard
        label={t("kpi.awaiting")}
        value={String(kpis.awaitingSignature)}
        icon={Hourglass}
        tone="warning"
      />
      <KpiCard
        label={t("kpi.deferred")}
        value={m0(kpis.deferredVat)}
        icon={CircleAlert}
        tone="destructive"
        note={t("kpi.deferredNote")}
      />
      <KpiCard label={t("kpi.outUnsent")} value={String(kpis.outUnsent)} icon={Send} tone="info" />
    </div>
  );
}

function KeyCard() {
  const { t } = useTx();
  const [keys, keyId, error, choose] = useUnit([$keys, $keyId, $keysError, keyChosen]);
  const key = keys.find((k) => k.id === keyId) ?? null;
  if (error) {
    return (
      <Banner tone="warning" icon={KeyRound}>
        {errorText(error)}
      </Banner>
    );
  }
  return (
    <Card className="flex flex-wrap items-end gap-4 p-4" data-testid="eimzo-key">
      <FormField label={t("eimzo.key")} className="w-72">
        <SimpleSelect
          options={keys.map((k) => ({ value: k.id, label: `${k.owner} · ${k.serial}` }))}
          value={keyId ?? ""}
          onValueChange={choose}
        />
      </FormField>
      {key ? (
        <dl className="flex flex-wrap gap-x-6 gap-y-1 text-[13px]">
          <div>
            <dt className="text-foreground-secondary">{t("eimzo.owner")}</dt>
            <dd className="font-semibold">{key.owner}</dd>
          </div>
          <div>
            <dt className="text-foreground-secondary">{t("eimzo.role")}</dt>
            <dd className="font-semibold">{key.role ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-foreground-secondary">{t("eimzo.validTo")}</dt>
            <dd className="font-semibold">{formatDate(key.validTo)}</dd>
          </div>
        </dl>
      ) : null}
    </Card>
  );
}

function EInvoicesPage() {
  const { t } = useTx();
  const canIn = useCan({ permission: "purchases.post" });
  const canOut = useCan({ anyOf: ["einvoice.sign", "purchases.post"] });
  const canCreate = useCan({ permission: "einvoice.create" });
  const canAny = useCan({ anyOf: ["purchases.post", "einvoice.create", "einvoice.sign"] });
  const [mounted, onTab, openDialog, dismissNotice, dismissError] = useUnit([
    pageMounted,
    tabChanged,
    dialogOpened,
    noticeDismissed,
    actionErrorDismissed,
  ]);
  const [tab, counts, notice, actionError, dialog, online] = useUnit([
    $tab,
    $tabCounts,
    $notice,
    $actionError,
    $dialog,
    $isOnline,
  ]);

  useEffect(() => {
    if (canAny) mounted({ today: todayIso(), canOutbound: canOut });
  }, [mounted, canAny, canOut]);

  if (!canAny) return <NoPermissionState />;
  const visible = TABS.filter((x) => (x === "in" ? canIn : x === "out" ? canOut : true));
  const current = visible.includes(tab) ? tab : (visible[0] ?? "ettn");

  return (
    <div className="flex flex-col gap-[18px]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-small text-foreground-secondary">{t("subtitle")}</p>
        {canCreate ? (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" disabled={!online} onClick={() => openDialog("fromReceipt")}>
              <Icon as={ReceiptText} size="sm" />
              {t("actions.fromReceipt")}
            </Button>
            <Button disabled={!online} onClick={() => openDialog("createOut")}>
              <Icon as={FilePlus2} size="sm" />
              {t("actions.createOut")}
            </Button>
          </div>
        ) : null}
      </div>
      {online ? null : (
        <Banner tone="warning" icon={WifiOff}>
          {t("offline")}
        </Banner>
      )}
      {notice ? (
        <Banner
          tone="success"
          icon={FileText}
          action={
            <Button size="sm" variant="secondary" onClick={dismissNotice}>
              {t("dialogs.close")}
            </Button>
          }
        >
          <span data-testid="edocs-notice">{t(notice.key, notice.params)}</span>
        </Banner>
      ) : null}
      {actionError && dialog === null ? (
        <Banner
          tone="destructive"
          icon={CircleAlert}
          live="assertive"
          action={
            <Button size="sm" variant="secondary" onClick={dismissError}>
              {t("dialogs.close")}
            </Button>
          }
        >
          <span data-testid="edocs-error">{errorText(actionError)}</span>
        </Banner>
      ) : null}
      <Kpis />
      <KeyCard />
      <Tabs value={current} onValueChange={(v) => (isTab(v) ? onTab(v) : undefined)}>
        <TabsList>
          {visible.map((x) => (
            <TabsTrigger key={x} value={x}>
              {t(`tabs.${x}`)} ({counts[x]})
            </TabsTrigger>
          ))}
        </TabsList>
        {canIn ? (
          <TabsContent value="in">
            <InboundTab />
          </TabsContent>
        ) : null}
        {canOut ? (
          <TabsContent value="out">
            <OutboundTab />
          </TabsContent>
        ) : null}
        <TabsContent value="ettn">
          <EttnTab />
        </TabsContent>
        <TabsContent value="poa">
          <PoaTab />
        </TabsContent>
      </Tabs>
      <DetailSheet />
      {canCreate ? (
        <>
          <FromReceiptDialog />
          <CreateOutDialog />
        </>
      ) : null}
    </div>
  );
}

export const EInvoices = {
  route: "einvoices",
  titleKey: "edocs:title",
  Page: EInvoicesPage,
} as const;

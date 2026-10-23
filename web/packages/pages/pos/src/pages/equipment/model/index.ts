/**
 * POS-16 — Uskunalar sozlamasi (07 POS-16; 24 §6; US-M01-07; QT-M01-22). Device-local: the printer settings
 * live in erp-device `device_settings` (`printer.*`, survive a logout — 16 §12), nothing is written to the
 * server. «Printerni aniqlash» opens the browser picker (Web Serial → WebUSB → system printer), «Sinov chek»
 * prints the test receipt with the form's settings (raster automatically for Қ/Ғ/Ҳ). Scale templates come
 * from the pulled `settings` scope (read-only here); the Do'kon agenti block pairs the local agent.
 */
import { attach, combine, createEffect, createEvent, createStore, sample } from "effector";

import { AGENT_TOKEN_KEY, createAgentClient, type AgentClient } from "@shared/lib/agent";
import {
  DEFAULT_PRINTER_SETTINGS,
  PrinterError,
  availableTransports,
  browserPrinterEnvironment,
  createPrinterPort,
  detectPrinterTransport,
  loadPrinterSettings,
  requestPrinterDevice,
  savePrinterSettings,
  type DeviceSettingsProvider,
  type PrintResult,
  type PrinterEnvironment,
  type PrinterRenderMode,
  type PrinterSettings,
  type PrinterTransport,
} from "@shared/lib/printer";
import { testReceiptDoc, type PaperWidth, type Rasterizer } from "@shared/lib/receipt";
import type { WeightBarcodeTemplate } from "@shared/lib/scale";
import { deviceSettings, settings as posSettings } from "@shared/offline";
import {
  $agentStatus,
  agentProbeConfigured,
  agentStatusRefreshRequested,
  type AgentStatus,
} from "@shared/state/device";

import { $posDevice } from "#/entities/pos-session/index.ts";

import { CATALOG_VIEW_KEY, printerFormErrors, type CatalogView } from "./lib.ts";

export * from "./lib.ts";

export interface EquipmentDeps {
  store: DeviceSettingsProvider;
  env(): PrinterEnvironment;
  agentState(): AgentStatus;
  agent(): AgentClient;
  templates(): Promise<WeightBarcodeTemplate[] | null>;
  deviceId(): string | null;
  now(): Date;
  /** Tests only — the browser canvas rasterizer is the default (24 §6.1 raster for Қ/Ғ/Ҳ). */
  rasterizer?: Rasterizer;
}

let agentClient: AgentClient | null = null;
/** Do'kon agenti client of the POS (token in erp-device, hw-api.md §1). */
export function posAgentClient(): AgentClient {
  agentClient ??= createAgentClient({
    tokenStore: {
      get: () => deviceSettings.get<string>(AGENT_TOKEN_KEY).then((t) => t ?? null),
      set: (t) => (t ? deviceSettings.set(AGENT_TOKEN_KEY, t) : deviceSettings.remove(AGENT_TOKEN_KEY)),
    },
  });
  return agentClient;
}

function defaultDeps(): EquipmentDeps {
  return {
    store: { get: (k) => deviceSettings.get(k), set: (k, v) => deviceSettings.set(k, v) },
    env: browserPrinterEnvironment,
    agentState: () => $agentStatus.getState(),
    agent: posAgentClient,
    templates: async () => {
      try {
        return (await posSettings.get()).weightBarcodeTemplates as WeightBarcodeTemplate[];
      } catch {
        return null;
      }
    },
    deviceId: () => $posDevice.getState()?.deviceId ?? null,
    now: () => new Date(),
  };
}

const $deps = createStore<EquipmentDeps | null>(null, { serialize: "ignore", skipVoid: false });
export const configureEquipment = createEvent<Partial<EquipmentDeps>>();
$deps.on(configureEquipment, (prev, d) => ({ ...(prev ?? defaultDeps()), ...d }));
const deps = (d: EquipmentDeps | null): EquipmentDeps => d ?? defaultDeps();

export interface TestOutcome {
  ok: boolean;
  at: string;
  mode: PrintResult["mode"] | null;
  /** PrinterError code (i18n `pos:equipment.printer.errors.<code>`). */
  code: string | null;
}

// ---- events ---------------------------------------------------------------------------------------
export const equipmentOpened = createEvent();
export const transportChanged = createEvent<PrinterTransport>();
export const paperWidthChanged = createEvent<PaperWidth>();
export const renderModeChanged = createEvent<PrinterRenderMode>();
export const lanAddressChanged = createEvent<string>();
export const catalogViewChanged = createEvent<CatalogView>();
export const saveRequested = createEvent();
export const detectRequested = createEvent();
export const testRequested = createEvent();
export const pairRequested = createEvent<string>();
export const agentCheckRequested = createEvent();

// ---- effects --------------------------------------------------------------------------------------
export const loadFx = attach({
  source: $deps,
  effect: createEffect(async (d: EquipmentDeps | null) => {
    const x = deps(d);
    const saved = await loadPrinterSettings(x.store);
    const env = x.env();
    const view = await x.store.get(CATALOG_VIEW_KEY).catch(() => undefined);
    const auto = saved.transport
      ? null
      : await detectPrinterTransport({ settings: saved, agentStatus: x.agentState(), env }).catch(() => null);
    const catalogView: CatalogView = view === "list" ? "list" : "grid";
    return { saved, auto, available: availableTransports(env), templates: await x.templates(), catalogView };
  }),
});

export const saveFx = attach({
  source: $deps,
  mapParams: (input: { form: PrinterSettings; catalogView: CatalogView }, d) => ({ input, d }),
  effect: createEffect(
    async ({
      input,
      d,
    }: {
      input: { form: PrinterSettings; catalogView: CatalogView };
      d: EquipmentDeps | null;
    }) => {
      const x = deps(d);
      await savePrinterSettings(x.store, input.form);
      await x.store.set(CATALOG_VIEW_KEY, input.catalogView);
      return input.form;
    },
  ),
});

export const detectFx = attach({
  source: $deps,
  mapParams: (transport: PrinterTransport | null, d) => ({ transport, d }),
  effect: createEffect(
    async ({ transport, d }: { transport: PrinterTransport | null; d: EquipmentDeps | null }) => {
      const picker =
        transport === "webserial" || transport === "webusb" || transport === "webbluetooth"
          ? transport
          : "auto";
      return requestPrinterDevice(picker, deps(d).env());
    },
  ),
});

export const testFx = attach({
  source: $deps,
  mapParams: (form: PrinterSettings, d) => ({ form, d }),
  effect: createEffect(
    async ({ form, d }: { form: PrinterSettings; d: EquipmentDeps | null }): Promise<TestOutcome> => {
      const x = deps(d);
      const at = x.now().toISOString();
      try {
        const port = createPrinterPort(form, {
          agent: x.agent(),
          agentState: () => x.agentState(),
          env: x.env(),
          ...(x.rasterizer ? { rasterizer: x.rasterizer } : {}),
        });
        const result = await port.printReceipt(
          testReceiptDoc({
            at,
            ...(form.transport ? { transport: form.transport } : {}),
            paperWidth: form.paperWidth,
          }),
        );
        return { ok: true, at, mode: result.mode, code: null };
      } catch (e) {
        return { ok: false, at, mode: null, code: e instanceof PrinterError ? e.code : "write_failed" };
      }
    },
  ),
});

export const pairFx = attach({
  source: $deps,
  mapParams: (code: string, d) => ({ code, d }),
  effect: createEffect(async ({ code, d }: { code: string; d: EquipmentDeps | null }) => {
    const x = deps(d);
    const deviceId = x.deviceId();
    if (!deviceId) throw Object.assign(new Error("no_device"), { kind: "no_device" });
    await x.agent().pair(code, deviceId);
  }),
});

// ---- stores ---------------------------------------------------------------------------------------
export const $form = createStore<PrinterSettings>({ ...DEFAULT_PRINTER_SETTINGS })
  .on(loadFx.doneData, (_, r) => ({ ...r.saved, transport: r.saved.transport ?? r.auto }))
  .on(transportChanged, (f, transport) => ({ ...f, transport }))
  .on(paperWidthChanged, (f, paperWidth) => ({ ...f, paperWidth }))
  .on(renderModeChanged, (f, renderMode) => ({ ...f, renderMode }))
  .on(lanAddressChanged, (f, v) => ({ ...f, lanAddress: v.trim().slice(0, 32) || null }))
  .on(detectFx.doneData, (f, transport) => ({ ...f, transport }));
export const $savedForm = createStore<PrinterSettings | null>(null, { skipVoid: false })
  .on(loadFx.doneData, (_, r) => r.saved)
  .on(saveFx.doneData, (_, f) => f);
export const $autoDetected = createStore<PrinterTransport | null>(null, { skipVoid: false }).on(
  loadFx.doneData,
  (_, r) => r.auto,
);
export const $available = createStore<PrinterTransport[]>([]).on(loadFx.doneData, (_, r) => r.available);
export const $templates = createStore<WeightBarcodeTemplate[] | null>(null, { skipVoid: false }).on(
  loadFx.doneData,
  (_, r) => r.templates,
);
export const $catalogView = createStore<CatalogView>("grid")
  .on(loadFx.doneData, (_, r) => r.catalogView)
  .on(catalogViewChanged, (_, v) => v);
export const $formErrors = $form.map(printerFormErrors);
export const $lastTest = createStore<TestOutcome | null>(null, { skipVoid: false }).on(
  testFx.doneData,
  (_, r) => r,
);
export const $detectError = createStore<string | null>(null, { skipVoid: false })
  .on(detectFx.failData, (_, e) => (e instanceof PrinterError ? e.code : "device_not_found"))
  .reset(detectFx);
export const $justSaved = createStore(false)
  .on(saveFx.done, () => true)
  .reset(transportChanged, paperWidthChanged, renderModeChanged, lanAddressChanged, catalogViewChanged);
export const $pairState = createStore<"idle" | "paired" | "error" | "no_device">("idle")
  .on(pairFx.done, () => "paired")
  .on(pairFx.failData, (_, e) => ((e as { kind?: string }).kind === "no_device" ? "no_device" : "error"))
  .reset(pairFx);
export const $busy = combine(
  [detectFx.pending, testFx.pending, saveFx.pending, pairFx.pending],
  ([detecting, testing, saving, pairing]) => ({ detecting, testing, saving, pairing }),
);
export const $dirty = combine(
  $form,
  $savedForm,
  $catalogView,
  (f, s, _v) => JSON.stringify(f) !== JSON.stringify(s),
);

// ---- wiring ---------------------------------------------------------------------------------------
sample({ clock: equipmentOpened, target: loadFx });
// make sure the agent status is probed with this POS's client (the bootstrap may already have done it)
sample({
  clock: equipmentOpened,
  source: $deps,
  fn: (d) => {
    const x = deps(d);
    return () => x.agent().probe();
  },
  target: agentProbeConfigured,
});
sample({
  clock: [equipmentOpened, agentCheckRequested, pairFx.done],
  fn: () => undefined,
  target: agentStatusRefreshRequested,
});
sample({
  clock: saveRequested,
  source: { form: $form, catalogView: $catalogView, errors: $formErrors },
  filter: ({ errors }) => errors.length === 0,
  fn: ({ form, catalogView }) => ({ form, catalogView }),
  target: saveFx,
});
sample({ clock: detectRequested, source: $form, fn: (f) => f.transport, target: detectFx });
sample({
  clock: testRequested,
  source: $form,
  filter: (f) => printerFormErrors(f).length === 0,
  target: testFx,
});
sample({ clock: pairRequested, filter: (code) => /^[0-9]{6}$/.test(code), target: pairFx });

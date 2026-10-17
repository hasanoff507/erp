/**
 * `cloud` and `system_print` transports (24 §6.1).
 *
 * Cloud (Star CloudPRNT / Epson Server Direct Print — the only direct iOS path): the front end only queues
 * a job on the server, the printer polls `/print/cloudprnt` / `/print/epson-sdp`. The server queue is
 * Bosqich 5; until an API is injected the adapter reports `cloud_unavailable` (POS-04 → electronic receipt).
 *
 * System print: the receipt DOM is appended to <body>, every other body child is hidden through CSSOM
 * (CSP-safe, no stylesheet needed), `window.print()` opens the OS dialog, then the page is restored.
 */
import { PrinterError } from "./types.ts";

export interface CloudPrintJob {
  /** UUID v7 chosen by the client — idempotency key of the queue. */
  id: string;
  cloud_printer_id: string;
  kind: "receipt" | "test" | "label";
  raster: { width_dots: number; height_dots: number; data_base64: string };
}

export interface CloudPrintApi {
  submit(job: CloudPrintJob): Promise<{ id: string; status: "queued" | "printing" | "done" | "failed" }>;
  status(cloudPrinterId: string): Promise<{ online: boolean }>;
}

export async function cloudSubmit(api: CloudPrintApi | undefined, job: CloudPrintJob): Promise<void> {
  if (!api) throw new PrinterError("cloud_unavailable", "cloud");
  try {
    const result = await api.submit(job);
    if (result.status === "failed") throw new PrinterError("cloud_failed", "cloud");
  } catch (e) {
    if (e instanceof PrinterError) throw e;
    throw new PrinterError("cloud_failed", "cloud", e);
  }
}

export interface PrintWindow {
  document: Document;
  print(): void;
  addEventListener(type: "afterprint", listener: () => void): void;
  removeEventListener(type: "afterprint", listener: () => void): void;
}

/** Prints `element` through the OS dialog and restores the page afterwards. */
export async function systemPrint(
  win: PrintWindow | undefined,
  element: HTMLElement,
  maxWaitMs = 60_000,
): Promise<void> {
  if (!win || typeof win.print !== "function") throw new PrinterError("not_supported", "system_print");
  const { body } = win.document;
  const hidden: { el: HTMLElement; display: string }[] = [];
  for (const child of Array.from(body.children)) {
    const el = child as HTMLElement;
    if (!el.style) continue;
    hidden.push({ el, display: el.style.display });
    el.style.display = "none";
  }
  const root = win.document.createElement("div");
  root.append(element);
  body.append(root);

  let done = false;
  let resolveAfter: () => void = () => undefined;
  const after = new Promise<void>((resolve) => {
    resolveAfter = resolve;
  });
  const onAfter = () => {
    done = true;
    resolveAfter();
  };
  win.addEventListener("afterprint", onAfter);
  try {
    win.print(); // blocking in Chromium; other browsers return at once and fire `afterprint` later
    if (!done) {
      await Promise.race([after, new Promise<void>((resolve) => setTimeout(resolve, maxWaitMs))]);
    }
  } catch (e) {
    throw new PrinterError("write_failed", "system_print", e);
  } finally {
    win.removeEventListener("afterprint", onAfter);
    root.remove();
    for (const { el, display } of hidden) el.style.display = display;
  }
}

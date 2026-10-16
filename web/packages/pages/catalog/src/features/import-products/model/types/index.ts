import type {
  ImportErrorItem,
  ImportErrorPage,
  ImportJobAccepted,
  ImportJobCreated,
  ImportJobOut,
} from "@shared/models";

/** Import kinds of 19 §6. Bosqich 1 builds `products` only (opening_stock — Bosqich 2, opening_debts — Bosqich 4). */
export type ImportKind = "products" | "opening_stock" | "opening_debts";

export const IMPORT_KINDS: readonly ImportKind[] = ["products", "opening_stock", "opening_debts"];
export const ENABLED_IMPORT_KINDS: ReadonlySet<ImportKind> = new Set<ImportKind>(["products"]);

/** `GET /import-jobs/{id}` status (19 §6). */
export type ImportJobStatus = "uploaded" | "validating" | "validated" | "committing" | "committed" | "failed";

/**
 * Flow phase (what the UI shows):
 * - `select` — choose a file;
 * - `processing` — upload + server validation running (sub-step in `$processingStep`);
 * - `review` — validated: summary + error rows, confirm commit;
 * - `invalid` — validation failed for every row / the file: error rows, re-upload only;
 * - `committing` — commit running;
 * - `done` — products created.
 */
export type ImportPhase = "select" | "processing" | "review" | "invalid" | "committing" | "done";
export type ProcessingStep = "uploading" | "validating";

/** Result handed to `onDone` (and shown in the summary). */
export interface ImportProductsResult {
  jobId: string;
  totalRows: number;
  /** Products created (`result.created_product_count`). */
  createdProductCount: number;
  /** Error rows skipped by the commit (`skip_error_rows=true`). */
  skippedRows: number;
  /** Initial price-change document(s) created from the `price` column. */
  createdDocIds: string[];
}

/** The generated `inventory` functions the flow uses — injectable for unit tests. */
export interface ImportApi {
  /** `GET /import-jobs/templates/{kind}` as a Blob (CSV, UTF-8, `;`). */
  template: (kind: ImportKind) => Promise<Blob>;
  createJob: (kind: ImportKind, file: File) => Promise<ImportJobCreated>;
  validate: (jobId: string) => Promise<ImportJobAccepted>;
  getJob: (jobId: string) => Promise<ImportJobOut>;
  listErrors: (jobId: string, cursor: string | null) => Promise<ImportErrorPage>;
  commit: (jobId: string) => Promise<ImportJobAccepted>;
}

export interface ImportFlowDeps {
  api: ImportApi;
  /** Delay between status polls (ms → Promise). */
  sleep: (ms: number) => Promise<void>;
  /** Hands a downloaded file to the browser ("Saqlash"). */
  saveFile: (blob: Blob, filename: string) => void;
  /** Poll interval schedule in ms (last value repeats). */
  pollIntervals?: readonly number[];
  /** Give up polling after this many ms (then a timeout error is shown; the job keeps running). */
  pollTimeoutMs?: number;
}

export type { ImportErrorItem, ImportJobOut };

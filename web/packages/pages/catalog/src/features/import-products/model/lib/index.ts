import { ApiError } from "@shared/api";

import type { ImportJobOut, ImportJobStatus, ImportProductsResult } from "../types/index.ts";

/** Polling gave up (the server job keeps running) — a client-side code, text in `catalog:server.client`. */
export const IMPORT_POLL_TIMEOUT = "IMPORT_POLL_TIMEOUT";
/** The flow was reset/unmounted while polling — never shown. */
export const IMPORT_POLL_CANCELED = "IMPORT_POLL_CANCELED";

export const DEFAULT_POLL_INTERVALS: readonly number[] = [500, 1000, 1000, 2000];
export const DEFAULT_POLL_TIMEOUT_MS = 10 * 60 * 1000;

const VALIDATE_DONE: ReadonlySet<string> = new Set<ImportJobStatus>(["validated", "failed", "committed"]);
const COMMIT_DONE: ReadonlySet<string> = new Set<ImportJobStatus>(["committed", "failed"]);

/** True when the job left the running state of the given stage. */
export function isSettled(stage: "validate" | "commit", status: string): boolean {
  return (stage === "validate" ? VALIDATE_DONE : COMMIT_DONE).has(status);
}

export function intervalAt(intervals: readonly number[], attempt: number): number {
  return intervals[Math.min(attempt, intervals.length - 1)] ?? 1000;
}

export function pollTimeoutError(): ApiError {
  return new ApiError({ status: null, code: IMPORT_POLL_TIMEOUT, messageKey: "client.import_poll_timeout" });
}

export function pollCanceledError(): ApiError {
  return new ApiError({ status: null, code: IMPORT_POLL_CANCELED, messageKey: "errors.request_canceled" });
}

function asCount(value: unknown): number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : 0;
}

function asIds(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

/** `GET /import-jobs/{id}` after commit → the flow result (`result` is a free-form object in the schema). */
export function resultFromJob(job: ImportJobOut): ImportProductsResult {
  return {
    jobId: job.id,
    totalRows: job.total_rows,
    createdProductCount: asCount(job.result.created_product_count),
    skippedRows: job.error_rows,
    createdDocIds: asIds(job.result.created_doc_ids),
  };
}

/** File-level problem (row 0, field "file") rather than row errors. */
export function isFileLevelError(item: { row: number; field: string }): boolean {
  return item.row === 0 || item.field === "file";
}

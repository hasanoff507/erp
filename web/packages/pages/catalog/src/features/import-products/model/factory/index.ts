/**
 * Product import flow model (19 §6, US-M04-04, 07 BO-21 ③a): upload → async validate (poll) →
 * error rows → commit (poll) → result. A factory: every mounted `ImportProductsFlow` owns its own
 * instance (the BO-05 import screen and the onboarding wizard step may both exist in one session).
 *
 *   POST /import-jobs (multipart, kind=products) → 201 {id, status:"uploaded"}
 *   POST /import-jobs/{id}/validate → 202 → poll GET /import-jobs/{id} until validated | failed
 *   GET  /import-jobs/{id}/errors?cursor= (row, field, code, message_key)
 *   POST /import-jobs/{id}/commit {skip_error_rows:true} → 202 → poll until committed | failed
 */
import { combine, createEffect, createEvent, createStore, sample } from "effector";

import { toApiError, type ApiError } from "@shared/api";
import type { ImportErrorPage, ImportJobCreated } from "@shared/models";

import {
  DEFAULT_POLL_INTERVALS,
  DEFAULT_POLL_TIMEOUT_MS,
  IMPORT_POLL_CANCELED,
  intervalAt,
  isSettled,
  pollCanceledError,
  pollTimeoutError,
  resultFromJob,
} from "../lib/index.ts";
import type {
  ImportErrorItem,
  ImportFlowDeps,
  ImportJobOut,
  ImportKind,
  ImportPhase,
  ImportProductsResult,
  ProcessingStep,
} from "../types/index.ts";

/** Upload errors shown on the dropzone itself (17 §12) rather than in the banner. */
const FILE_ERROR_CODES: ReadonlySet<string> = new Set([
  "FILE_TOO_LARGE",
  "UNSUPPORTED_FILE_TYPE",
  "IMPORT_FILE_INVALID",
]);

export const ERRORS_PAGE_SIZE = 100;

export function createImportFlow(deps: ImportFlowDeps, kind: ImportKind = "products") {
  const intervals = deps.pollIntervals ?? DEFAULT_POLL_INTERVALS;
  const timeoutMs = deps.pollTimeoutMs ?? DEFAULT_POLL_TIMEOUT_MS;
  /** Bumped on restart/dispose: a running poll loop of an older generation stops. */
  let generation = 0;

  async function poll(jobId: string, stage: "validate" | "commit", gen: number): Promise<ImportJobOut> {
    const started = Date.now();
    for (let attempt = 0; ; attempt += 1) {
      if (gen !== generation) throw pollCanceledError();
      const job = await deps.api.getJob(jobId);
      if (gen !== generation) throw pollCanceledError();
      if (isSettled(stage, job.status)) return job;
      if (Date.now() - started > timeoutMs) throw pollTimeoutError();
      await deps.sleep(intervalAt(intervals, attempt));
    }
  }

  // --- events -----------------------------------------------------------------------------------
  const fileSelected = createEvent<File>();
  const fileRemoved = createEvent();
  /** Client-side dropzone rejection (i18n key of `common`). */
  const fileRejected = createEvent<string>();
  const startRequested = createEvent();
  const commitRequested = createEvent();
  const moreErrorsRequested = createEvent();
  /** Back to the file step (fix the file and upload again — a new job). */
  const restarted = createEvent();
  const templateRequested = createEvent();
  const disposed = createEvent();

  // --- effects ----------------------------------------------------------------------------------
  const uploadFx = createEffect<File, ImportJobCreated, ApiError>(async (file) => {
    try {
      return await deps.api.createJob(kind, file);
    } catch (e) {
      throw toApiError(e);
    }
  });

  const validateFx = createEffect<string, ImportJobOut, ApiError>(async (jobId) => {
    const gen = generation;
    try {
      await deps.api.validate(jobId);
      return await poll(jobId, "validate", gen);
    } catch (e) {
      throw toApiError(e);
    }
  });

  const commitFx = createEffect<string, ImportJobOut, ApiError>(async (jobId) => {
    const gen = generation;
    try {
      try {
        await deps.api.commit(jobId);
      } catch (e) {
        // A double submit (or a retry after a lost answer) finds the job already committed: show it.
        if (toApiError(e).code !== "IMPORT_JOB_ALREADY_COMMITTED") throw e;
        const job = await deps.api.getJob(jobId);
        if (job.status === "committed") return job;
        throw e;
      }
      return await poll(jobId, "commit", gen);
    } catch (e) {
      throw toApiError(e);
    }
  });

  const errorsFx = createEffect<{ jobId: string; cursor: string | null }, ImportErrorPage, ApiError>(
    async ({ jobId, cursor }) => {
      try {
        return await deps.api.listErrors(jobId, cursor);
      } catch (e) {
        throw toApiError(e);
      }
    },
  );

  /** "Shablonni yuklab olish" — 19 §6 `GET /import-jobs/templates/{kind}` (CSV). */
  const templateFx = createEffect<void, void, ApiError>(async () => {
    try {
      const blob = await deps.api.template(kind);
      deps.saveFile(blob, `${kind}.csv`);
    } catch (e) {
      throw toApiError(e);
    }
  });

  const cancelPollsFx = createEffect(() => {
    generation += 1;
  });

  // --- stores -----------------------------------------------------------------------------------
  const $file = createStore<File | null>(null, { skipVoid: false })
    .on(fileSelected, (_, file) => file)
    .reset(fileRemoved, restarted);

  const $phase = createStore<ImportPhase>("select")
    .on(startRequested, () => "processing")
    .on(validateFx.doneData, (_, job) =>
      job.status === "validated" ? "review" : job.status === "committed" ? "done" : "invalid",
    )
    .on(uploadFx.fail, () => "select")
    .on(validateFx.failData, (phase, error) => (error.code === IMPORT_POLL_CANCELED ? phase : "select"))
    .on(commitRequested, () => "committing")
    .on(commitFx.doneData, (_, job) => (job.status === "committed" ? "done" : "invalid"))
    .on(commitFx.failData, (phase, error) => (error.code === IMPORT_POLL_CANCELED ? phase : "review"))
    .reset(restarted);

  const $processingStep = createStore<ProcessingStep>("uploading")
    .on(uploadFx, () => "uploading")
    .on(validateFx, () => "validating");

  const $job = createStore<ImportJobOut | null>(null, { skipVoid: false })
    .on(uploadFx.doneData, (_, created) => ({
      id: created.id,
      kind: created.kind,
      status: created.status,
      total_rows: created.total_rows,
      ok_rows: 0,
      error_rows: 0,
      result: {},
      created_at: "",
    }))
    .on(validateFx.doneData, (_, job) => job)
    .on(commitFx.doneData, (_, job) => job)
    .reset(restarted);

  const $errorRows = createStore<ImportErrorItem[]>([])
    .on(errorsFx.done, (rows, { params, result }) =>
      params.cursor ? [...rows, ...result.items] : result.items,
    )
    .reset(restarted, startRequested);

  const $errorsCursor = createStore<string | null>(null, { skipVoid: false })
    .on(errorsFx.doneData, (_, page) => page.next_cursor)
    .reset(restarted, startRequested);

  /** Server rejection of the file itself (dropzone error) or a client-side rejection. */
  const $fileError = createStore<string | null>(null, { skipVoid: false })
    .on(fileRejected, (_, key) => key)
    .on(uploadFx.failData, (_, error) => (FILE_ERROR_CODES.has(error.code) ? error.messageKey : null))
    .reset(fileSelected, fileRemoved, startRequested);

  /** Any other failure (network, permission, commit state…) → banner. */
  const $flowError = createStore<ApiError | null>(null, { skipVoid: false })
    .on(uploadFx.failData, (_, error) => (FILE_ERROR_CODES.has(error.code) ? null : error))
    .on(validateFx.failData, (_, error) => (error.code === IMPORT_POLL_CANCELED ? null : error))
    .on(commitFx.failData, (_, error) => (error.code === IMPORT_POLL_CANCELED ? null : error))
    .on(errorsFx.failData, (_, error) => error)
    .on(templateFx.failData, (_, error) => error)
    .reset(startRequested, commitRequested, restarted, fileSelected);

  const $result = $job.map<ImportProductsResult | null>((job) =>
    job && job.status === "committed" ? resultFromJob(job) : null,
  );

  const $busy = combine(
    uploadFx.pending,
    validateFx.pending,
    commitFx.pending,
    (upload, validate, commit) => upload || validate || commit,
  );

  // --- connections ------------------------------------------------------------------------------
  sample({
    clock: startRequested,
    source: $file,
    filter: (file: File | null): file is File => file !== null,
    target: uploadFx,
  });
  sample({ clock: uploadFx.doneData, fn: (created) => created.id, target: validateFx });

  sample({
    clock: [validateFx.doneData, commitFx.doneData],
    filter: (job) => job.error_rows > 0 || job.status === "failed",
    fn: (job) => ({ jobId: job.id, cursor: null }),
    target: errorsFx,
  });

  sample({
    clock: commitRequested,
    source: $job,
    filter: (job: ImportJobOut | null): job is ImportJobOut => job !== null && job.status === "validated",
    fn: (job) => job.id,
    target: commitFx,
  });

  sample({
    clock: moreErrorsRequested,
    source: { job: $job, cursor: $errorsCursor },
    filter: ({ job, cursor }) => job !== null && cursor !== null,
    fn: ({ job, cursor }) => ({ jobId: job?.id ?? "", cursor }),
    target: errorsFx,
  });

  sample({ clock: [restarted, disposed], target: cancelPollsFx });
  sample({ clock: templateRequested, target: templateFx });

  /** Fires once with the result when the commit finished (`onDone`). */
  const completed = sample({
    clock: commitFx.doneData,
    filter: (job) => job.status === "committed",
    fn: resultFromJob,
  });

  return {
    kind,
    // events
    fileSelected,
    fileRemoved,
    fileRejected,
    startRequested,
    commitRequested,
    moreErrorsRequested,
    restarted,
    templateRequested,
    disposed,
    completed,
    // stores
    $file,
    $phase,
    $processingStep,
    $job,
    $errorRows,
    $errorsCursor,
    $fileError,
    $flowError,
    $result,
    $busy,
    $errorsLoading: errorsFx.pending,
    $templateLoading: templateFx.pending,
    // effects (tests / advanced use)
    uploadFx,
    validateFx,
    commitFx,
    errorsFx,
    templateFx,
  };
}

export type ImportFlowModel = ReturnType<typeof createImportFlow>;

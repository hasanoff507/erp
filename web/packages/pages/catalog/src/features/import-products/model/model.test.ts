import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";
import type { ImportErrorPage, ImportJobOut } from "@shared/models";

import { createImportFlow } from "./factory/index.ts";
import { IMPORT_POLL_TIMEOUT, isSettled, resultFromJob } from "./lib/index.ts";
import type { ImportApi, ImportFlowDeps } from "./types/index.ts";

function job(patch: Partial<ImportJobOut>): ImportJobOut {
  return {
    id: "job-1",
    kind: "products",
    status: "uploaded",
    total_rows: 0,
    ok_rows: 0,
    error_rows: 0,
    result: {},
    created_at: "2026-10-17T08:00:00Z",
    ...patch,
  };
}

function apiError(status: number, code: string, messageKey: string): ApiError {
  return new ApiError({ status, code, messageKey });
}

/** Scripted fake of the generated inventory functions: GET returns the queued states in order. */
function fakeApi(states: ImportJobOut[], errors: ImportErrorPage[] = []) {
  const calls: string[] = [];
  const queue = [...states];
  const pages = [...errors];
  const api: ImportApi = {
    template: () => {
      calls.push("template");
      return Promise.resolve(new Blob(["name;unit_code\n"]));
    },
    createJob: (kind, file) => {
      calls.push(`create:${kind}:${file.name}`);
      return Promise.resolve({ id: "job-1", kind, status: "uploaded", total_rows: 0 });
    },
    validate: (id) => {
      calls.push(`validate:${id}`);
      return Promise.resolve({ job_id: id, status: "validating" });
    },
    getJob: (id) => {
      calls.push(`get:${id}`);
      const next = queue.length > 1 ? queue.shift() : queue[0];
      return next ? Promise.resolve(next) : Promise.reject(new Error("no state"));
    },
    listErrors: (id, cursor) => {
      calls.push(`errors:${id}:${cursor ?? ""}`);
      return Promise.resolve(pages.shift() ?? { items: [], next_cursor: null });
    },
    commit: (id) => {
      calls.push(`commit:${id}`);
      return Promise.resolve({ job_id: id, status: "committing" });
    },
  };
  return { api, calls };
}

function deps(api: ImportApi, extra: Partial<ImportFlowDeps> = {}): ImportFlowDeps {
  const saved: string[] = [];
  return {
    api,
    sleep: () => Promise.resolve(),
    saveFile: (_blob, name) => saved.push(name),
    pollIntervals: [0],
    ...extra,
  };
}

const file = new File(["name;unit_code;vat_rate\nNon;pcs;12.00\n"], "tovarlar.csv", { type: "text/csv" });

describe("product import flow (19 §6, US-M04-04)", () => {
  it("upload → validate (poll) → review with error rows → commit (poll) → done", async () => {
    const { api, calls } = fakeApi(
      [
        job({ status: "validating" }),
        job({ status: "validated", total_rows: 3, ok_rows: 2, error_rows: 1 }),
        job({ status: "committing", total_rows: 3, ok_rows: 2, error_rows: 1 }),
        job({
          status: "committed",
          total_rows: 3,
          ok_rows: 2,
          error_rows: 1,
          result: { created_product_count: 2, created_doc_ids: ["doc-1"] },
        }),
      ],
      [
        {
          items: [
            { row: 3, field: "barcode", code: "BARCODE_DUPLICATE", message: "validation.barcode_duplicate" },
          ],
          next_cursor: null,
        },
      ],
    );
    const model = createImportFlow(deps(api));
    const scope = fork();
    const done: unknown[] = [];
    model.completed.watch((r) => done.push(r));

    await allSettled(model.fileSelected, { scope, params: file });
    await allSettled(model.startRequested, { scope });

    expect(scope.getState(model.$phase)).toBe("review");
    expect(scope.getState(model.$job)?.ok_rows).toBe(2);
    expect(scope.getState(model.$errorRows)).toEqual([
      { row: 3, field: "barcode", code: "BARCODE_DUPLICATE", message: "validation.barcode_duplicate" },
    ]);
    expect(calls.slice(0, 4)).toEqual([
      "create:products:tovarlar.csv",
      "validate:job-1",
      "get:job-1",
      "get:job-1",
    ]);

    await allSettled(model.commitRequested, { scope });
    expect(scope.getState(model.$phase)).toBe("done");
    expect(scope.getState(model.$result)).toEqual({
      jobId: "job-1",
      totalRows: 3,
      createdProductCount: 2,
      skippedRows: 1,
      createdDocIds: ["doc-1"],
      lineCount: 0,
    });
    expect(calls).toContain("commit:job-1");
    expect(done).toHaveLength(1);
  });

  it("kind=opening_stock (BO-21 ③b): the job is created with that kind, the result carries line_count", async () => {
    const { api, calls } = fakeApi([
      job({ kind: "opening_stock", status: "validated", total_rows: 2, ok_rows: 2 }),
      job({
        kind: "opening_stock",
        status: "committed",
        total_rows: 2,
        ok_rows: 2,
        result: { created_doc_ids: ["so-1"], line_count: 2 },
      }),
    ]);
    const model = createImportFlow(deps(api), "opening_stock");
    const scope = fork();
    const stock = new File(["barcode;qty;unit_cost\n4780000000017;10;9800\n"], "qoldiq.csv");

    await allSettled(model.fileSelected, { scope, params: stock });
    await allSettled(model.startRequested, { scope });
    expect(calls[0]).toBe("create:opening_stock:qoldiq.csv");
    expect(scope.getState(model.$phase)).toBe("review");

    await allSettled(model.commitRequested, { scope });
    expect(scope.getState(model.$result)).toMatchObject({
      createdProductCount: 0,
      createdDocIds: ["so-1"],
      lineCount: 2,
      skippedRows: 0,
    });
    await allSettled(model.templateRequested, { scope });
    expect(calls).toContain("template");
  });

  it("all rows invalid → `invalid` phase, commit is not sent; restart returns to the file step", async () => {
    const { api, calls } = fakeApi(
      [job({ status: "failed", total_rows: 1, ok_rows: 0, error_rows: 1 })],
      [
        {
          items: [
            { row: 2, field: "unit_code", code: "VALIDATION_ERROR", message: "validation.unit_not_found" },
          ],
          next_cursor: null,
        },
      ],
    );
    const model = createImportFlow(deps(api));
    const scope = fork();

    await allSettled(model.fileSelected, { scope, params: file });
    await allSettled(model.startRequested, { scope });
    expect(scope.getState(model.$phase)).toBe("invalid");
    expect(scope.getState(model.$errorRows)).toHaveLength(1);

    await allSettled(model.commitRequested, { scope });
    expect(calls.some((c) => c.startsWith("commit"))).toBe(false);

    await allSettled(model.restarted, { scope });
    expect(scope.getState(model.$phase)).toBe("select");
    expect(scope.getState(model.$file)).toBeNull();
    expect(scope.getState(model.$errorRows)).toEqual([]);
  });

  it("FILE_TOO_LARGE / IMPORT_FILE_INVALID go to the dropzone, other errors to the banner", async () => {
    const { api } = fakeApi([job({})]);
    api.createJob = () => Promise.reject(apiError(413, "FILE_TOO_LARGE", "errors.file_too_large"));
    const model = createImportFlow(deps(api));
    const scope = fork();
    await allSettled(model.fileSelected, { scope, params: file });
    await allSettled(model.startRequested, { scope });
    expect(scope.getState(model.$phase)).toBe("select");
    expect(scope.getState(model.$fileError)).toBe("errors.file_too_large");
    expect(scope.getState(model.$flowError)).toBeNull();

    api.createJob = () => Promise.reject(apiError(403, "PERMISSION_DENIED", "errors.permission_denied"));
    await allSettled(model.startRequested, { scope });
    expect(scope.getState(model.$fileError)).toBeNull();
    expect(scope.getState(model.$flowError)?.code).toBe("PERMISSION_DENIED");
  });

  it("commit answered IMPORT_JOB_ALREADY_COMMITTED → shows the committed job (no second import)", async () => {
    const { api } = fakeApi([
      job({ status: "validated", total_rows: 1, ok_rows: 1 }),
      job({
        status: "committed",
        total_rows: 1,
        ok_rows: 1,
        result: { created_product_count: 1, created_doc_ids: [] },
      }),
    ]);
    api.commit = () =>
      Promise.reject(apiError(409, "IMPORT_JOB_ALREADY_COMMITTED", "errors.import_job_already_committed"));
    const model = createImportFlow(deps(api));
    const scope = fork();
    await allSettled(model.fileSelected, { scope, params: file });
    await allSettled(model.startRequested, { scope });
    await allSettled(model.commitRequested, { scope });
    expect(scope.getState(model.$phase)).toBe("done");
    expect(scope.getState(model.$result)?.createdProductCount).toBe(1);
  });

  it("commit refused with IMPORT_JOB_NOT_VALIDATED stays on review with a banner", async () => {
    const { api } = fakeApi([job({ status: "validated", total_rows: 1, ok_rows: 1 })]);
    api.commit = () =>
      Promise.reject(apiError(409, "IMPORT_JOB_NOT_VALIDATED", "errors.import_job_not_validated"));
    const model = createImportFlow(deps(api));
    const scope = fork();
    await allSettled(model.fileSelected, { scope, params: file });
    await allSettled(model.startRequested, { scope });
    await allSettled(model.commitRequested, { scope });
    expect(scope.getState(model.$phase)).toBe("review");
    expect(scope.getState(model.$flowError)?.messageKey).toBe("errors.import_job_not_validated");
  });

  it("polling gives up after the timeout with a client error", async () => {
    const { api } = fakeApi([job({ status: "validating" })]);
    let now = 0;
    const realNow = Date.now;
    Date.now = () => now;
    try {
      const model = createImportFlow(
        deps(api, {
          pollTimeoutMs: 1000,
          sleep: () => {
            now += 600;
            return Promise.resolve();
          },
        }),
      );
      const scope = fork();
      await allSettled(model.fileSelected, { scope, params: file });
      await allSettled(model.startRequested, { scope });
      expect(scope.getState(model.$flowError)?.code).toBe(IMPORT_POLL_TIMEOUT);
      expect(scope.getState(model.$phase)).toBe("select");
    } finally {
      Date.now = realNow;
    }
  });

  it("loads more error rows by cursor and downloads the template", async () => {
    const { api, calls } = fakeApi(
      [job({ status: "validated", total_rows: 4, ok_rows: 1, error_rows: 3 })],
      [
        {
          items: [{ row: 2, field: "name", code: "VALIDATION_ERROR", message: "validation.required" }],
          next_cursor: "c1",
        },
        {
          items: [
            {
              row: 3,
              field: "vat_rate",
              code: "VALIDATION_ERROR",
              message: "validation.vat_rate_not_allowed",
            },
            { row: 4, field: "mxik_code", code: "MXIK_CODE_INVALID", message: "validation.mxik_format" },
          ],
          next_cursor: null,
        },
      ],
    );
    const saved: string[] = [];
    const model = createImportFlow(deps(api, { saveFile: (_b, name) => saved.push(name) }));
    const scope = fork();
    await allSettled(model.templateRequested, { scope });
    expect(saved).toEqual(["products.csv"]);

    await allSettled(model.fileSelected, { scope, params: file });
    await allSettled(model.startRequested, { scope });
    expect(scope.getState(model.$errorsCursor)).toBe("c1");
    await allSettled(model.moreErrorsRequested, { scope });
    expect(scope.getState(model.$errorRows).map((r) => r.row)).toEqual([2, 3, 4]);
    expect(scope.getState(model.$errorsCursor)).toBeNull();
    expect(calls).toContain("errors:job-1:c1");
  });
});

describe("import lib", () => {
  it("settled states per stage and result mapping", () => {
    expect(isSettled("validate", "validating")).toBe(false);
    expect(isSettled("validate", "validated")).toBe(true);
    expect(isSettled("commit", "validated")).toBe(false);
    expect(isSettled("commit", "committed")).toBe(true);
    expect(
      resultFromJob(job({ status: "committed", result: { created_product_count: "x" } })).createdProductCount,
    ).toBe(0);
  });
});

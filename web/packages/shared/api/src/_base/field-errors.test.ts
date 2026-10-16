import { http as mswHttp, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  apiFieldErrors,
  apiRequest,
  applyApiFieldErrors,
  http,
  resetCsrfToken,
  toFieldPath,
} from "../index.ts";

const BASE = "http://api.test";

function validationError(details: { field: string; messageKey: string }[]): ApiError {
  return new ApiError({ status: 422, code: "VALIDATION_ERROR", messageKey: "errors.validation", details });
}

describe("details[] → form field errors (17 §7.1)", () => {
  it("normalises server paths to dot notation", () => {
    expect(toFieldPath("payments[0].amount")).toBe("payments.0.amount");
    expect(toFieldPath("body.name")).toBe("name");
    expect(toFieldPath("phone")).toBe("phone");
    expect(
      apiFieldErrors(validationError([{ field: "items[2].qty", messageKey: "validation.required" }])),
    ).toEqual([{ path: "items.2.qty", messageKey: "validation.required" }]);
  });

  it("sets known fields (first focused), returns the rest, honours fieldMap", () => {
    const setError = vi.fn();
    const error = validationError([
      { field: "name", messageKey: "validation.required" },
      { field: "branch_ids", messageKey: "validation.required" },
      { field: "Idempotency-Key", messageKey: "validation.required" },
    ]);
    const result = applyApiFieldErrors(error, setError, ["name", "branches"] as const, {
      branch_ids: "branches",
    });
    expect(setError).toHaveBeenNthCalledWith(
      1,
      "name",
      { type: "server", message: "validation.required" },
      { shouldFocus: true },
    );
    expect(setError).toHaveBeenNthCalledWith(
      2,
      "branches",
      { type: "server", message: "validation.required" },
      { shouldFocus: false },
    );
    expect(result).toEqual({
      applied: true,
      unmatched: [{ path: "Idempotency-Key", messageKey: "validation.required" }],
    });
  });

  it("an error without details applies nothing", () => {
    const setError = vi.fn();
    const result = applyApiFieldErrors(
      new ApiError({ status: 409, code: "VERSION_CONFLICT", messageKey: "errors.version_conflict" }),
      setError,
      ["name"],
    );
    expect(result).toEqual({ applied: false, unmatched: [] });
    expect(setError).not.toHaveBeenCalled();
  });
});

describe("multipart upload through the orval mutator (17 §12)", () => {
  const received: {
    contentType: string | null;
    fileName: string | null;
    fileText: string | null;
    kind: string | null;
    headers: Headers | null;
  } = {
    contentType: null,
    fileName: null,
    fileText: null,
    kind: null,
    headers: null,
  };
  const server = setupServer(
    mswHttp.get(`${BASE}/api/v1/auth/csrf`, () => HttpResponse.json({ csrf_token: "csrf-test-token" })),
    mswHttp.post(`${BASE}/api/v1/attachments`, async ({ request }) => {
      received.contentType = request.headers.get("content-type");
      received.headers = request.headers;
      const form = await request.formData();
      const file = form.get("file");
      received.fileName = file instanceof File ? file.name : null;
      received.fileText = file instanceof File ? await file.text() : null;
      received.kind = typeof form.get("kind") === "string" ? (form.get("kind") as string) : null;
      return HttpResponse.json(
        { id: "att-1", url: "https://s3/x", content_type: "text/csv", size_bytes: 9 },
        { status: 201 },
      );
    }),
  );

  beforeAll(() => {
    http.defaults.baseURL = BASE;
    server.listen({ onUnhandledFrame: "error" });
  });
  afterEach(() => resetCsrfToken());
  afterAll(() => server.close());

  // orval generates: `headers: {'Content-Type': 'multipart/form-data'}, data: formData`.
  it.each([
    ["with the orval multipart header", { "Content-Type": "multipart/form-data" }],
    ["without any Content-Type", {}],
  ])("passes FormData untouched — %s", async (_label, headers) => {
    const formData = new FormData();
    formData.append("file", new File(["sku;name\n"], "Tovarlar.csv", { type: "text/csv" }));
    formData.append("kind", "import");
    const body = await apiRequest<{ id: string }>({
      url: "/api/v1/attachments",
      method: "POST",
      headers,
      data: formData,
    });
    expect(body.id).toBe("att-1");
    expect(received.contentType).toMatch(/^multipart\/form-data; ?boundary=/);
    expect(received.fileName).toBe("Tovarlar.csv");
    expect(received.fileText).toBe("sku;name\n");
    expect(received.kind).toBe("import");
    // Writes still carry CSRF + Idempotency-Key (17 §6).
    expect(received.headers?.get("x-csrf-token")).toBe("csrf-test-token");
    expect(received.headers?.get("idempotency-key")).toMatch(/^[0-9a-f-]{36}$/);
  });
});

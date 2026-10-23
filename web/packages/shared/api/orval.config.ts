/**
 * orval — 24-frontend-arxitekturasi.md §3, 32-kod-qoidalari.md §2.4 / §9.
 * FastAPI /openapi.json → axios functions (tags-split) in @shared/api/generated and
 * types in @shared/models/generated. Never edit generated files: fix the Pydantic schema instead.
 */
import { defineConfig } from "orval";

/** `debts_list_debtors` (tag `debts`) → `listDebtors`. */
function operationName(operationId: string, tag: string | undefined): string {
  const prefix = tag ? `${tag.replace(/-/g, "_")}_` : "";
  const bare = prefix && operationId.startsWith(prefix) ? operationId.slice(prefix.length) : operationId;
  return bare.replace(/_([a-z0-9])/g, (_m: string, ch: string) => ch.toUpperCase());
}

export default defineConfig({
  erp: {
    input: {
      target: "./openapi.json",
    },
    output: {
      mode: "tags-split",
      client: "axios-functions",
      target: "./src/generated",
      schemas: "../models/src/generated",
      clean: true,
      override: {
        mutator: {
          path: "./src/_base/instance.ts",
          name: "apiRequest",
        },
        operationName: (operation) => operationName(String(operation.operationId ?? ""), operation.tags?.[0]),
      },
    },
  },
});

/** Production wiring of the import flow: generated `inventory` functions (19 §6) + browser download. */
import { api } from "@shared/api";

import { ERRORS_PAGE_SIZE } from "../factory/index.ts";
import type { ImportFlowDeps } from "../types/index.ts";

/** Saves a Blob through a temporary object URL (CSP-safe: no inline script, a plain navigation). */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export const importFlowDeps: ImportFlowDeps = {
  api: {
    template: async (kind) => {
      const data = await api.inventory.getImportTemplate(kind, { responseType: "blob" });
      if (data instanceof Blob) return data;
      return new Blob([typeof data === "string" ? data : ""], { type: "text/csv;charset=utf-8" });
    },
    createJob: (kind, file) => api.inventory.createImportJob({ kind, file }),
    validate: (jobId) => api.inventory.validateImportJob(jobId, {}),
    getJob: (jobId) => api.inventory.getImportJob(jobId),
    listErrors: (jobId, cursor) =>
      api.inventory.listImportJobErrors(jobId, { cursor, limit: ERRORS_PAGE_SIZE }),
    commit: (jobId) => api.inventory.commitImportJob(jobId, { skip_error_rows: true }),
  },
  sleep: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  saveFile: saveBlob,
};

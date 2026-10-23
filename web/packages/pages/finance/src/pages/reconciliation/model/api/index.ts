/** BO-10 follows the canonical state-report contract in 20 #3–#8. Keep DTOs local until backend OpenAPI exposes it. */
import { apiRequest } from "@shared/api";

import type {
  CompareResult,
  StateReport,
  StateReportDiffPage,
  StateReportPage,
  TaxType,
} from "../types/index.ts";

export async function listStateReports(params: { tax_type: TaxType; period?: string; cursor?: string }) {
  return apiRequest<StateReportPage>({ url: "/api/v1/state-reports", method: "GET", params });
}

export async function getStateReport(id: string) {
  return apiRequest<StateReport>({ url: `/api/v1/state-reports/${id}`, method: "GET" });
}

export async function listStateReportDiffs(id: string) {
  return apiRequest<StateReportDiffPage>({ url: `/api/v1/state-reports/${id}/diffs`, method: "GET" });
}

export async function uploadStateReport(input: {
  file: File;
  taxType: TaxType;
  period: string;
  publishedAt: string;
}) {
  const body = new FormData();
  body.append("file", input.file);
  body.append("tax_type", input.taxType);
  body.append("period", input.period);
  body.append("published_at", input.publishedAt);
  const uploaded = await apiRequest<{ id: string }>({
    url: "/api/v1/state-reports",
    method: "POST",
    headers: { "Content-Type": "multipart/form-data" },
    data: body,
  });
  return apiRequest<CompareResult>({
    url: `/api/v1/state-reports/${uploaded.id}/compare`,
    method: "POST",
  });
}

export async function compareStateReport(id: string) {
  return apiRequest<CompareResult>({ url: `/api/v1/state-reports/${id}/compare`, method: "POST" });
}

export async function recordCorrection(id: string, body: { comment: string; portal_ref?: string }) {
  return apiRequest<{ id: string; status: "correction_sent"; correction_sent_at: string }>({
    url: `/api/v1/state-reports/${id}/correction`,
    method: "POST",
    data: body,
  });
}

export async function confirmStateReport(id: string, body: { comment?: string }) {
  return apiRequest<{ id: string; status: "confirmed"; confirmed_at: string }>({
    url: `/api/v1/state-reports/${id}/confirm`,
    method: "POST",
    data: body,
  });
}

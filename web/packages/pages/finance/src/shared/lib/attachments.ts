/**
 * 17 §12 attachments: `POST /attachments` (multipart `kind` + `file`, Idempotency-Key by the shared client)
 * → `{id, url, content_type, size_bytes}`; `url` is a same-origin signed link (15 min) usable in `<img src>`
 * under the strict CSP (`img-src 'self'` — no blob: previews before the upload).
 */
import { api } from "@shared/api";
import type { AttachmentCreated } from "@shared/models";

import { apiFx } from "./effect.ts";

export type AttachmentKind = "expense_receipt" | "import";
export type Attachment = AttachmentCreated & { name: string };

const MB = 1024 * 1024;

/** Accepted file extensions and limits per kind (17 §12; BO-17 receipt photo, BO-24 statement file). */
export const ATTACHMENT_RULES: Record<AttachmentKind, { accept: readonly string[]; maxBytes: number }> = {
  expense_receipt: { accept: [".jpg", ".jpeg", ".png", ".pdf"], maxBytes: 10 * MB },
  import: { accept: [".pdf", ".xlsx", ".csv", ".txt", ".jpg", ".jpeg", ".png"], maxBytes: 10 * MB },
};

/** 1CClientBankExchange statement for `POST /bank-settlements/imports` (20 #55g). */
export const STATEMENT_RULE = { accept: [".txt"], maxBytes: 10 * MB } as const;

export const uploadAttachmentFx = apiFx<{ kind: AttachmentKind; file: File }, Attachment>(
  async ({ kind, file }) => ({ ...(await api.attachments.upload({ kind, file })), name: file.name }),
);

export function isImage(contentType: string): boolean {
  return contentType === "image/jpeg" || contentType === "image/png";
}

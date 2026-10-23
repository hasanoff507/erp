/**
 * File upload field (17 §12): the picked file goes to `POST /attachments` at once; the field then holds the
 * attachment id. Preview = the same-origin signed `url` (strict CSP: `img-src 'self'`, no blob: URLs) — an
 * image thumbnail or a link for PDF/other files. Upload errors (413/415) are shown under the zone.
 */
import { useUnit } from "effector-react";
import { FileText, Paperclip, X } from "lucide-react";
import { useState } from "react";

import { toApiError } from "@shared/api";
import { serverErrorText, useTranslation } from "@shared/i18n";
import { Button, FileDropzone, Icon } from "@shared/ui";

import {
  ATTACHMENT_RULES,
  isImage,
  uploadAttachmentFx,
  type Attachment,
  type AttachmentKind,
} from "../lib/attachments.ts";

export interface AttachmentFieldProps {
  kind: AttachmentKind;
  value: Attachment | null;
  onChange: (value: Attachment | null) => void;
  disabled?: boolean;
  title?: string;
  id?: string;
}

export function AttachmentField({ kind, value, onChange, disabled, title, id }: AttachmentFieldProps) {
  const { t } = useTranslation("finance");
  const uploadFile = useUnit(uploadAttachmentFx);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rule = ATTACHMENT_RULES[kind];

  const upload = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      onChange(await uploadFile({ kind, file }));
    } catch (e) {
      setError(serverErrorText(toApiError(e)));
    } finally {
      setBusy(false);
    }
  };

  if (value) {
    return (
      <div
        data-testid="attachment-chip"
        className="flex items-center gap-3 rounded-xl border border-border bg-background p-2.5"
      >
        {isImage(value.content_type) ? (
          <img src={value.url} alt={value.name} className="h-12 w-12 rounded-lg object-cover" />
        ) : (
          <span className="grid h-12 w-12 place-items-center rounded-lg bg-accent">
            <Icon as={FileText} size="md" />
          </span>
        )}
        <a
          href={value.url}
          target="_blank"
          rel="noopener noreferrer"
          className="min-w-0 flex-1 truncate text-[13px] font-semibold"
        >
          {value.name}
        </a>
        <Button
          variant="ghost"
          size="icon"
          aria-label={t("shared.removeFile")}
          disabled={disabled}
          onClick={() => onChange(null)}
        >
          <Icon as={X} size="sm" />
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <FileDropzone
        id={id}
        accept={rule.accept}
        maxSize={rule.maxBytes}
        disabled={disabled || busy}
        title={title}
        error={error}
        onFile={(file) => void upload(file)}
      />
      {busy ? (
        <p className="flex items-center gap-1.5 text-[12px] text-foreground-secondary" aria-live="polite">
          <Icon as={Paperclip} size="sm" />
          {t("shared.uploading")}
        </p>
      ) : null}
    </div>
  );
}

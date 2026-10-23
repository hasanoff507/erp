/**
 * FileDropzone — Excel/CSV import upload (US-M04-04, 17 §12: xlsx/csv ≤ 10 MB). Drag & drop or the
 * "Fayl tanlash" button (keyboard: Tab + Enter/Space opens the picker). Type and size are checked
 * client-side before `onFile`; a rejected file shows a translated error and calls `onReject`.
 * The server re-checks (`413 FILE_TOO_LARGE`, `415 UNSUPPORTED_FILE_TYPE`) — pass that as `error`.
 */
import { FileSpreadsheet, Upload, X } from "lucide-react";
import { useId, useRef, useState, type DragEvent } from "react";

import { useTranslation } from "@shared/i18n";
import { fileMatchesAccept, formatFileSize, UPLOAD_LIMITS } from "@shared/lib/file";

import { Button } from "#/components/ui/button.tsx";
import { Icon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";

import { translateFieldError, withParams } from "./form-field.tsx";

export type FileRejectReason = "too_large" | "wrong_type";

export interface FileDropzoneProps {
  /** Extensions / MIME types, e.g. [".xlsx", ".csv"] (default). */
  accept?: readonly string[];
  /** Bytes (default 10 MB — 17 §12). */
  maxSize?: number;
  /** Currently selected file (controlled); shows a file chip with a remove button. */
  file?: File | null;
  onFile: (file: File) => void;
  onRemove?: () => void;
  onReject?: (reason: FileRejectReason, file: File) => void;
  disabled?: boolean;
  /** Heading inside the zone (default "Faylni shu yerga tashlang"). */
  title?: string;
  /** External (server) error: i18n key or text. */
  error?: string | null;
  id?: string;
  className?: string;
}

export function FileDropzone({
  accept = [".xlsx", ".csv"],
  maxSize = UPLOAD_LIMITS.spreadsheet,
  file = null,
  onFile,
  onRemove,
  onReject,
  disabled = false,
  title,
  error,
  id,
  className,
}: FileDropzoneProps) {
  const { t } = useTranslation("common");
  const generated = useId();
  const inputId = id ?? `dz${generated}`;
  const input = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const units = { b: t("ui.fileSize.b"), kb: t("ui.fileSize.kb"), mb: t("ui.fileSize.mb") };
  const typesLabel = accept.map((a) => (a.startsWith(".") ? a.slice(1).toUpperCase() : a)).join(", ");
  const sizeLabel = formatFileSize(maxSize, units);

  const take = (candidate: File | undefined) => {
    if (!candidate || disabled) return;
    if (!fileMatchesAccept(candidate, accept)) {
      setLocalError(withParams("validation.file_type", { types: typesLabel }));
      onReject?.("wrong_type", candidate);
      return;
    }
    if (candidate.size > maxSize) {
      setLocalError(withParams("validation.file_too_large", { max: sizeLabel }));
      onReject?.("too_large", candidate);
      return;
    }
    setLocalError(null);
    onFile(candidate);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    take(event.dataTransfer.files[0]);
  };

  const errorText = translateFieldError(localError ?? error);
  const errorId = errorText ? `${inputId}-error` : undefined;
  const hintId = `${inputId}-hint`;

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        data-dragging={dragging || undefined}
        className={cn(
          "flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-input bg-muted px-6 py-8 text-center transition-colors",
          dragging && "border-primary bg-primary-soft",
          errorText && "border-destructive-border",
          disabled && "opacity-60",
        )}
      >
        <span className="flex h-11 w-11 items-center justify-center rounded-md bg-primary-soft text-primary-strong">
          <Icon as={Upload} size="lg" />
        </span>
        <p className="text-[15px] font-bold text-foreground">{title ?? t("ui.dropzone.title")}</p>
        <p id={hintId} className="text-small text-foreground-secondary">
          {t("ui.dropzone.hint", { types: typesLabel, size: sizeLabel })}
        </p>
        <input
          ref={input}
          id={inputId}
          type="file"
          className="sr-only"
          tabIndex={-1}
          accept={accept.join(",")}
          disabled={disabled}
          aria-describedby={[errorId, hintId].filter(Boolean).join(" ")}
          onChange={(e) => {
            take(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <Button
          variant="secondary"
          size="sm"
          disabled={disabled}
          aria-describedby={[errorId, hintId].filter(Boolean).join(" ")}
          onClick={() => input.current?.click()}
        >
          {t("ui.dropzone.browse")}
        </Button>
      </div>

      {file ? (
        <div
          className="flex items-center gap-3 rounded-lg border border-border bg-card px-3.5 py-2.5"
          aria-label={t("ui.dropzone.selected")}
          role="group"
        >
          <Icon as={FileSpreadsheet} size="md" className="shrink-0 text-primary" />
          <span className="min-w-0 flex-1 truncate text-[14px] font-semibold">{file.name}</span>
          <span className="text-small tabular-nums text-muted-foreground">
            {formatFileSize(file.size, units)}
          </span>
          {onRemove ? (
            <button
              type="button"
              aria-label={t("ui.dropzone.remove")}
              onClick={onRemove}
              disabled={disabled}
              className="flex h-9 w-9 items-center justify-center rounded-md text-foreground-secondary hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Icon as={X} size="sm" />
            </button>
          ) : null}
        </div>
      ) : null}

      {errorText ? (
        <p id={errorId} role="alert" className="text-small font-semibold text-destructive">
          {errorText}
        </p>
      ) : null}
    </div>
  );
}

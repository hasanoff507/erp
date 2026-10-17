/**
 * «Ko'chirmani yuklash» (20 #55g): a 1CClientBankExchange `.txt` (+ the branch when the file cannot tell)
 * → `POST /bank-settlements/imports`; the parser only proposes DRAFTS. Errors: «Fayl 1CClientBankExchange
 * formatida emas» (BANK_IMPORT_FILE_INVALID, line no.), account mismatch, duplicate file, 413 / 415.
 */
import { useUnit } from "effector-react";
import { useState } from "react";

import { toApiError } from "@shared/api";
import { serverErrorText, useTranslation } from "@shared/i18n";
import { $branches } from "@shared/state/session";
import { ConfirmDialog, FileDropzone, FormField, SimpleSelect } from "@shared/ui";

import { STATEMENT_RULE } from "#/shared/lib/attachments.ts";

import { importStatementFx } from "../../model/index.ts";

const AUTO = "auto";

export function ImportDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return open ? <ImportForm onOpenChange={onOpenChange} /> : null;
}

function ImportForm({ onOpenChange }: { onOpenChange: (open: boolean) => void }) {
  const { t } = useTranslation("finance");
  const [branches, run] = useUnit([$branches, importStatementFx]);
  const [file, setFile] = useState<File | null>(null);
  const [branchId, setBranchId] = useState(AUTO);
  const [error, setError] = useState<string | null>(null);

  const confirm = async () => {
    if (!file) {
      setError(t("bank.import.fileRequired"));
      throw new Error("file required");
    }
    setError(null);
    try {
      await run({ file, branchId: branchId === AUTO ? null : branchId });
    } catch (e) {
      const apiError = toApiError(e);
      const line = apiError.params.line_no;
      setError(
        apiError.code === "BANK_IMPORT_FILE_INVALID"
          ? t("bank.import.invalidFile", {
              line: typeof line === "number" || typeof line === "string" ? line : "—",
            })
          : serverErrorText(apiError),
      );
      throw e;
    }
  };

  return (
    <ConfirmDialog
      open
      onOpenChange={onOpenChange}
      title={t("bank.import.title")}
      description={t("bank.import.description")}
      confirmLabel={t("bank.import.submit")}
      cancelLabel={t("shared.back")}
      onConfirm={confirm}
      error={error}
    >
      <div className="flex flex-col gap-3">
        <FileDropzone
          accept={STATEMENT_RULE.accept}
          maxSize={STATEMENT_RULE.maxBytes}
          file={file}
          title={t("bank.import.drop")}
          onFile={(f) => {
            setFile(f);
            setError(null);
          }}
          onRemove={() => setFile(null)}
        />
        {branches.length > 1 ? (
          <FormField label={t("bank.import.branch")} hint={t("bank.import.branchHint")}>
            <SimpleSelect
              options={[
                { value: AUTO, label: t("bank.import.branchAuto") },
                ...branches.map((b) => ({ value: b.id, label: b.name })),
              ]}
              value={branchId}
              onValueChange={setBranchId}
            />
          </FormField>
        ) : null}
      </div>
    </ConfirmDialog>
  );
}

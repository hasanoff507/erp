import { useUnit } from "effector-react";
import { CircleCheck, Hourglass, RefreshCw, TriangleAlert } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { useCan } from "@shared/state/permissions";
import { Button, Card, Icon } from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";

import { $recostSummary, $recostSummaryError, recostSummaryOpened } from "../model/index.ts";

const JOURNAL_PATH = "/app/accounting/journal";

/**
 * «Qayta hisoblash navbati» holat qatori (07 BO-14, qaror #56c): how many recost jobs are open / failed,
 * with a link to the queue in BO-08 (shown when the user may open the journal — `accounting.post`).
 */
export function RecostStatusLine() {
  const { t } = useTranslation("settings");
  const canView = useCan({ permission: "stock.view" });
  const canOpenJournal = useCan({ permission: "accounting.post" });
  const [summary, error, opened] = useUnit([$recostSummary, $recostSummaryError, recostSummaryOpened]);

  useEffect(() => {
    if (canView) opened();
  }, [opened, canView]);

  if (!canView) return null;

  const count = (n: number) => (summary?.more ? `${n}+` : String(n));
  let icon = Hourglass;
  let tone = "text-foreground-secondary";
  let text = t("tenant.recostLine.loading");
  if (error) {
    icon = TriangleAlert;
    tone = "text-destructive-strong";
    text = errorText(error);
  } else if (summary && summary.failed > 0) {
    icon = TriangleAlert;
    tone = "text-destructive-strong";
    text = t("tenant.recostLine.failed", { count: count(summary.failed) });
  } else if (summary && summary.pending > 0) {
    icon = RefreshCw;
    tone = "text-info-strong";
    text = t("tenant.recostLine.pending", { count: count(summary.pending) });
  } else if (summary) {
    icon = CircleCheck;
    tone = "text-success-strong";
    text = t("tenant.recostLine.clear");
  }

  return (
    <Card role="region" className="flex flex-wrap items-center gap-3" aria-labelledby="recost-line-title">
      <Icon as={icon} size="lg" className={tone} />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <h3 id="recost-line-title" className="text-[15px] font-bold">
          {t("tenant.recostLine.title")}
        </h3>
        <p className={`text-small ${tone}`} role="status">
          {text}
        </p>
      </div>
      {canOpenJournal ? (
        <Button asChild size="sm" variant="secondary">
          <Link to={JOURNAL_PATH}>{t("tenant.recostLine.open")}</Link>
        </Button>
      ) : null}
    </Card>
  );
}

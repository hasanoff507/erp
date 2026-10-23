import { fork } from "effector";
import { Provider } from "effector-react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";

import { initI18n } from "@shared/i18n";

import { $recostJobs, $recostStatus, type RecostJob } from "../../model/index.ts";
import { RecostQueue } from "./RecostQueue.tsx";

const failed: RecostJob = {
  id: "j-1",
  warehouse_id: "w-1",
  product_id: "p-1",
  from_date: "2026-09-28",
  status: "failed",
  reason_doc_type: "goods_receipts",
  reason_doc_id: "gr-1",
  attempts: 3,
  last_error: "KeyError: x",
  created_at: "2026-10-01T05:00:00Z",
  finished_at: null,
};

beforeAll(async () => {
  await initI18n("uz").changeLanguage("uz");
});

describe("RecostQueue — raw last_error is never shown (08 §11)", () => {
  it("a failed job shows the generic text, not the backend exception (neither as text nor title)", () => {
    const scope = fork({
      values: [
        [$recostJobs, [failed]],
        [$recostStatus, "idle"],
      ],
    });
    const html = renderToStaticMarkup(
      <Provider value={scope}>
        <RecostQueue canRetry online />
      </Provider>,
    );
    expect(html).toContain("Hisoblashda xato — qayta urinib ko&#x27;ring");
    expect(html).not.toContain("KeyError");
  });
});

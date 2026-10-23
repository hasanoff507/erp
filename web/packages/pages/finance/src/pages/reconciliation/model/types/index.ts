export type TaxType = "vat" | "turnover";
export type ReportStatus =
  | "uploaded"
  | "compared"
  | "match"
  | "diff_found"
  | "correction_sent"
  | "confirmed"
  | "auto_accepted";

export interface StateReportRow {
  id: string;
  tax_type: TaxType;
  period: string;
  status: ReportStatus;
  deadline_at: string;
  diff_amount: string | null;
}

export interface StateReport extends StateReportRow {
  published_at: string;
  state_amount: string | null;
  our_amount: string | null;
  file_url: string | null;
  correction_sent_at: string | null;
  correction_comment: string | null;
  correction_portal_ref: string | null;
  confirmed_at: string | null;
  confirmed_by: string | null;
}

export interface StateReportDiff {
  id: string;
  indicator: string;
  state_value: string | null;
  our_value: string | null;
  diff: string | null;
  explanation: string | null;
  resolved: boolean;
}

export interface StateReportPage {
  items: StateReportRow[];
  next_cursor: string | null;
}

export interface StateReportDiffPage {
  items: StateReportDiff[];
  next_cursor: string | null;
}

export interface CompareResult {
  id: string;
  status: "match" | "diff_found" | "compared";
  diff_count: number;
  state_amount: string | null;
  our_amount: string | null;
  diff_amount: string | null;
  tolerance_amount: string;
}

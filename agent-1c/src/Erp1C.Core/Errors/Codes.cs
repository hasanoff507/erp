namespace Erp1C.Core.Errors
{
    /// <summary>Agent-channel codes used by the store agent (33 §12 / 17 §15 — only codes that exist in the catalog).</summary>
    public static class AgentCodes
    {
        public const string TaskRejected = "ONEC_TASK_REJECTED";
        public const string WorkerCrashed = "ONEC_WORKER_CRASHED";
        public const string Timeout = "ONEC_TIMEOUT";
        public const string UnknownOutcome = "ONEC_UNKNOWN_OUTCOME";
        public const string DpapiFailed = "ONEC_DPAPI_FAILED";
        public const string AgentRevoked = "ONEC_AGENT_REVOKED";
        public const string UpdateRequired = "ONEC_AGENT_UPDATE_REQUIRED";
        public const string LeaseLost = "ONEC_TASK_LEASE_LOST";
        public const string SubscriptionRestricted = "SUBSCRIPTION_RESTRICTED";
        public const string NotFound = "NOT_FOUND";
        public const string ValidationError = "VALIDATION_ERROR";
        public const string FileTooLarge = "FILE_TOO_LARGE";
        public const string RateLimited = "RATE_LIMITED";
        public const string Unauthorized = "UNAUTHORIZED";
    }

    /// <summary>Task rejection reasons (33 §9.11, 34 §7.5) — the A-05 <c>error.message</c>.</summary>
    public static class RejectReasons
    {
        public const string Signature = "signature";
        public const string Agent = "agent";
        public const string Tenant = "tenant";
        public const string Base = "base";
        public const string Expired = "expired";
        public const string PayloadHash = "payload_hash";
        public const string Kind = "kind";
        public const string Schema = "schema";
    }

    /// <summary>Local API (21 §16.1) codes — every one exists in 17 §15.</summary>
    public static class LocalCodes
    {
        public const string Unauthorized = "UNAUTHORIZED";
        public const string PermissionDenied = "PERMISSION_DENIED";
        public const string ValidationError = "VALIDATION_ERROR";
        public const string NotFound = "NOT_FOUND";
        public const string FileTooLarge = "FILE_TOO_LARGE";
        public const string RateLimited = "RATE_LIMITED";
        public const string InternalError = "INTERNAL_ERROR";
        public const string OtpInvalid = "OTP_INVALID";
        public const string OtpExpired = "OTP_EXPIRED";
        public const string OtpMaxAttempts = "OTP_MAX_ATTEMPTS";

        public const string ShiftNotOpen = "SHIFT_NOT_OPEN";
        public const string ShiftAlreadyOpen = "SHIFT_ALREADY_OPEN";
        public const string ReceiptSeqConflict = "RECEIPT_SEQ_CONFLICT";
        public const string FiscalDeviceLocked = "FISCAL_DEVICE_LOCKED";
        public const string FiscalOffline48hBlocked = "FISCAL_OFFLINE_48H_BLOCKED";
        public const string FiscalProviderError = "FISCAL_PROVIDER_ERROR";
        public const string AgentCapabilityDisabled = "AGENT_CAPABILITY_DISABLED";

        public const string CardTerminalUnreachable = "CARD_TERMINAL_UNREACHABLE";
        public const string CardTerminalBusy = "CARD_TERMINAL_BUSY";
        public const string CardTerminalTimeout = "CARD_TERMINAL_TIMEOUT";
        public const string CardOutcomeUnknown = "CARD_OUTCOME_UNKNOWN";
        public const string CardAmountMismatch = "CARD_AMOUNT_MISMATCH";
        public const string CardVoidFailed = "CARD_VOID_FAILED";

        public const string PrinterUnreachable = "PRINTER_UNREACHABLE";

        private static readonly System.Collections.Generic.Dictionary<string, (int Status, string MessageKey)> Catalog =
            new System.Collections.Generic.Dictionary<string, (int, string)>(System.StringComparer.Ordinal)
            {
                [Unauthorized] = (401, "errors.unauthorized"),
                [PermissionDenied] = (403, "errors.permission_denied"),
                [ValidationError] = (422, "errors.validation"),
                [NotFound] = (404, "errors.not_found"),
                [FileTooLarge] = (413, "errors.file_too_large"),
                [RateLimited] = (429, "errors.rate_limited"),
                [InternalError] = (500, "errors.internal_error"),
                [OtpInvalid] = (400, "errors.otp_invalid"),
                [OtpExpired] = (400, "errors.otp_expired"),
                [OtpMaxAttempts] = (429, "errors.otp_max_attempts"),
                [ShiftNotOpen] = (409, "errors.shift_not_open"),
                [ShiftAlreadyOpen] = (409, "errors.shift_already_open"),
                [ReceiptSeqConflict] = (409, "errors.receipt_seq_conflict"),
                [FiscalDeviceLocked] = (409, "errors.fiscal_device_locked"),
                [FiscalOffline48hBlocked] = (409, "errors.fiscal_offline_48h_blocked"),
                [FiscalProviderError] = (502, "errors.fiscal_provider_error"),
                [AgentCapabilityDisabled] = (409, "errors.agent_capability_disabled"),
                [CardTerminalUnreachable] = (503, "errors.card_terminal_unreachable"),
                [CardTerminalBusy] = (409, "errors.card_terminal_busy"),
                [CardTerminalTimeout] = (504, "errors.card_terminal_timeout"),
                [CardOutcomeUnknown] = (409, "errors.card_outcome_unknown"),
                [CardAmountMismatch] = (422, "errors.card_amount_mismatch"),
                [CardVoidFailed] = (502, "errors.card_void_failed"),
                [PrinterUnreachable] = (503, "errors.printer_unreachable"),
            };

        /// <summary>HTTP status of a catalog code (17 §15); unknown codes map to 500.</summary>
        public static int Status(string code) => Catalog.TryGetValue(code, out var v) ? v.Status : 500;

        /// <summary>i18n message key of a catalog code (17 §15).</summary>
        public static string MessageKey(string code) => Catalog.TryGetValue(code, out var v) ? v.MessageKey : "errors.internal_error";

        public static bool IsKnown(string code) => Catalog.ContainsKey(code);
    }
}

using System;
using System.Collections.Generic;

#pragma warning disable CA2227
#pragma warning disable CA1002

namespace Erp1C.CardTerminal
{
    // CardTerminalPort DTOs — 21 §9.4 / §16.1 field names (snake_case through AgentJson). Money = tiyin int64.

    /// <summary>21 §9.4 CardTxResult.</summary>
    public sealed class CardTxResult
    {
        public string AttemptId { get; set; } = string.Empty;

        /// <summary>purchase | refund | void.</summary>
        public string Kind { get; set; } = CardKinds.Purchase;

        /// <summary>approved | declined | cancelled | timeout | unknown | error.</summary>
        public string Status { get; set; } = CardStatuses.Unknown;

        public long? AmountTiyin { get; set; }

        public string? ApprovalCode { get; set; }

        public string? Rrn { get; set; }

        public string? Stan { get; set; }

        /// <summary>Normalised <c>^[0-9]{4}\*+[0-9]{4}$</c>; never a full PAN.</summary>
        public string? CardMask { get; set; }

        public string? CardScheme { get; set; }

        public string? CardType { get; set; }

        public string? EntryMode { get; set; }

        public string? Tid { get; set; }

        public string? Mid { get; set; }

        public string? Acquirer { get; set; }

        public string? TxAt { get; set; }

        public string? DeclineCode { get; set; }

        public string? DeclineMessage { get; set; }

        public string? SlipText { get; set; }

        public CardTxResult Clone() => (CardTxResult)MemberwiseClone();
    }

    public static class CardKinds
    {
        public const string Purchase = "purchase";
        public const string Refund = "refund";
        public const string Void = "void";
    }

    public static class CardStatuses
    {
        public const string Approved = "approved";
        public const string Declined = "declined";
        public const string Cancelled = "cancelled";
        public const string Timeout = "timeout";
        public const string Unknown = "unknown";
        public const string Error = "error";

        public static bool IsFinal(string status) => status == Approved || status == Declined || status == Cancelled || status == Error;
    }

    /// <summary>Configured terminal (agent settings; BO-12 binds it on the server by <c>local_id</c>).</summary>
    public sealed class TerminalConfig
    {
        public string LocalId { get; set; } = string.Empty;

        public string Driver { get; set; } = string.Empty;

        public string Name { get; set; } = string.Empty;

        /// <summary>Private LAN IPv4 only (RFC 1918).</summary>
        public string Host { get; set; } = string.Empty;

        public int Port { get; set; }

        public string? Tid { get; set; }
    }

    public sealed class CardPurchase
    {
        public Guid AttemptId { get; set; }

        public long AmountTiyin { get; set; }

        public string Currency { get; set; } = "UZS";

        public string? CashRegisterId { get; set; }

        public string? ClientEventId { get; set; }

        public long? ReceiptSeq { get; set; }
    }

    public sealed class CardRefund
    {
        public Guid AttemptId { get; set; }

        public long AmountTiyin { get; set; }

        public string? OriginalRrn { get; set; }

        public Guid? OriginalAttemptId { get; set; }
    }

    public sealed class CardVoid
    {
        public Guid AttemptId { get; set; }

        public long AmountTiyin { get; set; }

        public string? OriginalRrn { get; set; }

        public Guid? OriginalAttemptId { get; set; }
    }

    /// <summary>21 §9.4 TerminalHealth — status online | busy | offline | error.</summary>
    public sealed class TerminalHealth
    {
        public string Status { get; set; } = "offline";

        public string? Tid { get; set; }

        public string? LastTxAt { get; set; }

        public string? Message { get; set; }
    }

    public sealed class SchemeTotal
    {
        public string CardScheme { get; set; } = "other";

        public int Count { get; set; }

        public long TotalTiyin { get; set; }
    }

    /// <summary>
    /// 21 §9.4 SettlementResult: <c>count</c>/<c>total_tiyin</c> = purchases only (gross); refunds separately in
    /// <c>refund_count</c>/<c>refund_total_tiyin</c> (0 when none) — card_terminal_settlements (21 §16).
    /// </summary>
    public sealed class SettlementResult
    {
        public string? Tid { get; set; }

        public string? BatchNo { get; set; }

        public int Count { get; set; }

        public long TotalTiyin { get; set; }

        public int RefundCount { get; set; }

        public long RefundTotalTiyin { get; set; }

        public List<SchemeTotal> ByScheme { get; set; } = new List<SchemeTotal>();

        public string SettledAt { get; set; } = string.Empty;
    }

    [Flags]
    public enum DriverCapabilities
    {
        None = 0,
        Void = 1,
        CancelPending = 2,
        StatusByErn = 4,
        LastTransaction = 8,
        Settlement = 16,
        CardType = 32,
    }
}

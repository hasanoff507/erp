using System.Collections.Generic;

#pragma warning disable CA2227
#pragma warning disable CA1002
#pragma warning disable CA1056

namespace Erp1C.Fiscal
{
    // FiscalPort DTOs at the agent boundary — 21 §1 / §16.1 field names; money and quantities are integers
    // (tiyin int64, qty in thousandths) — qaror #12 / 26 #84.

    /// <summary>A fiscal device configured on the agent (capabilities.fiscal.devices[].local_id).</summary>
    public sealed class FiscalDeviceConfig
    {
        public string LocalId { get; set; } = string.Empty;

        /// <summary>fake | multikassa_local | fiscaldrive_local.</summary>
        public string Provider { get; set; } = string.Empty;

        public string Name { get; set; } = string.Empty;
    }

    /// <summary>21 §16.1 CashRegisterRef.</summary>
    public sealed class CashRegisterRef
    {
        public string CashRegisterId { get; set; } = string.Empty;

        public string LocalId { get; set; } = string.Empty;
    }

    public sealed class FiscalItem
    {
        public string Name { get; set; } = string.Empty;

        public string? Mxik { get; set; }

        public string? PackageCode { get; set; }

        public string? UnitCode { get; set; }

        public long QtyMilli { get; set; }

        public long PriceTiyin { get; set; }

        public long AmountTiyin { get; set; }

        public string? VatRate { get; set; }

        public long VatTiyin { get; set; }

        public List<string> MarkingCodes { get; set; } = new List<string>();
    }

    public sealed class FiscalPayments
    {
        /// <summary>cash | card | qr | mixed.</summary>
        public string PaymentForm { get; set; } = "cash";

        public long CashTiyin { get; set; }

        public long CardTiyin { get; set; }

        public long QrTiyin { get; set; }

        public string? CardType { get; set; }

        public string? CardMask { get; set; }

        public string? Rrn { get; set; }
    }

    public sealed class RefundInfo
    {
        public string FmTerminalId { get; set; } = string.Empty;

        public long FmReceiptSeq { get; set; }

        public string FiscalSign { get; set; } = string.Empty;
    }

    /// <summary>21 §16.1 FiscalReceiptPayload.</summary>
    public sealed class FiscalReceiptPayload
    {
        public CashRegisterRef CashRegister { get; set; } = new CashRegisterRef();

        public long ReceiptSeq { get; set; }

        /// <summary>sale | debt_settlement | credit_sale (POST /sale) or return (POST /refund).</summary>
        public string Kind { get; set; } = "sale";

        public List<FiscalItem> Items { get; set; } = new List<FiscalItem>();

        public FiscalPayments Payments { get; set; } = new FiscalPayments();

        public RefundInfo? RefundInfo { get; set; }

        public long TotalTiyin()
        {
            long s = 0;
            foreach (var i in Items) s += i.AmountTiyin;
            return s;
        }
    }

    /// <summary>21 §16.1 FiscalResult.</summary>
    public sealed class FiscalResult
    {
        public string FmTerminalId { get; set; } = string.Empty;

        public long FmReceiptSeq { get; set; }

        public string FiscalSign { get; set; } = string.Empty;

        public string QrUrl { get; set; } = string.Empty;

        public string FiscalAt { get; set; } = string.Empty;
    }

    public sealed class FiscalShiftResult
    {
        public string FmTerminalId { get; set; } = string.Empty;

        public string OpenedAt { get; set; } = string.Empty;
    }

    public sealed class ZTotals
    {
        public long Sale { get; set; }

        public long Return { get; set; }

        public Dictionary<string, long> ByPaymentForm { get; set; } = new Dictionary<string, long>();
    }

    /// <summary>21 §16.1 ZReport (totals in tiyin).</summary>
    public sealed class ZReport
    {
        public string FmTerminalId { get; set; } = string.Empty;

        public long ZNumber { get; set; }

        public ZTotals Totals { get; set; } = new ZTotals();

        public string ClosedAt { get; set; } = string.Empty;
    }

    public sealed class AckedReceipt
    {
        public string FmTerminalId { get; set; } = string.Empty;

        public long FmReceiptSeq { get; set; }

        public string AckedAt { get; set; } = string.Empty;
    }

    /// <summary>21 §16.1 FiscalDeviceStatus (+ acked receipts for the fiscal.status task).</summary>
    public sealed class FiscalDeviceStatus
    {
        /// <summary>ok | locked | ack_overdue | memory_full | unknown.</summary>
        public string FmState { get; set; } = "unknown";

        public int PendingCount { get; set; }

        public string? OldestUnackedAt { get; set; }

        public List<AckedReceipt> Acked { get; set; } = new List<AckedReceipt>();
    }

    public sealed class UnsentReceipt
    {
        public long FmReceiptSeq { get; set; }

        public string FiscalAt { get; set; } = string.Empty;

        public long AmountTiyin { get; set; }
    }

    public sealed class ResendResult
    {
        public int Sent { get; set; }

        public int Failed { get; set; }

        public List<AckedReceipt> Acked { get; set; } = new List<AckedReceipt>();
    }
}

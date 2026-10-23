using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace Erp1C.Fiscal
{
    /// <summary>
    /// Fiscal bridge to the partner's local service / FM (21 §1 FiscalPort, 34 §14.3). Partner-specific fields and
    /// error codes stay inside the bridge; the local API and the task schemas never change (26 #109).
    /// Exceptions: <see cref="FiscalProviderException"/> (partner service/FM error → FISCAL_PROVIDER_ERROR),
    /// <see cref="FiscalDeviceLockedException"/> (FM refuses to sign → FISCAL_DEVICE_LOCKED),
    /// <see cref="FiscalShiftStateException"/> (SHIFT_NOT_OPEN / SHIFT_ALREADY_OPEN).
    /// </summary>
    public interface IFiscalBridge
    {
        string Provider { get; }

        /// <summary>False for a bridge whose partner protocol is not available yet (⛔ 26 #109).</summary>
        bool Available { get; }

        Task<FiscalShiftResult> OpenShiftAsync(FiscalDeviceConfig device, long shiftNo, string cashierName, CancellationToken ct);

        Task<ZReport> CloseShiftAsync(FiscalDeviceConfig device, long? shiftNo, CancellationToken ct);

        Task<FiscalResult> RegisterSaleAsync(FiscalDeviceConfig device, FiscalReceiptPayload receipt, CancellationToken ct);

        Task<FiscalResult> RegisterRefundAsync(FiscalDeviceConfig device, FiscalReceiptPayload receipt, CancellationToken ct);

        Task<FiscalDeviceStatus> GetDeviceStatusAsync(FiscalDeviceConfig device, CancellationToken ct);

        Task<IReadOnlyList<UnsentReceipt>> ListUnsentAsync(FiscalDeviceConfig device, CancellationToken ct);

        Task<ResendResult> ResendUnsentAsync(FiscalDeviceConfig device, CancellationToken ct);

        /// <summary>The FM's own record of a receipt by our receipt_seq (resolves an interrupted call), or null.</summary>
        Task<FiscalResult?> FindReceiptAsync(FiscalDeviceConfig device, string cashRegisterId, long receiptSeq, CancellationToken ct);

        /// <summary>The last Z-report (null when no shift was ever closed); <c>shift_open</c> tells whether a shift is open.</summary>
        Task<(bool ShiftOpen, ZReport? LastZ)> ShiftStateAsync(FiscalDeviceConfig device, CancellationToken ct);
    }

    public class FiscalProviderException : Exception
    {
        public FiscalProviderException()
        {
        }

        public FiscalProviderException(string message)
            : base(message)
        {
        }

        public FiscalProviderException(string message, Exception inner)
            : base(message, inner)
        {
        }
    }

    public sealed class FiscalDeviceLockedException : FiscalProviderException
    {
        public FiscalDeviceLockedException()
        {
        }

        public FiscalDeviceLockedException(string message)
            : base(message)
        {
        }

        public FiscalDeviceLockedException(string message, Exception inner)
            : base(message, inner)
        {
        }
    }

    public sealed class FiscalShiftStateException : FiscalProviderException
    {
        public FiscalShiftStateException()
        {
        }

        public FiscalShiftStateException(string message)
            : base(message)
        {
        }

        public FiscalShiftStateException(string message, Exception inner)
            : base(message, inner)
        {
        }

        /// <summary>True → SHIFT_ALREADY_OPEN, false → SHIFT_NOT_OPEN.</summary>
        public bool AlreadyOpen { get; set; }
    }

    /// <summary>
    /// Placeholder for the partner local services (<c>multikassa_local</c>, <c>fiscaldrive_local</c>): their protocol,
    /// authentication and certification are not public yet — ⛔ 26 #109. Every call fails with FISCAL_PROVIDER_ERROR
    /// and the capability is not announced, so the server never routes a register to it.
    /// </summary>
    public sealed class UnavailableFiscalBridge : IFiscalBridge
    {
        public UnavailableFiscalBridge(string provider)
        {
            Provider = provider;
        }

        public string Provider { get; }

        public bool Available => false;

        private FiscalProviderException NotAvailable() => new FiscalProviderException(Provider + " bridge is not available (26 #109)");

        public Task<FiscalShiftResult> OpenShiftAsync(FiscalDeviceConfig device, long shiftNo, string cashierName, CancellationToken ct) => throw NotAvailable();

        public Task<ZReport> CloseShiftAsync(FiscalDeviceConfig device, long? shiftNo, CancellationToken ct) => throw NotAvailable();

        public Task<FiscalResult> RegisterSaleAsync(FiscalDeviceConfig device, FiscalReceiptPayload receipt, CancellationToken ct) => throw NotAvailable();

        public Task<FiscalResult> RegisterRefundAsync(FiscalDeviceConfig device, FiscalReceiptPayload receipt, CancellationToken ct) => throw NotAvailable();

        public Task<FiscalDeviceStatus> GetDeviceStatusAsync(FiscalDeviceConfig device, CancellationToken ct) => throw NotAvailable();

        public Task<IReadOnlyList<UnsentReceipt>> ListUnsentAsync(FiscalDeviceConfig device, CancellationToken ct) => throw NotAvailable();

        public Task<ResendResult> ResendUnsentAsync(FiscalDeviceConfig device, CancellationToken ct) => throw NotAvailable();

        public Task<FiscalResult?> FindReceiptAsync(FiscalDeviceConfig device, string cashRegisterId, long receiptSeq, CancellationToken ct) => throw NotAvailable();

        public Task<(bool ShiftOpen, ZReport? LastZ)> ShiftStateAsync(FiscalDeviceConfig device, CancellationToken ct) => throw NotAvailable();
    }
}

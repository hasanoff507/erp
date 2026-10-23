using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;

namespace Erp1C.CardTerminal
{
    /// <summary>
    /// Vendor driver plug-in (34 §14.4). The vendor protocol stays inside the driver; only <see cref="CardTxResult"/>
    /// leaves it. Exceptions: <see cref="CardTerminalUnreachableException"/> — nothing reached the terminal;
    /// <see cref="CardTerminalBusyException"/> — the terminal refused (busy); <see cref="CardTerminalTimeoutException"/>
    /// or any other exception after the request was sent — outcome unknown.
    /// </summary>
    public interface ICardTerminalDriver
    {
        string Name { get; }

        DriverCapabilities Capabilities { get; }

        Task<TerminalHealth> HealthAsync(TerminalConfig t, CancellationToken ct);

        Task<CardTxResult> PurchaseAsync(TerminalConfig t, CardPurchase req, CancellationToken ct);

        Task<CardTxResult> RefundAsync(TerminalConfig t, CardRefund req, CancellationToken ct);

        Task<CardTxResult> VoidAsync(TerminalConfig t, CardVoid req, CancellationToken ct);

        Task<CardTxResult?> GetStatusAsync(TerminalConfig t, Guid attemptId, CancellationToken ct);

        Task<CardTxResult?> GetLastTransactionAsync(TerminalConfig t, CancellationToken ct);

        Task<SettlementResult> SettlementAsync(TerminalConfig t, CancellationToken ct);

        Task CancelPendingAsync(TerminalConfig t, Guid attemptId, CancellationToken ct);
    }

    public class CardTerminalException : Exception
    {
        public CardTerminalException()
        {
        }

        public CardTerminalException(string message)
            : base(message)
        {
        }

        public CardTerminalException(string message, Exception inner)
            : base(message, inner)
        {
        }
    }

    /// <summary>The request never reached the terminal (connect failed / refused within 5 s).</summary>
    public sealed class CardTerminalUnreachableException : CardTerminalException
    {
        public CardTerminalUnreachableException()
        {
        }

        public CardTerminalUnreachableException(string message)
            : base(message)
        {
        }

        public CardTerminalUnreachableException(string message, Exception inner)
            : base(message, inner)
        {
        }
    }

    /// <summary>The terminal answered "busy" — nothing was started.</summary>
    public sealed class CardTerminalBusyException : CardTerminalException
    {
        public CardTerminalBusyException()
        {
        }

        public CardTerminalBusyException(string message)
            : base(message)
        {
        }

        public CardTerminalBusyException(string message, Exception inner)
            : base(message, inner)
        {
        }
    }

    /// <summary>Sent, no answer — the outcome is unknown (never retried automatically).</summary>
    public sealed class CardTerminalTimeoutException : CardTerminalException
    {
        public CardTerminalTimeoutException()
        {
        }

        public CardTerminalTimeoutException(string message)
            : base(message)
        {
        }

        public CardTerminalTimeoutException(string message, Exception inner)
            : base(message, inner)
        {
        }
    }

    /// <summary>
    /// Compile-time driver list (34 §14.4, 32 §1.3) — no DLL is loaded by reflection; a new driver ships in a new
    /// signed agent release.
    /// </summary>
    public sealed class DriverRegistry
    {
        private readonly Dictionary<string, ICardTerminalDriver> _drivers;

        public DriverRegistry(IEnumerable<ICardTerminalDriver> drivers)
        {
            _drivers = drivers.ToDictionary(d => d.Name, StringComparer.Ordinal);
        }

        public IEnumerable<string> Names => _drivers.Keys;

        public bool TryGet(string name, out ICardTerminalDriver driver) => _drivers.TryGetValue(name, out driver!);
    }
}

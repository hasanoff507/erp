using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;

namespace Erp1C.CardTerminal.Drivers.Fake
{
    /// <summary>Fake outcomes — same table as the web/backend fakes (24 §6.5, 21 §9.4).</summary>
    public enum FakeOutcome
    {
        Approved,
        Declined51,
        TimeoutThenApproved,
        TimeoutUnresolved,
        Busy,
        AmountMismatch,
        ApprovedVoidFails,
        Cancelled,
        Error,
        ApprovedSocial,
        TimeoutThenNotFound,
        Declined05,
        Unreachable,
    }

    /// <summary>
    /// Terminal emulator for CI, demo and the DoD-02 tests (34 §14.4). Deterministic by the last three digits of the
    /// amount in so'm (<c>amount_tiyin / 100 % 1000</c>): other → approved; 001 declined 51; 002 no answer → status
    /// approved; 003 no answer, unresolvable; 004 busy; 005 approved 100 000 tiyin less; 006 approved, the void
    /// fails; 007 cancelled; 008 error; 009 approved, card_type social; 010 no answer → status not_found; 011
    /// declined 05. Raw mask <c>860031******1234</c> (the common layer normalises it). Holds no real card data.
    /// </summary>
    public sealed class FakeCardTerminalDriver : ICardTerminalDriver
    {
        public const string FakeTid = "T0000001";
        public const string RawMask = "860031******1234";

        private readonly ConcurrentDictionary<Guid, CardTxResult> _byAttempt = new ConcurrentDictionary<Guid, CardTxResult>();
        private readonly ConcurrentDictionary<Guid, FakeOutcome> _pending = new ConcurrentDictionary<Guid, FakeOutcome>();
        private readonly ConcurrentQueue<FakeOutcome> _forced = new ConcurrentQueue<FakeOutcome>();
        private readonly List<CardTxResult> _batch = new List<CardTxResult>();
        private readonly object _lock = new object();
        private readonly Func<DateTimeOffset> _now;
        private CardTxResult? _last;
        private int _batchNo = 1;

        public FakeCardTerminalDriver(TimeSpan? delay = null, Func<DateTimeOffset>? now = null)
        {
            Delay = delay ?? TimeSpan.Zero;
            _now = now ?? (() => DateTimeOffset.UtcNow);
        }

        public string Name => "fake";

        public DriverCapabilities Capabilities =>
            DriverCapabilities.Void | DriverCapabilities.CancelPending | DriverCapabilities.StatusByErn |
            DriverCapabilities.LastTransaction | DriverCapabilities.Settlement | DriverCapabilities.CardType;

        /// <summary>Simulated customer time on the terminal before an approval (3 s in demo, 0 in tests).</summary>
        public TimeSpan Delay { get; set; }

        /// <summary>Health answer (tests flip it to offline/error).</summary>
        public string HealthStatus { get; set; } = "online";

        private int _purchaseCalls;

        public int PurchaseCalls => Volatile.Read(ref _purchaseCalls);
        private int _refundCalls;

        public int RefundCalls => Volatile.Read(ref _refundCalls);
        private int _voidCalls;

        public int VoidCalls => Volatile.Read(ref _voidCalls);
        private int _statusCalls;

        public int StatusCalls => Volatile.Read(ref _statusCalls);
        private int _healthCalls;

        public int HealthCalls => Volatile.Read(ref _healthCalls);
        private int _settlementCalls;

        public int SettlementCalls => Volatile.Read(ref _settlementCalls);

        /// <summary>Force the next purchase outcomes (FIFO), overriding the amount table.</summary>
        public void Scenario(params FakeOutcome[] outcomes)
        {
            foreach (var o in outcomes) _forced.Enqueue(o);
        }

        public static FakeOutcome OutcomeFor(long amountTiyin)
        {
            switch ((amountTiyin / 100) % 1000)
            {
                case 1: return FakeOutcome.Declined51;
                case 2: return FakeOutcome.TimeoutThenApproved;
                case 3: return FakeOutcome.TimeoutUnresolved;
                case 4: return FakeOutcome.Busy;
                case 5: return FakeOutcome.AmountMismatch;
                case 6: return FakeOutcome.ApprovedVoidFails;
                case 7: return FakeOutcome.Cancelled;
                case 8: return FakeOutcome.Error;
                case 9: return FakeOutcome.ApprovedSocial;
                case 10: return FakeOutcome.TimeoutThenNotFound;
                case 11: return FakeOutcome.Declined05;
                default: return FakeOutcome.Approved;
            }
        }

        private string Iso() => _now().UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ss.fffZ", CultureInfo.InvariantCulture);

        private static string RrnOf(Guid id)
        {
            var hex = id.ToString("N");
            ulong h = 0;
            foreach (var c in hex) h = unchecked((h * 16) + (ulong)Convert.ToInt32(c.ToString(), 16)) % 1000000000000UL;
            return h.ToString("D12", CultureInfo.InvariantCulture);
        }

        private CardTxResult Base(Guid id, string kind) => new CardTxResult
        {
            AttemptId = id.ToString("D"),
            Kind = kind,
            Status = CardStatuses.Approved,
            Tid = FakeTid,
            Mid = "M000000000001",
            Acquirer = "FAKEBANK",
            TxAt = Iso(),
        };

        private CardTxResult Approved(Guid id, string kind, long amount)
        {
            var r = Base(id, kind);
            r.AmountTiyin = amount;
            r.Rrn = RrnOf(id);
            r.Stan = RrnOf(id).Substring(6);
            r.ApprovalCode = id.ToString("N").Substring(26).ToUpperInvariant();
            r.CardMask = RawMask;
            r.CardScheme = "uzcard";
            r.EntryMode = "contactless";
            return r;
        }

        public Task<TerminalHealth> HealthAsync(TerminalConfig t, CancellationToken ct)
        {
            Interlocked.Increment(ref _healthCalls);
            if (HealthStatus == "offline") throw new CardTerminalUnreachableException("fake terminal offline");
            return Task.FromResult(new TerminalHealth { Status = HealthStatus, Tid = FakeTid, LastTxAt = _last?.TxAt });
        }

        public async Task<CardTxResult> PurchaseAsync(TerminalConfig t, CardPurchase req, CancellationToken ct)
        {
            Interlocked.Increment(ref _purchaseCalls);
            var outcome = _forced.TryDequeue(out var f) ? f : OutcomeFor(req.AmountTiyin);
            switch (outcome)
            {
                case FakeOutcome.Unreachable:
                    throw new CardTerminalUnreachableException("fake terminal unreachable");
                case FakeOutcome.Busy:
                    throw new CardTerminalBusyException("fake terminal busy");
                case FakeOutcome.TimeoutThenApproved:
                case FakeOutcome.TimeoutUnresolved:
                case FakeOutcome.TimeoutThenNotFound:
                    _pending[req.AttemptId] = outcome;
                    if (outcome == FakeOutcome.TimeoutThenApproved) Record(Approved(req.AttemptId, CardKinds.Purchase, req.AmountTiyin), req.AttemptId);
                    throw new CardTerminalTimeoutException("fake terminal did not answer");
            }

            if (Delay > TimeSpan.Zero) await Task.Delay(Delay, ct).ConfigureAwait(false);
            if (_cancelRequested.TryRemove(req.AttemptId, out _)) outcome = FakeOutcome.Cancelled;

            CardTxResult r;
            switch (outcome)
            {
                case FakeOutcome.Declined51:
                    r = Base(req.AttemptId, CardKinds.Purchase);
                    r.Status = CardStatuses.Declined;
                    r.DeclineCode = "51";
                    r.DeclineMessage = "Mablag' yetarli emas";
                    r.CardMask = RawMask;
                    break;
                case FakeOutcome.Declined05:
                    r = Base(req.AttemptId, CardKinds.Purchase);
                    r.Status = CardStatuses.Declined;
                    r.DeclineCode = "05";
                    r.DeclineMessage = "Rad etildi";
                    break;
                case FakeOutcome.Cancelled:
                    r = Base(req.AttemptId, CardKinds.Purchase);
                    r.Status = CardStatuses.Cancelled;
                    r.DeclineCode = "cancelled";
                    break;
                case FakeOutcome.Error:
                    r = Base(req.AttemptId, CardKinds.Purchase);
                    r.Status = CardStatuses.Error;
                    r.DeclineCode = "error";
                    break;
                case FakeOutcome.AmountMismatch:
                    r = Approved(req.AttemptId, CardKinds.Purchase, req.AmountTiyin - 100000);
                    break;
                case FakeOutcome.ApprovedVoidFails:
                    r = Approved(req.AttemptId, CardKinds.Purchase, req.AmountTiyin);
                    _voidFails[r.Rrn!] = true;
                    break;
                case FakeOutcome.ApprovedSocial:
                    r = Approved(req.AttemptId, CardKinds.Purchase, req.AmountTiyin);
                    r.CardType = "social";
                    break;
                default:
                    r = Approved(req.AttemptId, CardKinds.Purchase, req.AmountTiyin);
                    break;
            }

            Record(r, req.AttemptId);
            return r;
        }

        private readonly ConcurrentDictionary<string, bool> _voidFails = new ConcurrentDictionary<string, bool>(StringComparer.Ordinal);
        private readonly ConcurrentDictionary<Guid, bool> _cancelRequested = new ConcurrentDictionary<Guid, bool>();

        private void Record(CardTxResult r, Guid id)
        {
            _byAttempt[id] = r;
            lock (_lock)
            {
                _last = r;
                if (r.Status == CardStatuses.Approved) _batch.Add(r);
            }
        }

        public Task<CardTxResult> RefundAsync(TerminalConfig t, CardRefund req, CancellationToken ct)
        {
            Interlocked.Increment(ref _refundCalls);
            var r = Approved(req.AttemptId, CardKinds.Refund, req.AmountTiyin);
            Record(r, req.AttemptId);
            return Task.FromResult(r);
        }

        public Task<CardTxResult> VoidAsync(TerminalConfig t, CardVoid req, CancellationToken ct)
        {
            Interlocked.Increment(ref _voidCalls);
            if (req.OriginalRrn != null && _voidFails.ContainsKey(req.OriginalRrn))
            {
                var e = Base(req.AttemptId, CardKinds.Void);
                e.Status = CardStatuses.Error;
                e.DeclineCode = "error";
                e.DeclineMessage = "Void rejected";
                return Task.FromResult(e);
            }

            var r = Approved(req.AttemptId, CardKinds.Void, req.AmountTiyin);
            lock (_lock)
            {
                _batch.RemoveAll(x => x.Kind == CardKinds.Purchase && x.Rrn == req.OriginalRrn);
            }

            _byAttempt[req.AttemptId] = r;
            return Task.FromResult(r);
        }

        public Task<CardTxResult?> GetStatusAsync(TerminalConfig t, Guid attemptId, CancellationToken ct)
        {
            Interlocked.Increment(ref _statusCalls);
            if (_pending.TryGetValue(attemptId, out var o))
            {
                if (o == FakeOutcome.TimeoutUnresolved) return Task.FromResult<CardTxResult?>(null);
                if (o == FakeOutcome.TimeoutThenNotFound)
                {
                    var nf = Base(attemptId, CardKinds.Purchase);
                    nf.Status = CardStatuses.Declined;
                    nf.DeclineCode = "not_found";
                    return Task.FromResult<CardTxResult?>(nf);
                }
            }

            return Task.FromResult(_byAttempt.TryGetValue(attemptId, out var r) ? r : null);
        }

        public Task<CardTxResult?> GetLastTransactionAsync(TerminalConfig t, CancellationToken ct)
        {
            lock (_lock)
            {
                // The unresolvable scenario has nothing on the terminal either.
                var last = _last;
                if (last != null && Guid.TryParse(last.AttemptId, out var id) && _pending.TryGetValue(id, out var o) && o != FakeOutcome.TimeoutThenApproved) return Task.FromResult<CardTxResult?>(null);
                return Task.FromResult(last);
            }
        }

        public Task<SettlementResult> SettlementAsync(TerminalConfig t, CancellationToken ct)
        {
            Interlocked.Increment(ref _settlementCalls);
            lock (_lock)
            {
                var purchases = _batch.Where(x => x.Kind == CardKinds.Purchase).ToList();
                var refunds = _batch.Where(x => x.Kind == CardKinds.Refund).ToList();
                var r = new SettlementResult
                {
                    Tid = FakeTid,
                    BatchNo = _batchNo.ToString("D6", CultureInfo.InvariantCulture),
                    Count = purchases.Count,
                    TotalTiyin = purchases.Sum(x => x.AmountTiyin ?? 0),
                    RefundCount = refunds.Count,
                    RefundTotalTiyin = refunds.Sum(x => x.AmountTiyin ?? 0),
                    ByScheme = purchases.GroupBy(x => x.CardScheme ?? "other")
                        .Select(g => new SchemeTotal { CardScheme = g.Key, Count = g.Count(), TotalTiyin = g.Sum(x => x.AmountTiyin ?? 0) })
                        .ToList(),
                    SettledAt = Iso(),
                };
                _batch.Clear();
                _batchNo++;
                return Task.FromResult(r);
            }
        }

        public Task CancelPendingAsync(TerminalConfig t, Guid attemptId, CancellationToken ct)
        {
            _cancelRequested[attemptId] = true;
            return Task.CompletedTask;
        }
    }
}

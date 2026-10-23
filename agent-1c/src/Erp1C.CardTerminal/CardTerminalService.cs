using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Core.Errors;
using Erp1C.Core.Hosting;
using Erp1C.Core.Security;

namespace Erp1C.CardTerminal
{
    /// <summary>Configured terminals as the agent settings define them.</summary>
    public interface ICardTerminalConfig
    {
        IReadOnlyList<TerminalConfig> Terminals { get; }

        /// <summary>The <c>fake</c> driver counts only in a DEV build or on a demo-tenant agent (34 §14.4).</summary>
        bool AllowFakeDriver { get; }
    }

    /// <summary>Timeouts of 21 §9.4 / 34 §14.4 (overridable in tests).</summary>
    public sealed class CardTimeouts
    {
        public TimeSpan Purchase { get; set; } = TimeSpan.FromSeconds(120);

        public TimeSpan RefundVoid { get; set; } = TimeSpan.FromSeconds(60);

        public TimeSpan Health { get; set; } = TimeSpan.FromSeconds(3);

        public TimeSpan Status { get; set; } = TimeSpan.FromSeconds(10);

        public TimeSpan Settlement { get; set; } = TimeSpan.FromSeconds(60);

        public TimeSpan CancelPending { get; set; } = TimeSpan.FromSeconds(5);

        /// <summary>Safe operations (health, status, settlement): 3 tries, 2 s apart.</summary>
        public int SafeTries { get; set; } = 3;

        public TimeSpan SafeRetryDelay { get; set; } = TimeSpan.FromSeconds(2);

        public TimeSpan HealthCacheAge { get; set; } = TimeSpan.FromSeconds(30);
    }

    /// <summary>Result of a local card call: HTTP status + CardTxResult or a 17 §15 error code.</summary>
    public sealed class CardCallResult
    {
        private CardCallResult(int status, CardTxResult? tx, string? code, IDictionary<string, object?>? parameters, string? attemptId)
        {
            Status = status;
            Tx = tx;
            ErrorCode = code;
            Params = parameters;
            AttemptId = attemptId;
        }

        public int Status { get; }

        public CardTxResult? Tx { get; }

        public string? ErrorCode { get; }

        public IDictionary<string, object?>? Params { get; }

        /// <summary>For 202 — the POS polls <c>GET /v1/card/tx/{attempt_id}</c>.</summary>
        public string? AttemptId { get; }

        public static CardCallResult Ok(CardTxResult tx) => new CardCallResult(200, tx, null, null, tx.AttemptId);

        public static CardCallResult Accepted(string attemptId) => new CardCallResult(202, null, null, null, attemptId);

        public static CardCallResult Error(string code, IDictionary<string, object?>? parameters = null) =>
            new CardCallResult(LocalCodes.Status(code), null, code, parameters, null);
    }

    public sealed class TerminalListItem
    {
        public string LocalId { get; set; } = string.Empty;

        public string Driver { get; set; } = string.Empty;

        public string Host { get; set; } = string.Empty;

        public string? Tid { get; set; }

        public string Status { get; set; } = "offline";
    }

    public sealed class TerminalStatusItem
    {
        public string? CardTerminalId { get; set; }

        public string LocalId { get; set; } = string.Empty;

        public string Status { get; set; } = "offline";

        public string? Tid { get; set; }

        public string? LastTxAt { get; set; }
    }

    /// <summary>A resolved <c>unknown</c> attempt reported in the card.status result (21 §16).</summary>
    public sealed class ResolvedAttempt
    {
        public string AttemptId { get; set; } = string.Empty;

        public string Kind { get; set; } = CardKinds.Purchase;

        public string Status { get; set; } = CardStatuses.Unknown;

        public long? AmountTiyin { get; set; }

        public string? ApprovalCode { get; set; }

        public string? Rrn { get; set; }

        public string? Stan { get; set; }

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

        public string ResolvedBy { get; set; } = "status_query";

        public string LocalId { get; set; } = string.Empty;

        public static ResolvedAttempt From(CardTxResult r, string localId) => new ResolvedAttempt
        {
            AttemptId = r.AttemptId,
            Kind = r.Kind,
            Status = r.Status == CardStatuses.Cancelled || r.Status == CardStatuses.Error ? CardStatuses.Declined : r.Status,
            AmountTiyin = r.AmountTiyin,
            ApprovalCode = r.ApprovalCode,
            Rrn = r.Rrn,
            Stan = r.Stan,
            CardMask = r.CardMask,
            CardScheme = r.CardScheme,
            CardType = r.CardType,
            EntryMode = r.EntryMode,
            Tid = r.Tid,
            Mid = r.Mid,
            Acquirer = r.Acquirer,
            TxAt = r.TxAt,
            DeclineCode = r.DeclineCode ?? (r.Status == CardStatuses.Cancelled ? "cancelled" : r.Status == CardStatuses.Error ? "error" : null),
            DeclineMessage = r.DeclineMessage,
            SlipText = r.SlipText,
            LocalId = localId,
        };
    }

    /// <summary>
    /// <c>Erp1C.CardTerminal</c> common layer (34 §14.4): attempt journal and idempotency, DeviceLane per terminal,
    /// timeouts, normalisation, amount check with automatic void, unknown-outcome resolution. <c>purchase</c> is
    /// never sent to a terminal twice for one attempt_id.
    /// </summary>
    public sealed class CardTerminalService
    {
        private readonly ICardTerminalConfig _config;
        private readonly DriverRegistry _drivers;
        private readonly CardJournal _journal;
        private readonly DeviceLanes _lanes;
        private readonly IClock _clock;
        private readonly IAgentLogger _log;
        private readonly CardTimeouts _t;
        private readonly Func<TimeSpan, CancellationToken, Task> _delay;
        private readonly ConcurrentDictionary<string, (TerminalHealth Health, DateTimeOffset At)> _health =
            new ConcurrentDictionary<string, (TerminalHealth, DateTimeOffset)>(StringComparer.Ordinal);

        public CardTerminalService(
            ICardTerminalConfig config,
            DriverRegistry drivers,
            CardJournal journal,
            DeviceLanes lanes,
            IClock clock,
            IAgentLogger? log = null,
            CardTimeouts? timeouts = null,
            Func<TimeSpan, CancellationToken, Task>? delay = null)
        {
            _config = config;
            _drivers = drivers;
            _journal = journal;
            _lanes = lanes;
            _clock = clock;
            _log = log ?? NullAgentLogger.Instance;
            _t = timeouts ?? new CardTimeouts();
            _delay = delay ?? ((d, ct) => Task.Delay(d, ct));
        }

        public CardJournal Journal => _journal;

        /// <summary>Terminals with a valid private-LAN address and an installed (and allowed) driver.</summary>
        public IReadOnlyList<(TerminalConfig Config, ICardTerminalDriver Driver)> ActiveTerminals()
        {
            var list = new List<(TerminalConfig, ICardTerminalDriver)>();
            foreach (var t in _config.Terminals)
            {
                if (TryResolve(t.LocalId, out var cfg, out var drv)) list.Add((cfg, drv));
            }

            return list;
        }

        public bool Enabled => ActiveTerminals().Count > 0;

        public bool TryResolve(string? localId, out TerminalConfig config, out ICardTerminalDriver driver)
        {
            config = null!;
            driver = null!;
            if (string.IsNullOrEmpty(localId)) return false;
            var t = _config.Terminals.FirstOrDefault(x => string.Equals(x.LocalId, localId, StringComparison.Ordinal));
            if (t is null) return false;
            if (!PrivateLan.IsPrivateIPv4(t.Host) || !PrivateLan.IsValidPort(t.Port)) return false;
            if (!_drivers.TryGet(t.Driver, out var d)) return false;
            if (d.Name == "fake" && !_config.AllowFakeDriver) return false;
            config = t;
            driver = d;
            return true;
        }

        private string Now() => CardJournal.Iso(_clock.UtcNow);

        private static CancellationTokenSource Timeout(TimeSpan span, CancellationToken outer)
        {
            var cts = CancellationTokenSource.CreateLinkedTokenSource(outer);
            cts.CancelAfter(span);
            return cts;
        }

        // ---------------------------------------------------------------- terminals / health

        public IReadOnlyList<TerminalListItem> Terminals()
        {
            var items = new List<TerminalListItem>();
            foreach (var (cfg, drv) in ActiveTerminals())
            {
                var status = "offline";
                if (_lanes.For(cfg.LocalId).HasTransaction)
                {
                    status = "busy";
                }
                else if (_health.TryGetValue(cfg.LocalId, out var h))
                {
                    status = h.Health.Status;
                }

                items.Add(new TerminalListItem { LocalId = cfg.LocalId, Driver = drv.Name, Host = cfg.Host, Tid = cfg.Tid ?? (_health.TryGetValue(cfg.LocalId, out var hh) ? hh.Health.Tid : null), Status = status });
            }

            return items;
        }

        /// <summary>True when the cached health of a terminal is older than 30 s (the caller refreshes in the background).</summary>
        public bool HealthStale(string localId) =>
            !_health.TryGetValue(localId, out var h) || _clock.UtcNow - h.At > _t.HealthCacheAge;

        public async Task<TerminalHealth> HealthAsync(string localId, bool withRetries, CancellationToken ct)
        {
            if (!TryResolve(localId, out var cfg, out var drv)) throw new LocalApiException(LocalCodes.NotFound, new Dictionary<string, object?> { ["local_id"] = localId });
            var lane = _lanes.For(localId);
            if (lane.HasTransaction)
            {
                var busy = new TerminalHealth { Status = "busy", Tid = cfg.Tid, LastTxAt = LastTxAt(localId) };
                return busy;
            }

            var tries = withRetries ? Math.Max(1, _t.SafeTries) : 1;
            TerminalHealth result = new TerminalHealth { Status = "offline", Tid = cfg.Tid };
            for (var i = 0; i < tries; i++)
            {
                if (i > 0) await _delay(_t.SafeRetryDelay, ct).ConfigureAwait(false);
                try
                {
                    using var cts = Timeout(_t.Health, ct);
                    using (await lane.EnterAsync(false, cts.Token).ConfigureAwait(false))
                    {
                        result = await drv.HealthAsync(cfg, cts.Token).ConfigureAwait(false);
                    }

                    result.Tid ??= cfg.Tid;
                    result.LastTxAt ??= LastTxAt(localId);
                    if (result.Status == "online" || result.Status == "busy") break;
                }
                catch (OperationCanceledException) when (!ct.IsCancellationRequested)
                {
                    result = new TerminalHealth { Status = "offline", Tid = cfg.Tid, Message = "timeout" };
                }
                catch (CardTerminalUnreachableException)
                {
                    result = new TerminalHealth { Status = "offline", Tid = cfg.Tid, Message = "unreachable" };
                }
                catch (CardTerminalBusyException)
                {
                    result = new TerminalHealth { Status = "busy", Tid = cfg.Tid };
                    break;
                }
                catch (CardTerminalException e)
                {
                    result = new TerminalHealth { Status = "error", Tid = cfg.Tid, Message = e.Message };
                }
            }

            _health[localId] = (result, _clock.UtcNow);
            return result;
        }

        private string? LastTxAt(string localId) =>
            _journal.All()
                .Where(a => a.LocalId == localId && a.Result?.TxAt != null && a.Result.Status == CardStatuses.Approved)
                .Select(a => a.Result!.TxAt)
                .OrderByDescending(x => x, StringComparer.Ordinal)
                .FirstOrDefault();

        // ---------------------------------------------------------------- purchase

        public async Task<CardCallResult> PurchaseAsync(string localId, CardPurchase req, CancellationToken ct)
        {
            if (!TryResolve(localId, out var cfg, out var drv)) return CardCallResult.Error(LocalCodes.NotFound, new Dictionary<string, object?> { ["local_id"] = localId });
            var attemptId = req.AttemptId.ToString("D");

            var existing = _journal.Get(attemptId);
            if (existing != null) return Replay(existing, CardKinds.Purchase, localId, req.AmountTiyin);

            var lane = _lanes.For(localId);
            using var slot = await lane.TryEnterExclusiveAsync(ct).ConfigureAwait(false);
            if (slot is null) return CardCallResult.Error(LocalCodes.CardTerminalBusy, new Dictionary<string, object?> { ["local_id"] = localId });

            var attempt = new CardAttempt { AttemptId = attemptId, Kind = CardKinds.Purchase, LocalId = localId, AmountTiyin = req.AmountTiyin };
            if (!_journal.TryCreate(attempt)) return Replay(_journal.Get(attemptId)!, CardKinds.Purchase, localId, req.AmountTiyin);

            // From here on the attempt is "sent": it is never handed to the driver again (no automatic retry).
            attempt.State = "sent";
            _journal.Write("sent", attempt);
            _log.Info("card.purchase.sent", "card purchase sent", Ctx(attempt));

            CardTxResult raw;
            try
            {
                using var cts = Timeout(_t.Purchase, ct);
                raw = await drv.PurchaseAsync(cfg, req, cts.Token).ConfigureAwait(false);
            }
            catch (Exception e)
            {
                return FinishWithException(attempt, e);
            }

            var res = CardNormalizer.Normalize(raw, attemptId, CardKinds.Purchase);
            if (res.Status == CardStatuses.Approved && res.AmountTiyin is null) res.AmountTiyin = req.AmountTiyin;
            if (res.Status == CardStatuses.Timeout || res.Status == CardStatuses.Unknown)
            {
                return Finish(attempt, Unknown(attempt), 504, LocalCodes.CardTerminalTimeout, "auto");
            }

            if (res.Status == CardStatuses.Approved && res.AmountTiyin != req.AmountTiyin)
            {
                Finish(attempt, res, 422, LocalCodes.CardAmountMismatch, "auto");
                var voidStatus = await AutoVoidAsync(cfg, drv, attempt, res, ct).ConfigureAwait(false);
                _log.Warn("card.void.auto", "amount mismatch, automatic void: " + voidStatus, Ctx(attempt));
                var p = new Dictionary<string, object?>
                {
                    ["amount_tiyin"] = req.AmountTiyin,
                    ["approved_amount_tiyin"] = res.AmountTiyin,
                    ["void_status"] = voidStatus,
                };
                _mismatchParams[attemptId] = p;
                return CardCallResult.Error(LocalCodes.CardAmountMismatch, p);
            }

            return Finish(attempt, res, 200, null, "auto");
        }

        private readonly ConcurrentDictionary<string, IDictionary<string, object?>> _mismatchParams =
            new ConcurrentDictionary<string, IDictionary<string, object?>>(StringComparer.OrdinalIgnoreCase);

        /// <summary>Automatic void after CARD_AMOUNT_MISMATCH (the only automatic void the agent does, 21 §9.4).</summary>
        private async Task<string> AutoVoidAsync(TerminalConfig cfg, ICardTerminalDriver drv, CardAttempt original, CardTxResult approved, CancellationToken ct)
        {
            if ((drv.Capabilities & DriverCapabilities.Void) == 0) return "failed";
            var voidId = Guid.NewGuid();
            var va = new CardAttempt
            {
                AttemptId = voidId.ToString("D"),
                Kind = CardKinds.Void,
                LocalId = original.LocalId,
                AmountTiyin = approved.AmountTiyin ?? original.AmountTiyin,
                OriginalAttemptId = original.AttemptId,
                OriginalRrn = approved.Rrn,
                State = "sent",
            };
            _journal.TryCreate(va);
            _journal.Write("sent", va);
            try
            {
                using var cts = Timeout(_t.RefundVoid, ct);
                var raw = await drv.VoidAsync(cfg, new CardVoid { AttemptId = voidId, AmountTiyin = va.AmountTiyin, OriginalAttemptId = Guid.Parse(original.AttemptId), OriginalRrn = approved.Rrn }, cts.Token).ConfigureAwait(false);
                var res = CardNormalizer.Normalize(raw, va.AttemptId, CardKinds.Void);
                if (res.Status == CardStatuses.Approved)
                {
                    Finish(va, res, 200, null, "auto");
                    MarkVoided(original.AttemptId, va.AttemptId);
                    return "voided";
                }

                Finish(va, res, 502, LocalCodes.CardVoidFailed, "auto");
                return "failed";
            }
            catch (Exception e)
            {
                FinishWithException(va, e);
                return "failed";
            }
        }

        private void MarkVoided(string originalId, string voidId)
        {
            var o = _journal.Get(originalId);
            if (o is null) return;
            o.VoidedBy = voidId;
            _journal.Write("voided", o);
        }

        private CardCallResult Replay(CardAttempt existing, string kind, string localId, long amountTiyin)
        {
            if (existing.Kind != kind || existing.LocalId != localId || existing.AmountTiyin != amountTiyin)
            {
                return CardCallResult.Error(LocalCodes.ValidationError, new Dictionary<string, object?> { ["field"] = "attempt_id", ["reason"] = "reused" });
            }

            if (existing.State != "done") return CardCallResult.Accepted(existing.AttemptId);
            return Stored(existing);
        }

        private CardCallResult Stored(CardAttempt a)
        {
            if (a.HttpStatus == 200 && a.Result != null) return CardCallResult.Ok(a.Result);
            if (a.ErrorCode == LocalCodes.CardAmountMismatch)
            {
                _mismatchParams.TryGetValue(a.AttemptId, out var p);
                return CardCallResult.Error(LocalCodes.CardAmountMismatch, p ?? new Dictionary<string, object?> { ["amount_tiyin"] = a.AmountTiyin, ["approved_amount_tiyin"] = a.Result?.AmountTiyin, ["void_status"] = a.VoidedBy != null ? "voided" : "failed" });
            }

            return CardCallResult.Error(a.ErrorCode ?? LocalCodes.CardTerminalTimeout, new Dictionary<string, object?> { ["attempt_id"] = a.AttemptId });
        }

        private static CardTxResult Unknown(CardAttempt a) => new CardTxResult
        {
            AttemptId = a.AttemptId,
            Kind = a.Kind,
            Status = CardStatuses.Unknown,
            AmountTiyin = a.AmountTiyin,
        };

        private CardCallResult FinishWithException(CardAttempt attempt, Exception e)
        {
            switch (e)
            {
                case CardTerminalUnreachableException _:
                    return Finish(attempt, new CardTxResult { AttemptId = attempt.AttemptId, Kind = attempt.Kind, Status = CardStatuses.Error, AmountTiyin = attempt.AmountTiyin, DeclineCode = "unreachable" }, 503, LocalCodes.CardTerminalUnreachable, "auto");
                case CardTerminalBusyException _:
                    return Finish(attempt, new CardTxResult { AttemptId = attempt.AttemptId, Kind = attempt.Kind, Status = CardStatuses.Error, AmountTiyin = attempt.AmountTiyin, DeclineCode = "busy" }, 409, LocalCodes.CardTerminalBusy, "auto");
                default:
                    // Sent and no answer (timeout, dropped connection, driver fault): outcome unknown — never resend.
                    _log.Warn("card.outcome.unknown", "card terminal gave no answer: " + e.GetType().Name, Ctx(attempt));
                    return Finish(attempt, Unknown(attempt), 504, LocalCodes.CardTerminalTimeout, "auto");
            }
        }

        private CardCallResult Finish(CardAttempt attempt, CardTxResult result, int http, string? code, string resolvedBy)
        {
            attempt.State = "done";
            attempt.Result = result;
            attempt.HttpStatus = http;
            attempt.ErrorCode = code;
            attempt.ResolvedBy = CardStatuses.IsFinal(result.Status) ? resolvedBy : null;
            _journal.Write("result", attempt);
            _log.Info("card." + attempt.Kind + "." + result.Status, "card " + attempt.Kind + " finished: " + result.Status, Ctx(attempt));
            return http == 200 ? CardCallResult.Ok(result) : CardCallResult.Error(code!, new Dictionary<string, object?> { ["attempt_id"] = attempt.AttemptId });
        }

        private static Dictionary<string, object?> Ctx(CardAttempt a) => new Dictionary<string, object?>
        {
            ["attempt_id"] = a.AttemptId,
            ["kind"] = a.Kind,
            ["local_id"] = a.LocalId,
            ["amount_tiyin"] = a.AmountTiyin,
        };

        // ---------------------------------------------------------------- refund / void

        public Task<CardCallResult> RefundAsync(string localId, CardRefund req, CancellationToken ct) =>
            ReverseAsync(CardKinds.Refund, localId, req.AttemptId, req.AmountTiyin, req.OriginalAttemptId, req.OriginalRrn, ct);

        public Task<CardCallResult> VoidAsync(string localId, CardVoid req, CancellationToken ct) =>
            ReverseAsync(CardKinds.Void, localId, req.AttemptId, req.AmountTiyin, req.OriginalAttemptId, req.OriginalRrn, ct);

        private async Task<CardCallResult> ReverseAsync(string kind, string localId, Guid attemptGuid, long amount, Guid? originalAttempt, string? originalRrn, CancellationToken ct)
        {
            if (!TryResolve(localId, out var cfg, out var drv)) return CardCallResult.Error(LocalCodes.NotFound, new Dictionary<string, object?> { ["local_id"] = localId });
            var attemptId = attemptGuid.ToString("D");
            var existing = _journal.Get(attemptId);
            if (existing != null) return Replay(existing, kind, localId, amount);

            string? rrn = originalRrn;
            CardAttempt? original = null;
            if (originalAttempt.HasValue)
            {
                original = _journal.Get(originalAttempt.Value.ToString("D"));
                if (original?.Result is null || original.Result.Status != CardStatuses.Approved || original.Kind != CardKinds.Purchase)
                {
                    return CardCallResult.Error(LocalCodes.ValidationError, new Dictionary<string, object?> { ["field"] = "original_attempt_id", ["reason"] = "not_found" });
                }

                rrn ??= original.Result.Rrn;

                // Already voided (e.g. the automatic void after CARD_AMOUNT_MISMATCH): answer with that void.
                if (kind == CardKinds.Void && original.VoidedBy != null)
                {
                    var done = _journal.Get(original.VoidedBy);
                    if (done?.Result != null && done.Result.Status == CardStatuses.Approved) return CardCallResult.Ok(done.Result);
                }
            }

            if (rrn is null && original is null)
            {
                return CardCallResult.Error(LocalCodes.ValidationError, new Dictionary<string, object?> { ["field"] = "original_rrn", ["reason"] = "required" });
            }

            if (kind == CardKinds.Void && (drv.Capabilities & DriverCapabilities.Void) == 0)
            {
                return CardCallResult.Error(LocalCodes.CardVoidFailed, new Dictionary<string, object?> { ["reason"] = "not_supported" });
            }

            var lane = _lanes.For(localId);
            using var slot = await lane.EnterAsync(true, ct).ConfigureAwait(false);
            var attempt = new CardAttempt { AttemptId = attemptId, Kind = kind, LocalId = localId, AmountTiyin = amount, OriginalAttemptId = original?.AttemptId, OriginalRrn = rrn };
            if (!_journal.TryCreate(attempt)) return Replay(_journal.Get(attemptId)!, kind, localId, amount);
            attempt.State = "sent";
            _journal.Write("sent", attempt);

            CardTxResult raw;
            try
            {
                using var cts = Timeout(_t.RefundVoid, ct);
                raw = kind == CardKinds.Void
                    ? await drv.VoidAsync(cfg, new CardVoid { AttemptId = attemptGuid, AmountTiyin = amount, OriginalAttemptId = originalAttempt, OriginalRrn = rrn }, cts.Token).ConfigureAwait(false)
                    : await drv.RefundAsync(cfg, new CardRefund { AttemptId = attemptGuid, AmountTiyin = amount, OriginalAttemptId = originalAttempt, OriginalRrn = rrn }, cts.Token).ConfigureAwait(false);
            }
            catch (Exception e)
            {
                return FinishWithException(attempt, e);
            }

            var res = CardNormalizer.Normalize(raw, attemptId, kind);
            if (res.Status == CardStatuses.Approved && res.AmountTiyin is null) res.AmountTiyin = amount;
            if (res.Status == CardStatuses.Timeout || res.Status == CardStatuses.Unknown) return Finish(attempt, Unknown(attempt), 504, LocalCodes.CardTerminalTimeout, "auto");
            if (kind == CardKinds.Void)
            {
                if (res.Status != CardStatuses.Approved) return Finish(attempt, res, 502, LocalCodes.CardVoidFailed, "auto");
                var r = Finish(attempt, res, 200, null, "auto");
                if (original != null) MarkVoided(original.AttemptId, attemptId);
                return r;
            }

            return Finish(attempt, res, 200, null, "auto");
        }

        // ---------------------------------------------------------------- tx status / cancel

        public async Task<CardCallResult> GetTxAsync(string attemptId, CancellationToken ct)
        {
            var a = _journal.Get(attemptId);
            if (a is null) return CardCallResult.Error(LocalCodes.NotFound, new Dictionary<string, object?> { ["attempt_id"] = attemptId });
            if (a.State != "done") return CardCallResult.Ok(Unknown(a));
            if (a.Result != null && a.Result.Status == CardStatuses.Unknown)
            {
                var resolved = await TryResolveUnknownAsync(a, ct).ConfigureAwait(false);
                if (resolved != null) return CardCallResult.Ok(resolved);
                return CardCallResult.Ok(a.Result);
            }

            if (a.Result != null) return CardCallResult.Ok(a.Result);
            return CardCallResult.Ok(Unknown(a));
        }

        /// <summary>
        /// Status query for an unknown attempt (21 §9.4): driver <c>GetStatusAsync</c> (3 tries, 2 s), else
        /// <c>GetLastTransactionAsync</c> matched by ERN (= attempt_id) or amount + time. Never re-sends the purchase.
        /// </summary>
        public async Task<CardTxResult?> TryResolveUnknownAsync(CardAttempt a, CancellationToken ct)
        {
            if (!TryResolve(a.LocalId, out var cfg, out var drv)) return null;
            CardTxResult? found = null;
            for (var i = 0; i < Math.Max(1, _t.SafeTries) && found is null; i++)
            {
                if (i > 0) await _delay(_t.SafeRetryDelay, ct).ConfigureAwait(false);
                try
                {
                    using var cts = Timeout(_t.Status, ct);
                    if ((drv.Capabilities & DriverCapabilities.StatusByErn) != 0)
                    {
                        found = await drv.GetStatusAsync(cfg, Guid.Parse(a.AttemptId), cts.Token).ConfigureAwait(false);
                    }

                    if (found is null && (drv.Capabilities & DriverCapabilities.LastTransaction) != 0)
                    {
                        var last = await drv.GetLastTransactionAsync(cfg, cts.Token).ConfigureAwait(false);
                        if (last != null && Matches(a, last)) found = last;
                    }

                    if (found is null) break; // the terminal answered: it knows nothing more
                }
                catch (OperationCanceledException) when (!ct.IsCancellationRequested)
                {
                }
                catch (CardTerminalException)
                {
                }
            }

            if (found is null || found.Status == CardStatuses.Unknown || found.Status == CardStatuses.Timeout) return null;
            var res = CardNormalizer.Normalize(found, a.AttemptId, a.Kind);
            if (res.Status == CardStatuses.Approved && res.AmountTiyin is null) res.AmountTiyin = a.AmountTiyin;
            var current = _journal.Get(a.AttemptId) ?? a;
            current.Result = res;
            current.HttpStatus = 200;
            current.ErrorCode = null;
            current.ResolvedBy = "status_query";
            current.Reported = false;
            _journal.Write("resolved", current);
            _log.Info("card.outcome.resolved", "unknown card attempt resolved by status query: " + res.Status, Ctx(current));
            return res;
        }

        private static bool Matches(CardAttempt a, CardTxResult last)
        {
            if (!string.IsNullOrEmpty(last.AttemptId)) return string.Equals(last.AttemptId, a.AttemptId, StringComparison.OrdinalIgnoreCase);
            if (last.AmountTiyin != a.AmountTiyin || last.Kind != a.Kind) return false;
            if (!DateTimeOffset.TryParse(last.TxAt, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out var tx)) return false;
            if (!DateTimeOffset.TryParse(a.CreatedAt, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out var created)) return false;
            return tx >= created.AddMinutes(-1) && tx <= created.AddMinutes(5);
        }

        /// <summary><c>POST /v1/card/cancel-pending</c>: "cancelled" | "not_cancellable".</summary>
        public async Task<string> CancelPendingAsync(string attemptId, CancellationToken ct)
        {
            var a = _journal.Get(attemptId);
            if (a is null) throw new LocalApiException(LocalCodes.NotFound, new Dictionary<string, object?> { ["attempt_id"] = attemptId });
            if (a.State != "sent") return "not_cancellable";
            if (!TryResolve(a.LocalId, out var cfg, out var drv) || (drv.Capabilities & DriverCapabilities.CancelPending) == 0) return "not_cancellable";
            try
            {
                using var cts = Timeout(_t.CancelPending, ct);
                await drv.CancelPendingAsync(cfg, Guid.Parse(attemptId), cts.Token).ConfigureAwait(false);
                return "cancelled";
            }
            catch (Exception e) when (e is CardTerminalException || e is OperationCanceledException)
            {
                return "not_cancellable";
            }
        }

        // ---------------------------------------------------------------- settlement

        public async Task<SettlementResult> SettlementAsync(string localId, CancellationToken ct)
        {
            if (!TryResolve(localId, out var cfg, out var drv)) throw new LocalApiException(LocalCodes.NotFound, new Dictionary<string, object?> { ["local_id"] = localId });
            if ((drv.Capabilities & DriverCapabilities.Settlement) == 0) throw LocalApiException.Validation("local_id", "settlement_not_supported");
            var lane = _lanes.For(localId);
            using var slot = await lane.EnterAsync(true, ct).ConfigureAwait(false);
            Exception? last = null;
            for (var i = 0; i < Math.Max(1, _t.SafeTries); i++)
            {
                if (i > 0) await _delay(_t.SafeRetryDelay, ct).ConfigureAwait(false);
                try
                {
                    using var cts = Timeout(_t.Settlement, ct);
                    var r = await drv.SettlementAsync(cfg, cts.Token).ConfigureAwait(false);
                    r.Tid ??= cfg.Tid;
                    if (string.IsNullOrEmpty(r.SettledAt)) r.SettledAt = Now();
                    _journal.WriteSettlement(localId, r);
                    _log.Info("card.settlement", "card terminal settlement done", new Dictionary<string, object?> { ["local_id"] = localId, ["count"] = r.Count, ["total_tiyin"] = r.TotalTiyin });
                    return r;
                }
                catch (CardTerminalBusyException e)
                {
                    throw new LocalApiException(LocalCodes.CardTerminalBusy, e);
                }
                catch (Exception e) when (e is CardTerminalException || (e is OperationCanceledException && !ct.IsCancellationRequested))
                {
                    last = e;
                }
            }

            _log.Warn("card.settlement.failed", "card terminal settlement failed: " + last?.GetType().Name);
            throw new LocalApiException(LocalCodes.CardTerminalUnreachable, new Dictionary<string, object?> { ["local_id"] = localId });
        }

        // ---------------------------------------------------------------- card.status (server task)

        public async Task<(List<TerminalStatusItem> Terminals, List<ResolvedAttempt> Unresolved)> StatusForServerAsync(
            IReadOnlyList<(string? CardTerminalId, string LocalId)> requested, CancellationToken ct)
        {
            var targets = requested.Count > 0
                ? requested.ToList()
                : ActiveTerminals().Select(t => ((string?)null, t.Config.LocalId)).ToList();
            var terminals = new List<TerminalStatusItem>();
            foreach (var (cardTerminalId, localId) in targets)
            {
                if (!TryResolve(localId, out var cfg, out _))
                {
                    terminals.Add(new TerminalStatusItem { CardTerminalId = cardTerminalId, LocalId = localId, Status = "error" });
                    continue;
                }

                var h = await HealthAsync(localId, true, ct).ConfigureAwait(false);
                terminals.Add(new TerminalStatusItem { CardTerminalId = cardTerminalId, LocalId = localId, Status = h.Status, Tid = h.Tid ?? cfg.Tid, LastTxAt = h.LastTxAt ?? LastTxAt(localId) });
            }

            var locals = new HashSet<string>(targets.Select(t => t.LocalId), StringComparer.Ordinal);
            foreach (var a in _journal.All().Where(x => locals.Contains(x.LocalId) && x.State == "done" && x.Result?.Status == CardStatuses.Unknown))
            {
                await TryResolveUnknownAsync(a, ct).ConfigureAwait(false);
            }

            var unresolved = new List<ResolvedAttempt>();
            foreach (var a in _journal.All().Where(x => locals.Contains(x.LocalId) && x.ResolvedBy == "status_query" && !x.Reported && x.Result != null))
            {
                unresolved.Add(ResolvedAttempt.From(a.Result!, a.LocalId));
            }

            return (terminals, unresolved);
        }

        /// <summary>Marks status-query resolutions as reported (after the card.status result is in the outbox).</summary>
        public void MarkReported(IEnumerable<string> attemptIds)
        {
            foreach (var id in attemptIds)
            {
                var a = _journal.Get(id);
                if (a is null || a.Reported) continue;
                a.Reported = true;
                _journal.Write("reported", a);
            }
        }
    }
}

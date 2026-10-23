using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Core.Crypto;
using Erp1C.Core.Errors;
using Erp1C.Core.Hosting;
using Erp1C.Core.Json;
using Erp1C.Core.Security;
using Erp1C.Core.Storage;

#pragma warning disable CA1002

namespace Erp1C.Fiscal
{
    public interface IFiscalConfig
    {
        IReadOnlyList<FiscalDeviceConfig> Devices { get; }

        /// <summary>The <c>fake</c> bridge counts only in a DEV build or on a demo-tenant agent.</summary>
        bool AllowFakeBridge { get; }
    }

    /// <summary>
    /// Agent-side fiscal layer (21 §1, §16, 34 §14.3): device resolution, the 48 h / FM-lock gate, the
    /// <c>fiscal_journal.jsonl</c> idempotency journal (<c>cash_register_id + receipt_seq</c> — the FM never signs the
    /// same sale twice; a fiscal call is never repeated automatically), one FIFO lane per FM.
    /// </summary>
    public sealed class FiscalService
    {
        public static readonly TimeSpan OfflineBlock = TimeSpan.FromHours(48);
        private readonly IFiscalConfig _config;
        private readonly Dictionary<string, IFiscalBridge> _bridges;
        private readonly JsonlFile _journal;
        private readonly DeviceLanes _lanes;
        private readonly IClock _clock;
        private readonly IAgentLogger _log;
        private readonly object _lock = new object();
        private readonly Dictionary<string, JournalRow> _byKey = new Dictionary<string, JournalRow>(StringComparer.Ordinal);
        private readonly Dictionary<string, string> _registerToLocal = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        private readonly HashSet<string> _ackReported = new HashSet<string>(StringComparer.Ordinal);

        public FiscalService(IFiscalConfig config, IEnumerable<IFiscalBridge> bridges, string journalPath, DeviceLanes lanes, IClock clock, IAgentLogger? log = null)
        {
            _config = config;
            _bridges = bridges.ToDictionary(b => b.Provider, StringComparer.Ordinal);
            _journal = new JsonlFile(journalPath);
            _lanes = lanes;
            _clock = clock;
            _log = log ?? NullAgentLogger.Instance;
            Load();
        }

        internal sealed class JournalRow
        {
            public int V { get; set; } = 1;

            public string E { get; set; } = string.Empty;

            public string At { get; set; } = string.Empty;

            public string? Key { get; set; }

            public string? Hash { get; set; }

            public string? CashRegisterId { get; set; }

            public string? LocalId { get; set; }

            public FiscalResult? Result { get; set; }

            public List<string>? Acked { get; set; }
        }

        private void Load()
        {
            foreach (var line in _journal.ReadLines())
            {
                JournalRow? r;
                try
                {
                    r = AgentJson.Deserialize<JournalRow>(line);
                }
                catch (JsonException)
                {
                    continue;
                }

                if (r is null) continue;
                if (r.E == "map" && r.CashRegisterId != null && r.LocalId != null) _registerToLocal[r.CashRegisterId] = r.LocalId;
                if ((r.E == "sent" || r.E == "result") && r.Key != null) _byKey[r.Key] = r;
                if (r.E == "acked_reported" && r.Acked != null) foreach (var a in r.Acked) _ackReported.Add(a);
            }
        }

        private void Append(JournalRow row)
        {
            row.At = Iso(_clock.UtcNow);
            _journal.Append(AgentJson.Serialize(row));
        }

        private static string Iso(DateTimeOffset t) => t.UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture);

        public IReadOnlyList<(FiscalDeviceConfig Device, IFiscalBridge Bridge)> Active()
        {
            var list = new List<(FiscalDeviceConfig, IFiscalBridge)>();
            foreach (var d in _config.Devices)
            {
                if (!_bridges.TryGetValue(d.Provider, out var b) || !b.Available) continue;
                if (b.Provider == "fake" && !_config.AllowFakeBridge) continue;
                list.Add((d, b));
            }

            return list;
        }

        public (FiscalDeviceConfig Device, IFiscalBridge Bridge) Resolve(string? localId)
        {
            var hit = Active().FirstOrDefault(x => string.Equals(x.Device.LocalId, localId, StringComparison.Ordinal));
            if (hit.Device is null) throw new LocalApiException(LocalCodes.NotFound, new Dictionary<string, object?> { ["local_id"] = localId });
            return hit;
        }

        /// <summary>Remembers cash_register_id → local_id from POS calls (fallback when a task payload has no local_id).</summary>
        public void Learn(CashRegisterRef r)
        {
            if (string.IsNullOrEmpty(r.CashRegisterId) || string.IsNullOrEmpty(r.LocalId)) return;
            lock (_lock)
            {
                if (_registerToLocal.TryGetValue(r.CashRegisterId, out var known) && known == r.LocalId) return;
                _registerToLocal[r.CashRegisterId] = r.LocalId;
                Append(new JournalRow { E = "map", CashRegisterId = r.CashRegisterId, LocalId = r.LocalId });
            }
        }

        public string? LocalIdFor(string cashRegisterId)
        {
            lock (_lock) return _registerToLocal.TryGetValue(cashRegisterId, out var l) ? l : null;
        }

        private static LocalApiException Map(FiscalProviderException e)
        {
            switch (e)
            {
                case FiscalDeviceLockedException _:
                    return new LocalApiException(LocalCodes.FiscalDeviceLocked, e);
                case FiscalShiftStateException s:
                    return new LocalApiException(s.AlreadyOpen ? LocalCodes.ShiftAlreadyOpen : LocalCodes.ShiftNotOpen, e);
                default:
                    return new LocalApiException(LocalCodes.FiscalProviderError, e);
            }
        }

        private async Task<T> Call<T>(string localId, Func<FiscalDeviceConfig, IFiscalBridge, CancellationToken, Task<T>> f, CancellationToken ct)
        {
            var (d, b) = Resolve(localId);
            using (await _lanes.For("fiscal:" + d.LocalId).EnterAsync(true, ct).ConfigureAwait(false))
            {
                try
                {
                    return await f(d, b, ct).ConfigureAwait(false);
                }
                catch (FiscalProviderException e)
                {
                    _log.Warn("fiscal.provider_error", "fiscal bridge error: " + e.Message, new Dictionary<string, object?> { ["local_id"] = localId });
                    throw Map(e);
                }
            }
        }

        public Task<FiscalShiftResult> OpenShiftAsync(CashRegisterRef register, long shiftNo, string cashierName, CancellationToken ct)
        {
            Learn(register);
            return Call(register.LocalId, (d, b, c) => b.OpenShiftAsync(d, shiftNo, cashierName, c), ct);
        }

        public Task<ZReport> CloseShiftAsync(CashRegisterRef register, long? shiftNo, CancellationToken ct)
        {
            Learn(register);
            return Call(register.LocalId, (d, b, c) => b.CloseShiftAsync(d, shiftNo, c), ct);
        }

        /// <summary>
        /// Signs a sale / refund once per <c>(cash_register_id, receipt_seq)</c>: a repeated request with the same body
        /// answers from the journal; a different body → RECEIPT_SEQ_CONFLICT; an interrupted earlier call is resolved
        /// through the FM's own record before anything is signed again.
        /// </summary>
        public async Task<FiscalResult> RegisterAsync(FiscalReceiptPayload receipt, JsonElement rawBody, bool refund, CancellationToken ct)
        {
            Learn(receipt.CashRegister);
            var key = "rcpt|" + receipt.CashRegister.CashRegisterId.ToLowerInvariant() + "|" + receipt.ReceiptSeq.ToString(CultureInfo.InvariantCulture);
            var hash = Hashing.Sha256Hex(Jcs.Canonicalize(rawBody));
            var (d, b) = Resolve(receipt.CashRegister.LocalId);
            using (await _lanes.For("fiscal:" + d.LocalId).EnterAsync(true, ct).ConfigureAwait(false))
            {
                JournalRow? prev;
                lock (_lock) _byKey.TryGetValue(key, out prev);
                if (prev != null)
                {
                    if (prev.Hash != hash) throw new LocalApiException(LocalCodes.ReceiptSeqConflict, new Dictionary<string, object?> { ["receipt_seq"] = receipt.ReceiptSeq });
                    if (prev.Result != null) return prev.Result;

                    // An earlier call was interrupted after it was handed to the FM: ask the FM before signing.
                    FiscalResult? found;
                    try
                    {
                        found = await b.FindReceiptAsync(d, receipt.CashRegister.CashRegisterId, receipt.ReceiptSeq, ct).ConfigureAwait(false);
                    }
                    catch (FiscalProviderException)
                    {
                        // The FM cannot tell whether it signed it — never sign blindly a second time.
                        throw new LocalApiException(LocalCodes.FiscalProviderError, new Dictionary<string, object?> { ["reason"] = "outcome_unknown", ["receipt_seq"] = receipt.ReceiptSeq });
                    }

                    if (found != null)
                    {
                        Store(key, hash, receipt, found);
                        return found;
                    }
                }

                try
                {
                    var status = await b.GetDeviceStatusAsync(d, ct).ConfigureAwait(false);
                    Gate(status);
                    lock (_lock)
                    {
                        var sent = new JournalRow { E = "sent", Key = key, Hash = hash, CashRegisterId = receipt.CashRegister.CashRegisterId, LocalId = d.LocalId };
                        Append(sent);
                        _byKey[key] = sent;
                    }

                    var r = refund
                        ? await b.RegisterRefundAsync(d, receipt, ct).ConfigureAwait(false)
                        : await b.RegisterSaleAsync(d, receipt, ct).ConfigureAwait(false);
                    Store(key, hash, receipt, r);
                    _log.Info("fiscal.receipt.signed", "fiscal receipt signed", new Dictionary<string, object?> { ["local_id"] = d.LocalId, ["receipt_seq"] = receipt.ReceiptSeq, ["fm_receipt_seq"] = r.FmReceiptSeq });
                    return r;
                }
                catch (FiscalProviderException e)
                {
                    _log.Warn("fiscal.provider_error", "fiscal bridge error: " + e.Message, new Dictionary<string, object?> { ["local_id"] = d.LocalId });
                    throw Map(e);
                }
            }
        }

        private void Store(string key, string hash, FiscalReceiptPayload receipt, FiscalResult r)
        {
            lock (_lock)
            {
                var row = new JournalRow { E = "result", Key = key, Hash = hash, CashRegisterId = receipt.CashRegister.CashRegisterId, LocalId = receipt.CashRegister.LocalId, Result = r };
                Append(row);
                _byKey[key] = row;
            }
        }

        /// <summary>FM lock → FISCAL_DEVICE_LOCKED; oldest unacknowledged receipt ≥ 48 h → FISCAL_OFFLINE_48H_BLOCKED (qaror #43).</summary>
        private void Gate(FiscalDeviceStatus status)
        {
            if (status.FmState != "ok") throw new LocalApiException(LocalCodes.FiscalDeviceLocked, new Dictionary<string, object?> { ["fm_state"] = status.FmState });
            if (status.OldestUnackedAt != null
                && DateTimeOffset.TryParse(status.OldestUnackedAt, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out var oldest)
                && _clock.UtcNow - oldest >= OfflineBlock)
            {
                throw new LocalApiException(LocalCodes.FiscalOffline48hBlocked, new Dictionary<string, object?> { ["oldest_unacked_at"] = status.OldestUnackedAt });
            }
        }

        public Task<FiscalDeviceStatus> DeviceStatusAsync(string localId, CancellationToken ct) =>
            Call(localId, (d, b, c) => b.GetDeviceStatusAsync(d, c), ct);

        public Task<IReadOnlyList<UnsentReceipt>> UnsentAsync(string localId, CancellationToken ct) =>
            Call(localId, (d, b, c) => b.ListUnsentAsync(d, c), ct);

        public Task<ResendResult> ResendAsync(string localId, CancellationToken ct) =>
            Call(localId, (d, b, c) => b.ResendUnsentAsync(d, c), ct);

        /// <summary>Acknowledgements not reported to the server yet (fiscal.status result <c>acked[]</c>).</summary>
        public List<AckedReceipt> NewAcks(IEnumerable<AckedReceipt> acked)
        {
            lock (_lock) return acked.Where(a => !_ackReported.Contains(a.FmTerminalId + "|" + a.FmReceiptSeq.ToString(CultureInfo.InvariantCulture))).ToList();
        }

        public void MarkAcksReported(IEnumerable<AckedReceipt> acked)
        {
            var keys = acked.Select(a => a.FmTerminalId + "|" + a.FmReceiptSeq.ToString(CultureInfo.InvariantCulture)).ToList();
            if (keys.Count == 0) return;
            lock (_lock)
            {
                foreach (var k in keys) _ackReported.Add(k);
                Append(new JournalRow { E = "acked_reported", Acked = keys });
            }
        }

        /// <summary>fiscal.zreport: closes the FM shift if the POS did not, otherwise returns the last Z-report.</summary>
        public Task<ZReport> ZReportAsync(string localId, CancellationToken ct) =>
            Call(localId, async (d, b, c) =>
            {
                var (open, last) = await b.ShiftStateAsync(d, c).ConfigureAwait(false);
                if (open) return await b.CloseShiftAsync(d, null, c).ConfigureAwait(false);
                return last ?? throw new FiscalShiftStateException("no shift on the FM") { AlreadyOpen = false };
            }, ct);
    }
}

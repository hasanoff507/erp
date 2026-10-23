using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Core.Json;
using Erp1C.Core.Security;
using Erp1C.Core.Storage;

#pragma warning disable CA1002
#pragma warning disable CA2227

namespace Erp1C.Fiscal
{
    /// <summary>
    /// Fake partner local service + FM emulator (21 §1 <c>FakeFiscalAdapter</c> rules, 34 §14): terminal id
    /// <c>ZZ</c> + 12 digits, increasing <c>fm_receipt_seq</c>, random 12-digit <c>fiscal_sign</c>, real-format
    /// <c>qr_url</c>, signs offline; OFD acknowledgement at once while <see cref="OfdOnline"/> (tests turn it off
    /// to accumulate unsent receipts). Not a real partner protocol (⛔ 26 #109). State persists to a JSON file.
    /// </summary>
    public sealed class FakeFiscalBridge : IFiscalBridge
    {
        private readonly object _lock = new object();
        private readonly string? _statePath;
        private readonly IClock _clock;
        private readonly Dictionary<string, FakeFm> _devices;

        public FakeFiscalBridge(IClock clock, string? statePath = null)
        {
            _clock = clock;
            _statePath = statePath;
            _devices = Load();
        }

        public string Provider => "fake";

        public bool Available => true;

        /// <summary>OFD reachable — receipts are acknowledged immediately.</summary>
        public bool OfdOnline { get; set; } = true;

        /// <summary>Forced FM state (null → computed: ok).</summary>
        public string? ForcedFmState { get; set; }

        public int SaleCalls { get; private set; }

        private sealed class FakeFm
        {
            public string TerminalId { get; set; } = string.Empty;

            public long NextSeq { get; set; } = 1;

            public bool ShiftOpen { get; set; }

            public long ShiftNo { get; set; }

            public string? OpenedAt { get; set; }

            public long ZNumber { get; set; }

            public ZReport? LastZ { get; set; }

            public long LastClosedShiftNo { get; set; }

            public List<FakeReceipt> Receipts { get; set; } = new List<FakeReceipt>();
        }

        private sealed class FakeReceipt
        {
            public long Seq { get; set; }

            public string CashRegisterId { get; set; } = string.Empty;

            public long ReceiptSeq { get; set; }

            public string Kind { get; set; } = "sale";

            public long AmountTiyin { get; set; }

            public string PaymentForm { get; set; } = "cash";

            public long CashTiyin { get; set; }

            public long CardTiyin { get; set; }

            public long QrTiyin { get; set; }

            public long ShiftNo { get; set; }

            public string FiscalAt { get; set; } = string.Empty;

            public string FiscalSign { get; set; } = string.Empty;

            public string QrUrl { get; set; } = string.Empty;

            public string? AckedAt { get; set; }
        }

        private Dictionary<string, FakeFm> Load()
        {
            if (_statePath is null || !File.Exists(_statePath)) return new Dictionary<string, FakeFm>(StringComparer.Ordinal);
            try
            {
                return AgentJson.Deserialize<Dictionary<string, FakeFm>>(File.ReadAllText(_statePath)) ?? new Dictionary<string, FakeFm>(StringComparer.Ordinal);
            }
            catch (System.Text.Json.JsonException)
            {
                return new Dictionary<string, FakeFm>(StringComparer.Ordinal);
            }
        }

        private void Save()
        {
            if (_statePath is null) return;
            AtomicFile.WriteAllText(_statePath, AgentJson.Serialize(_devices));
        }

        private static string Iso(DateTimeOffset t) => t.UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture);

        private FakeFm Fm(FiscalDeviceConfig d)
        {
            if (!_devices.TryGetValue(d.LocalId, out var fm))
            {
                using var sha = SHA256.Create();
                var h = sha.ComputeHash(Encoding.UTF8.GetBytes(d.LocalId));
                var n = BitConverter.ToUInt64(h, 0) % 1000000000000UL;
                fm = new FakeFm { TerminalId = "ZZ" + n.ToString("D12", CultureInfo.InvariantCulture) };
                _devices[d.LocalId] = fm;
            }

            return fm;
        }

        private static string RandomSign()
        {
            var b = new byte[8];
            using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(b);
            var n = BitConverter.ToUInt64(b, 0) % 1000000000000UL;
            return n.ToString("D12", CultureInfo.InvariantCulture);
        }

        private string State(FakeFm fm) => ForcedFmState ?? "ok";

        private void CheckSignable(FakeFm fm)
        {
            var s = State(fm);
            if (s != "ok") throw new FiscalDeviceLockedException("fake FM state " + s);
        }

        public Task<FiscalShiftResult> OpenShiftAsync(FiscalDeviceConfig device, long shiftNo, string cashierName, CancellationToken ct)
        {
            lock (_lock)
            {
                var fm = Fm(device);
                CheckSignable(fm);
                if (fm.ShiftOpen)
                {
                    if (fm.ShiftNo == shiftNo) return Task.FromResult(new FiscalShiftResult { FmTerminalId = fm.TerminalId, OpenedAt = fm.OpenedAt! });
                    throw new FiscalShiftStateException("shift already open") { AlreadyOpen = true };
                }

                fm.ShiftOpen = true;
                fm.ShiftNo = shiftNo;
                fm.OpenedAt = Iso(_clock.UtcNow);
                Save();
                return Task.FromResult(new FiscalShiftResult { FmTerminalId = fm.TerminalId, OpenedAt = fm.OpenedAt });
            }
        }

        public Task<ZReport> CloseShiftAsync(FiscalDeviceConfig device, long? shiftNo, CancellationToken ct)
        {
            lock (_lock)
            {
                var fm = Fm(device);
                if (!fm.ShiftOpen)
                {
                    if (fm.LastZ != null && (shiftNo is null || fm.LastClosedShiftNo == shiftNo)) return Task.FromResult(fm.LastZ);
                    throw new FiscalShiftStateException("shift not open") { AlreadyOpen = false };
                }

                if (shiftNo.HasValue && fm.ShiftNo != shiftNo) throw new FiscalShiftStateException("another shift is open") { AlreadyOpen = true };
                var inShift = fm.Receipts.Where(r => r.ShiftNo == fm.ShiftNo).ToList();
                var totals = new ZTotals
                {
                    Sale = inShift.Where(r => r.Kind != "return").Sum(r => r.AmountTiyin),
                    Return = inShift.Where(r => r.Kind == "return").Sum(r => r.AmountTiyin),
                };
                foreach (var g in inShift.Where(r => r.Kind != "return"))
                {
                    Add(totals.ByPaymentForm, "cash", g.CashTiyin);
                    Add(totals.ByPaymentForm, "card", g.CardTiyin);
                    Add(totals.ByPaymentForm, "qr", g.QrTiyin);
                }

                fm.ZNumber++;
                var z = new ZReport { FmTerminalId = fm.TerminalId, ZNumber = fm.ZNumber, Totals = totals, ClosedAt = Iso(_clock.UtcNow) };
                fm.LastZ = z;
                fm.LastClosedShiftNo = fm.ShiftNo;
                fm.ShiftOpen = false;
                Save();
                return Task.FromResult(z);
            }
        }

        private static void Add(Dictionary<string, long> d, string k, long v)
        {
            if (v == 0) return;
            d[k] = (d.TryGetValue(k, out var x) ? x : 0) + v;
        }

        public Task<FiscalResult> RegisterSaleAsync(FiscalDeviceConfig device, FiscalReceiptPayload receipt, CancellationToken ct) => Register(device, receipt);

        public Task<FiscalResult> RegisterRefundAsync(FiscalDeviceConfig device, FiscalReceiptPayload receipt, CancellationToken ct) => Register(device, receipt);

        private Task<FiscalResult> Register(FiscalDeviceConfig device, FiscalReceiptPayload receipt)
        {
            lock (_lock)
            {
                SaleCalls++;
                var fm = Fm(device);
                CheckSignable(fm);
                if (!fm.ShiftOpen) throw new FiscalShiftStateException("shift not open") { AlreadyOpen = false };
                var now = _clock.UtcNow;
                var seq = fm.NextSeq++;
                var sign = RandomSign();
                var c = now.UtcDateTime.ToString("yyyyMMddHHmmss", CultureInfo.InvariantCulture);
                var r = new FakeReceipt
                {
                    Seq = seq,
                    CashRegisterId = receipt.CashRegister.CashRegisterId,
                    ReceiptSeq = receipt.ReceiptSeq,
                    Kind = receipt.Kind,
                    AmountTiyin = receipt.TotalTiyin(),
                    PaymentForm = receipt.Payments.PaymentForm,
                    CashTiyin = receipt.Payments.CashTiyin,
                    CardTiyin = receipt.Payments.CardTiyin,
                    QrTiyin = receipt.Payments.QrTiyin,
                    ShiftNo = fm.ShiftNo,
                    FiscalAt = Iso(now),
                    FiscalSign = sign,
                    QrUrl = "https://ofd.soliq.uz/check?t=" + fm.TerminalId + "&r=" + seq.ToString(CultureInfo.InvariantCulture) + "&c=" + c + "&s=" + sign,
                    AckedAt = OfdOnline ? Iso(now) : null,
                };
                fm.Receipts.Add(r);
                Save();
                return Task.FromResult(ToResult(fm, r));
            }
        }

        private static FiscalResult ToResult(FakeFm fm, FakeReceipt r) => new FiscalResult
        {
            FmTerminalId = fm.TerminalId,
            FmReceiptSeq = r.Seq,
            FiscalSign = r.FiscalSign,
            QrUrl = r.QrUrl,
            FiscalAt = r.FiscalAt,
        };

        public Task<FiscalDeviceStatus> GetDeviceStatusAsync(FiscalDeviceConfig device, CancellationToken ct)
        {
            lock (_lock)
            {
                var fm = Fm(device);
                var unacked = fm.Receipts.Where(r => r.AckedAt == null).OrderBy(r => r.Seq).ToList();
                return Task.FromResult(new FiscalDeviceStatus
                {
                    FmState = State(fm),
                    PendingCount = unacked.Count,
                    OldestUnackedAt = unacked.FirstOrDefault()?.FiscalAt,
                    Acked = fm.Receipts.Where(r => r.AckedAt != null).Select(r => new AckedReceipt { FmTerminalId = fm.TerminalId, FmReceiptSeq = r.Seq, AckedAt = r.AckedAt! }).ToList(),
                });
            }
        }

        public Task<IReadOnlyList<UnsentReceipt>> ListUnsentAsync(FiscalDeviceConfig device, CancellationToken ct)
        {
            lock (_lock)
            {
                var fm = Fm(device);
                IReadOnlyList<UnsentReceipt> list = fm.Receipts.Where(r => r.AckedAt == null).OrderBy(r => r.Seq)
                    .Select(r => new UnsentReceipt { FmReceiptSeq = r.Seq, FiscalAt = r.FiscalAt, AmountTiyin = r.AmountTiyin }).ToList();
                return Task.FromResult(list);
            }
        }

        public Task<ResendResult> ResendUnsentAsync(FiscalDeviceConfig device, CancellationToken ct)
        {
            lock (_lock)
            {
                var fm = Fm(device);
                var unacked = fm.Receipts.Where(r => r.AckedAt == null).OrderBy(r => r.Seq).ToList();
                var result = new ResendResult();
                if (!OfdOnline)
                {
                    result.Failed = unacked.Count;
                    return Task.FromResult(result);
                }

                var now = Iso(_clock.UtcNow);
                foreach (var r in unacked)
                {
                    r.AckedAt = now;
                    result.Sent++;
                    result.Acked.Add(new AckedReceipt { FmTerminalId = fm.TerminalId, FmReceiptSeq = r.Seq, AckedAt = now });
                }

                Save();
                return Task.FromResult(result);
            }
        }

        public Task<FiscalResult?> FindReceiptAsync(FiscalDeviceConfig device, string cashRegisterId, long receiptSeq, CancellationToken ct)
        {
            lock (_lock)
            {
                var fm = Fm(device);
                var r = fm.Receipts.LastOrDefault(x => x.CashRegisterId == cashRegisterId && x.ReceiptSeq == receiptSeq);
                return Task.FromResult(r is null ? null : ToResult(fm, r));
            }
        }

        public Task<(bool ShiftOpen, ZReport? LastZ)> ShiftStateAsync(FiscalDeviceConfig device, CancellationToken ct)
        {
            lock (_lock)
            {
                var fm = Fm(device);
                return Task.FromResult((fm.ShiftOpen, fm.LastZ));
            }
        }

        /// <summary>Test hook: age every unacknowledged receipt (48 h offline block scenarios).</summary>
        public void BackdateUnacked(TimeSpan by)
        {
            lock (_lock)
            {
                foreach (var fm in _devices.Values)
                {
                    foreach (var r in fm.Receipts.Where(x => x.AckedAt == null))
                    {
                        var t = DateTimeOffset.Parse(r.FiscalAt, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal);
                        r.FiscalAt = Iso(t - by);
                    }
                }
            }
        }
    }
}

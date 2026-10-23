using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using Erp1C.Core.Json;
using Erp1C.Core.Security;
using Erp1C.Core.Storage;

namespace Erp1C.CardTerminal
{
    /// <summary>Journal state of one card attempt (attempt_id is the idempotency key, 21 §9.4).</summary>
    public sealed class CardAttempt
    {
        public string AttemptId { get; set; } = string.Empty;

        public string Kind { get; set; } = CardKinds.Purchase;

        public string LocalId { get; set; } = string.Empty;

        public long AmountTiyin { get; set; }

        public string? OriginalAttemptId { get; set; }

        public string? OriginalRrn { get; set; }

        /// <summary>created → sent → done (the driver call happens only between sent and done).</summary>
        public string State { get; set; } = "created";

        public CardTxResult? Result { get; set; }

        /// <summary>HTTP status of the local API answer (replayed for the same attempt_id).</summary>
        public int HttpStatus { get; set; }

        public string? ErrorCode { get; set; }

        /// <summary>auto | status_query | manager (21 §9.4).</summary>
        public string? ResolvedBy { get; set; }

        public string? VoidedBy { get; set; }

        /// <summary>A status-query resolution already reported to the server in a card.status result.</summary>
        public bool Reported { get; set; }

        public string CreatedAt { get; set; } = string.Empty;

        public string UpdatedAt { get; set; } = string.Empty;

        public CardAttempt Clone()
        {
            var c = (CardAttempt)MemberwiseClone();
            c.Result = Result?.Clone();
            return c;
        }
    }

    internal sealed class JournalLine
    {
        public int V { get; set; } = 1;

        public string E { get; set; } = string.Empty;

        public string At { get; set; } = string.Empty;

        public CardAttempt? Attempt { get; set; }

        public string? LocalId { get; set; }

        public SettlementResult? Settlement { get; set; }
    }

    /// <summary>
    /// <c>card_journal.jsonl</c> (34 §14.4): append-only, fsync per line, no DPAPI but no secrets either — only the
    /// mask, RRN, approval code, scheme, type, tid and amounts. Kept 90 days.
    /// </summary>
    public sealed class CardJournal
    {
        public static readonly TimeSpan Retention = TimeSpan.FromDays(90);
        private readonly JsonlFile _file;
        private readonly IClock _clock;
        private readonly object _lock = new object();
        private readonly Dictionary<string, CardAttempt> _byId = new Dictionary<string, CardAttempt>(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, SettlementResult> _lastSettlement = new Dictionary<string, SettlementResult>(StringComparer.Ordinal);

        public CardJournal(string path, IClock clock)
        {
            _file = new JsonlFile(path);
            _clock = clock;
            Load();
        }

        public string Path => _file.Path;

        private void Load()
        {
            var cutoff = _clock.UtcNow - Retention;
            var kept = new List<string>();
            var dropped = false;
            foreach (var line in _file.ReadLines())
            {
                JournalLine? j;
                try
                {
                    j = AgentJson.Deserialize<JournalLine>(line);
                }
                catch (JsonException)
                {
                    dropped = true;
                    continue;
                }

                if (j is null) continue;
                if (DateTimeOffset.TryParse(j.At, System.Globalization.CultureInfo.InvariantCulture, System.Globalization.DateTimeStyles.AssumeUniversal, out var at) && at < cutoff)
                {
                    dropped = true;
                    continue;
                }

                kept.Add(line);
                if (j.Attempt != null) _byId[j.Attempt.AttemptId] = j.Attempt;
                if (j.Settlement != null && j.LocalId != null) _lastSettlement[j.LocalId] = j.Settlement;
            }

            if (dropped) _file.Rewrite(kept);
        }

        public CardAttempt? Get(string attemptId)
        {
            lock (_lock) return _byId.TryGetValue(attemptId, out var a) ? a.Clone() : null;
        }

        public IReadOnlyList<CardAttempt> All()
        {
            lock (_lock) return _byId.Values.Select(a => a.Clone()).ToList();
        }

        /// <summary>Writes the new state of an attempt (fsync before returning).</summary>
        public void Write(string evt, CardAttempt attempt)
        {
            var now = Iso(_clock.UtcNow);
            var a = attempt.Clone();
            if (string.IsNullOrEmpty(a.CreatedAt)) a.CreatedAt = now;
            a.UpdatedAt = now;
            lock (_lock)
            {
                _file.Append(AgentJson.Serialize(new JournalLine { E = evt, At = now, Attempt = a }));
                _byId[a.AttemptId] = a;
            }
        }

        /// <summary>Adds the attempt only if its id is new (idempotency); false when it already exists.</summary>
        public bool TryCreate(CardAttempt attempt)
        {
            lock (_lock)
            {
                if (_byId.ContainsKey(attempt.AttemptId)) return false;
                Write("created", attempt);
                return true;
            }
        }

        public void WriteSettlement(string localId, SettlementResult result)
        {
            var now = Iso(_clock.UtcNow);
            lock (_lock)
            {
                _file.Append(AgentJson.Serialize(new JournalLine { E = "settlement", At = now, LocalId = localId, Settlement = result }));
                _lastSettlement[localId] = result;
            }
        }

        public SettlementResult? LastSettlement(string localId)
        {
            lock (_lock) return _lastSettlement.TryGetValue(localId, out var s) ? s : null;
        }

        public static string Iso(DateTimeOffset t) => t.UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ss.fffZ", System.Globalization.CultureInfo.InvariantCulture);
    }
}

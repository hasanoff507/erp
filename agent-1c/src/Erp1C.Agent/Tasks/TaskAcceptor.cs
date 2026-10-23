using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Agent.State;
using Erp1C.Core.Contracts;
using Erp1C.Core.Crypto;
using Erp1C.Core.Errors;
using Erp1C.Core.Hosting;
using Erp1C.Core.Json;
using Erp1C.Core.Security;
using Erp1C.Core.Trust;

namespace Erp1C.Agent.Tasks
{
    /// <summary>A parsed task envelope (33 §9.3 A-03).</summary>
    public sealed class TaskEnvelope
    {
        public string TaskId { get; set; } = string.Empty;

        public string Kind { get; set; } = string.Empty;

        public string? Purpose { get; set; }

        public string? BaseId { get; set; }

        public string? LocalId { get; set; }

        public int Attempt { get; set; }

        public string LeaseId { get; set; } = string.Empty;

        public string? LeaseUntil { get; set; }

        public int TimeoutS { get; set; }

        public JsonElement Payload { get; set; }

        public string PayloadSha256 { get; set; } = string.Empty;

        public string Kid { get; set; } = string.Empty;

        public string Signature { get; set; } = string.Empty;
    }

    public enum AcceptDecision
    {
        Accepted,
        Rejected,
        Replay,
        Dropped,
    }

    public sealed class AcceptResult
    {
        public AcceptDecision Decision { get; set; }

        public TaskEnvelope? Envelope { get; set; }

        public IAgentTaskHandler? Handler { get; set; }

        /// <summary>signature | agent | tenant | base | expired | payload_hash | kind | schema.</summary>
        public string? Reason { get; set; }

        public string? Field { get; set; }

        /// <summary>The A-05 body to put in the outbox (rejection or replayed journal result).</summary>
        public ResultBody? Result { get; set; }
    }

    /// <summary>The task keyset the acceptor trusts, with the one-time A-08 refresh for an unknown kid (34 §5.5).</summary>
    public interface ITaskKeyProvider
    {
        TaskKeyset? Current { get; }

        /// <summary>A-08 refresh; returns the verified keyset or null.</summary>
        Task<TaskKeyset?> RefreshAsync(CancellationToken ct);
    }

    /// <summary>
    /// 33 §9.11 / 34 §7.5 — every envelope is checked in this exact order; the first failure decides:
    /// 0 envelope fields → 1 signature (kid in keyset, key validity, Ed25519 over the received <c>seg0.seg1</c>) →
    /// 2 claims → 3 base → 4 expiry (±120 s) → 5 payload hash (JCS) → 6 journal (finished → replay) →
    /// 7 write locks (no store-agent kind writes) → 8 payload schema (strict, no non-integer numbers).
    /// </summary>
    public sealed class TaskAcceptor
    {
        public const string Issuer = "urn:erp:onec";
        public const string TaskTyp = "onec-task+jwt";
        private static readonly TimeSpan Skew = TimeSpan.FromSeconds(120);
        private static readonly Regex Hex64 = new Regex("^[0-9a-f]{64}$", RegexOptions.CultureInvariant);

        private readonly ITaskKeyProvider _keys;
        private readonly IReadOnlyDictionary<string, IAgentTaskHandler> _handlers;
        private readonly ActionJournal _journal;
        private readonly IClock _clock;
        private readonly Func<string?> _agentId;
        private readonly Func<string?> _tenantId;

        public TaskAcceptor(ITaskKeyProvider keys, IEnumerable<IAgentTaskHandler> handlers, ActionJournal journal, IClock clock, Func<string?> agentId, Func<string?> tenantId)
        {
            _keys = keys;
            _journal = journal;
            _clock = clock;
            _agentId = agentId;
            _tenantId = tenantId;
            var map = new Dictionary<string, IAgentTaskHandler>(StringComparer.Ordinal);
            foreach (var h in handlers)
            {
                foreach (var k in h.Kinds)
                {
                    if (map.ContainsKey(k)) throw new InvalidOperationException("two handlers for kind " + k);
                    map[k] = h;
                }
            }

            _handlers = map;
        }

        public IReadOnlyCollection<string> KnownKinds => _handlers.Keys.ToList();

        public async Task<AcceptResult> AcceptAsync(JsonElement raw, CancellationToken ct)
        {
            // 0 — envelope shape
            var env = ParseEnvelope(raw, out var shapeField);
            if (env is null)
            {
                var taskId = Str(raw, "task_id");
                var leaseId = Str(raw, "lease_id");
                var attempt = raw.ValueKind == JsonValueKind.Object && raw.TryGetProperty("attempt", out var at) && at.ValueKind == JsonValueKind.Number && at.TryGetInt32(out var a) ? a : 0;
                if (taskId is null || leaseId is null) return new AcceptResult { Decision = AcceptDecision.Dropped, Reason = RejectReasons.Schema, Field = shapeField };
                return Reject(new TaskEnvelope { TaskId = taskId, LeaseId = leaseId, Attempt = attempt }, RejectReasons.Schema, shapeField);
            }

            var now = _clock.UtcNow;

            // 1 — signature
            JwsParts jws;
            try
            {
                jws = CompactJws.Parse(env.Signature);
            }
            catch (JwsFormatException)
            {
                return Reject(env, RejectReasons.Signature, "signature");
            }

            if (jws.Alg != "EdDSA" || jws.Typ != TaskTyp || jws.Kid != env.Kid) return Reject(env, RejectReasons.Signature, "signature");
            var key = _keys.Current?.Find(env.Kid);
            if (key is null)
            {
                var refreshed = await _keys.RefreshAsync(ct).ConfigureAwait(false);
                key = refreshed?.Find(env.Kid);
            }

            if (key is null) return Reject(env, RejectReasons.Signature, "kid");
            if (key.NotBefore.HasValue && key.NotBefore.Value > now + Skew) return Reject(env, RejectReasons.Signature, "kid");
            if (key.Expires.HasValue && key.Expires.Value < now - Skew) return Reject(env, RejectReasons.Signature, "kid");
            if (!Ed25519.Verify(key.X, jws.SigningInput, jws.Signature)) return Reject(env, RejectReasons.Signature, "signature");

            JsonElement claims;
            try
            {
                claims = jws.PayloadJson();
            }
            catch (JwsFormatException)
            {
                return Reject(env, RejectReasons.Signature, "signature");
            }

            // 2 — claims
            var agentId = _agentId();
            if (Str(claims, "iss") != Issuer) return Reject(env, RejectReasons.Agent, "iss");
            if (agentId is null || !Same(Str(claims, "aud"), "urn:erp:onec-agent:" + agentId) || !Same(Str(claims, "aid"), agentId)) return Reject(env, RejectReasons.Agent, "aud");
            var tenantId = _tenantId();
            if (tenantId is null || !Same(Str(claims, "ten"), tenantId)) return Reject(env, RejectReasons.Tenant, "ten");
            if (!Same(Str(claims, "tid"), env.TaskId) || !Same(Str(claims, "lid"), env.LeaseId) || !(TaskKeyset.TryInt(claims, "att", out var att) && att == env.Attempt))
            {
                return Reject(env, RejectReasons.Agent, "tid");
            }

            if (Str(claims, "knd") != env.Kind || !_handlers.TryGetValue(env.Kind, out var handler)) return Reject(env, RejectReasons.Kind, "kind");

            // 3 — base: store-agent kinds never target a 1C base (33 §9.5: base_id = null)
            var bidNull = !claims.TryGetProperty("bid", out var bid) || bid.ValueKind == JsonValueKind.Null;
            if (!bidNull || env.BaseId != null) return Reject(env, RejectReasons.Base, "base_id");

            // 4 — expiry
            if (!TaskKeyset.TryLong(claims, "exp", out var exp) || DateTimeOffset.FromUnixTimeSeconds(exp) <= now - Skew) return Reject(env, RejectReasons.Expired, "exp");

            // 5 — payload hash
            string actual;
            try
            {
                actual = Hashing.Sha256Hex(Jcs.Canonicalize(env.Payload));
            }
            catch (JcsException)
            {
                return Reject(env, RejectReasons.Schema, "payload");
            }

            if (actual != env.PayloadSha256 || Str(claims, "psh") != actual) return Reject(env, RejectReasons.PayloadHash, "payload_sha256");

            // 6 — journal: a finished attempt is answered from the journal, the device is not touched again
            var stored = _journal.FinishedResult(env.TaskId, env.Attempt);
            if (stored != null)
            {
                stored.LeaseId = env.LeaseId;
                return new AcceptResult { Decision = AcceptDecision.Replay, Envelope = env, Handler = handler, Result = stored };
            }

            // 7 — write locks: no store-agent kind is a 1C write (is_write = false).

            // 8 — payload schema
            if (StrictObject.HasNonIntegerNumber(env.Payload)) return Reject(env, RejectReasons.Schema, "payload");
            var badField = handler.ValidatePayload(env.Kind, env.Payload);
            if (badField != null) return Reject(env, RejectReasons.Schema, badField);

            return new AcceptResult { Decision = AcceptDecision.Accepted, Envelope = env, Handler = handler };
        }

        private static bool Same(string? a, string? b) => a != null && b != null && string.Equals(a, b, StringComparison.OrdinalIgnoreCase);

        private AcceptResult Reject(TaskEnvelope env, string reason, string? field)
        {
            var now = Iso.Ms(_clock.UtcNow);
            var body = new ResultBody
            {
                LeaseId = env.LeaseId,
                Attempt = env.Attempt,
                Outcome = "failed",
                Data = TaskExecution.EmptyObject(),
                Error = new ErrorObj { Code = AgentCodes.TaskRejected, Message = reason, Field = field, RetryableHint = false },
                StartedAt = now,
                FinishedAt = now,
                DurationMs = 0,
                WorkerBits = null,
            };
            return new AcceptResult { Decision = AcceptDecision.Rejected, Envelope = env, Reason = reason, Field = field, Result = body };
        }

        internal static TaskEnvelope? ParseEnvelope(JsonElement raw, out string? badField)
        {
            badField = null;
            if (raw.ValueKind != JsonValueKind.Object)
            {
                badField = "envelope";
                return null;
            }

            string? bad = null;
            string? Need(string name)
            {
                var v = Str(raw, name);
                if (string.IsNullOrEmpty(v)) bad ??= name;
                return v;
            }

            var e = new TaskEnvelope
            {
                TaskId = Need("task_id") ?? string.Empty,
                Kind = Need("kind") ?? string.Empty,
                LeaseId = Need("lease_id") ?? string.Empty,
                PayloadSha256 = Need("payload_sha256") ?? string.Empty,
                Kid = Need("kid") ?? string.Empty,
                Signature = Need("signature") ?? string.Empty,
                Purpose = Str(raw, "purpose"),
                LeaseUntil = Str(raw, "lease_until"),
                LocalId = Str(raw, "local_id"),
            };
            badField = bad;
            if (raw.TryGetProperty("base_id", out var b) && b.ValueKind != JsonValueKind.Null)
            {
                if (b.ValueKind != JsonValueKind.String) badField ??= "base_id";
                else e.BaseId = b.GetString();
            }

            if (!(raw.TryGetProperty("attempt", out var at) && at.ValueKind == JsonValueKind.Number && at.TryGetInt32(out var att) && att >= 1)) badField ??= "attempt";
            else e.Attempt = att;
            if (!(raw.TryGetProperty("timeout_s", out var to) && to.ValueKind == JsonValueKind.Number && to.TryGetInt32(out var tos) && tos > 0)) badField ??= "timeout_s";
            else e.TimeoutS = tos;
            if (!(raw.TryGetProperty("payload", out var p) && p.ValueKind == JsonValueKind.Object)) badField ??= "payload";
            else e.Payload = p.Clone();
            if (!Guid.TryParse(e.TaskId, out _)) badField ??= "task_id";
            if (!Guid.TryParse(e.LeaseId, out _)) badField ??= "lease_id";
            if (!Hex64.IsMatch(e.PayloadSha256)) badField ??= "payload_sha256";
            return badField is null ? e : null;
        }

        private static string? Str(JsonElement o, string name) =>
            o.ValueKind == JsonValueKind.Object && o.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;
    }
}

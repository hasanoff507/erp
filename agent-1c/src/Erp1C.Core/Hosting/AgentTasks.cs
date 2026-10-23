using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Core.Contracts;
using Erp1C.Core.Json;

namespace Erp1C.Core.Hosting
{
    /// <summary>Context of one accepted server task (33 §9.5 store-agent kinds, 21 §16).</summary>
    public sealed class TaskContext
    {
        public TaskContext(string taskId, string kind, int attempt, string leaseId, Action<string, int>? progress = null)
        {
            TaskId = taskId;
            Kind = kind;
            Attempt = attempt;
            LeaseId = leaseId;
            _progress = progress;
        }

        private readonly Action<string, int>? _progress;

        public string TaskId { get; }

        public string Kind { get; }

        public int Attempt { get; }

        public string LeaseId { get; }

        /// <summary>Heartbeat stage/pct (33 A-04 stage enum).</summary>
        public void Progress(string stage, int pct) => _progress?.Invoke(stage, pct);
    }

    /// <summary>Outcome of a store-agent task — becomes the A-05 body (outcome, data, error).</summary>
    public sealed class TaskExecution
    {
        private TaskExecution(string outcome, JsonElement data, ErrorObj? error)
        {
            Outcome = outcome;
            Data = data;
            Error = error;
        }

        public string Outcome { get; }

        public JsonElement Data { get; }

        public ErrorObj? Error { get; }

        public static TaskExecution Done<T>(T data) => new TaskExecution("done", AgentJson.ToElement(data), null);

        public static TaskExecution Failed(ErrorObj error) => new TaskExecution("failed", EmptyObject(), error);

        public static TaskExecution Failed(string code, string message, bool retryable = false, string? field = null) =>
            Failed(ErrorObj.Of(code, message, retryable, field));

        public static JsonElement EmptyObject()
        {
            using var doc = JsonDocument.Parse("{}");
            return doc.RootElement.Clone();
        }
    }

    /// <summary>
    /// A store-agent module's server task kinds (34 §14.3 (b)). The agent rejects any kind no handler declares
    /// (33 §9.11 #2 <c>kind</c>).
    /// </summary>
    public interface IAgentTaskHandler
    {
        IReadOnlyCollection<string> Kinds { get; }

        /// <summary>Strict payload check (34 §7.5 #8): null when valid, else the failing field path.</summary>
        string? ValidatePayload(string kind, JsonElement payload);

        Task<TaskExecution> ExecuteAsync(TaskContext context, JsonElement payload, CancellationToken ct);
    }

    /// <summary>Contributes one family of <c>hello.capabilities</c> (34 §14.2).</summary>
    public interface ICapabilityProvider
    {
        string Family { get; }

        object Describe();
    }

    /// <summary>Strict JSON object validation for task payloads — no unknown members, typed values, no floats.</summary>
    public sealed class StrictObject
    {
        private readonly Dictionary<string, (bool Required, Func<JsonElement, bool> Check)> _fields =
            new Dictionary<string, (bool, Func<JsonElement, bool>)>(StringComparer.Ordinal);

        public StrictObject Required(string name, Func<JsonElement, bool> check)
        {
            _fields[name] = (true, check);
            return this;
        }

        public StrictObject Optional(string name, Func<JsonElement, bool> check)
        {
            _fields[name] = (false, check);
            return this;
        }

        /// <summary>Null when valid; otherwise the offending member path (e.g. <c>payload.cash_register_id</c>).</summary>
        public string? Validate(JsonElement value, string path = "payload")
        {
            if (value.ValueKind != JsonValueKind.Object) return path;
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var p in value.EnumerateObject())
            {
                if (!seen.Add(p.Name)) return path + "." + p.Name;
                if (!_fields.TryGetValue(p.Name, out var f)) return path + "." + p.Name;
                if (!f.Check(p.Value)) return path + "." + p.Name;
            }

            foreach (var kv in _fields.Where(kv => kv.Value.Required))
            {
                if (!seen.Contains(kv.Key)) return path + "." + kv.Key;
            }

            return null;
        }

        public static bool IsUuid(JsonElement e) => e.ValueKind == JsonValueKind.String && Guid.TryParse(e.GetString(), out _);

        public static bool IsUuidOrNull(JsonElement e) => e.ValueKind == JsonValueKind.Null || IsUuid(e);

        public static bool IsNonEmptyString(JsonElement e) => e.ValueKind == JsonValueKind.String && !string.IsNullOrEmpty(e.GetString());

        public static Func<JsonElement, bool> IsOneOf(params string[] values) =>
            e => e.ValueKind == JsonValueKind.String && values.Contains(e.GetString(), StringComparer.Ordinal);

        public static bool IsUuidArray(JsonElement e) => e.ValueKind == JsonValueKind.Array && e.EnumerateArray().All(IsUuid);

        public static bool IsUuidArrayOrNull(JsonElement e) => e.ValueKind == JsonValueKind.Null || IsUuidArray(e);

        /// <summary>True when the tree contains a non-integer JSON number (34 §7.5 #8 — rejected for JCS safety).</summary>
        public static bool HasNonIntegerNumber(JsonElement e)
        {
            switch (e.ValueKind)
            {
                case JsonValueKind.Number:
                    return !e.TryGetInt64(out _);
                case JsonValueKind.Object:
                    return e.EnumerateObject().Any(p => HasNonIntegerNumber(p.Value));
                case JsonValueKind.Array:
                    return e.EnumerateArray().Any(HasNonIntegerNumber);
                default:
                    return false;
            }
        }
    }
}

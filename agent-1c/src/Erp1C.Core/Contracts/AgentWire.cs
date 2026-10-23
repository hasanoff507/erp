using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;

#pragma warning disable CA2227 // DTOs: settable collections are the wire contract
#pragma warning disable CA1002 // DTOs use List<T> for System.Text.Json
#pragma warning disable CA1056 // URI properties are strings on the wire

namespace Erp1C.Core.Contracts
{
    // Wire DTOs of the agent ↔ server protocol (33 §9.2, §9.3 A-01, A-03…A-10). snake_case via AgentJson options.
    // Hand-written for Bosqich 5 (no JSON Schema export of the agent channel exists yet — 34 §2.4 gen-contracts
    // covers ObjectSpec only); field names follow 33 §9.3 / contracts/agent-wire.md exactly.

    /// <summary>A-01 request.</summary>
    public sealed class HelloRequest
    {
        public string AgentVersion { get; set; } = string.Empty;

        public int Protocol { get; set; } = 2;

        public string OsVersion { get; set; } = string.Empty;

        public string MachineHash { get; set; } = string.Empty;

        public string PcName { get; set; } = string.Empty;

        public List<int> WorkerBits { get; set; } = new List<int>();

        public List<JsonElement> Platforms { get; set; } = new List<JsonElement>();

        public List<JsonElement> Bases { get; set; } = new List<JsonElement>();

        public int? TaskKeysetVersion { get; set; }

        public List<string> BusyBaseIds { get; set; } = new List<string>();

        public int ResultsOutboxPending { get; set; }

        public Dictionary<string, JsonElement> Capabilities { get; set; } = new Dictionary<string, JsonElement>();

        public string Clock { get; set; } = string.Empty;
    }

    /// <summary>A-01 response.</summary>
    public sealed class HelloResponse
    {
        public string? AgentId { get; set; }

        public string? ServerTime { get; set; }

        public int HelloIntervalS { get; set; } = 600;

        public int PollHintMs { get; set; }

        public string? TaskKeyset { get; set; }

        public HelloUpdate? Update { get; set; }

        public string? MinAgentVersion { get; set; }

        public string? LogLevel { get; set; }

        public string? Subscription { get; set; }
    }

    public sealed class HelloUpdate
    {
        public string? Version { get; set; }

        public string? Channel { get; set; }

        public bool Mandatory { get; set; }

        public string? ManifestUrl { get; set; }
    }

    /// <summary>A-03 request (34 §7.4).</summary>
    public sealed class PollRequest
    {
        public List<string> ReadyBaseIds { get; set; } = new List<string>();

        public List<string> BusyBaseIds { get; set; } = new List<string>();

        public bool AgentLevelBusy { get; set; }

        public int MaxTasks { get; set; } = 1;

        public int WaitS { get; set; } = 25;
    }

    /// <summary>A-03 response: raw task envelopes — the acceptor validates each one (34 §7.5 #0).</summary>
    public sealed class PollResponse
    {
        public List<JsonElement> Tasks { get; set; } = new List<JsonElement>();
    }

    /// <summary>A-04 request.</summary>
    public sealed class HeartbeatRequest
    {
        public string LeaseId { get; set; } = string.Empty;

        public HeartbeatProgress Progress { get; set; } = new HeartbeatProgress();
    }

    public sealed class HeartbeatProgress
    {
        public string Stage { get; set; } = "connecting";

        public int Pct { get; set; }

        public string? Message { get; set; }
    }

    /// <summary>A-04 response.</summary>
    public sealed class HeartbeatResponse
    {
        public string? LeaseUntil { get; set; }

        public bool CancelRequested { get; set; }
    }

    /// <summary>33 §9.10 agent error object.</summary>
    public sealed class ErrorObj
    {
        public string Code { get; set; } = string.Empty;

        public string Message { get; set; } = string.Empty;

        public string? OnecText { get; set; }

        public List<string> OnecMessages { get; set; } = new List<string>();

        public string? ComHresult { get; set; }

        public string? Stage { get; set; }

        public string? Field { get; set; }

        public bool RetryableHint { get; set; }

        /// <summary>Not part of 33 §9.10 — written only when set (device-task codes with params).</summary>
        [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
        [JsonPropertyName("params")]
        public Dictionary<string, JsonElement>? Params { get; set; }

        public static ErrorObj Of(string code, string message, bool retryable = false, string? field = null) =>
            new ErrorObj { Code = code, Message = message, RetryableHint = retryable, Field = field };
    }

    /// <summary>A-05 request body.</summary>
    public sealed class ResultBody
    {
        public string LeaseId { get; set; } = string.Empty;

        public int Attempt { get; set; }

        /// <summary>done | failed | unknown.</summary>
        public string Outcome { get; set; } = "done";

        public JsonElement Data { get; set; }

        public ErrorObj? Error { get; set; }

        public string StartedAt { get; set; } = string.Empty;

        public string FinishedAt { get; set; } = string.Empty;

        public long DurationMs { get; set; }

        public int? WorkerBits { get; set; }
    }

    /// <summary>A-05 response.</summary>
    public sealed class ResultResponse
    {
        public bool Accepted { get; set; }

        public bool Duplicate { get; set; }

        public bool Late { get; set; }
    }

    /// <summary>A-06 entry (34 §9.3).</summary>
    public sealed class LogEntry
    {
        public string ClientLogId { get; set; } = string.Empty;

        public string At { get; set; } = string.Empty;

        public string Level { get; set; } = "info";

        public string? Code { get; set; }

        public string Message { get; set; } = string.Empty;

        public string? BaseId { get; set; }

        public string? TaskId { get; set; }

        public Dictionary<string, JsonElement>? Context { get; set; }
    }

    public sealed class LogsRequest
    {
        public List<LogEntry> Entries { get; set; } = new List<LogEntry>();
    }

    public sealed class LogsResponse
    {
        public int Accepted { get; set; }

        public int Duplicates { get; set; }
    }

    /// <summary>A-08 response.</summary>
    public sealed class TaskKeysResponse
    {
        public int Version { get; set; }

        public string TaskKeyset { get; set; } = string.Empty;
    }

    /// <summary>A-09 response.</summary>
    public sealed class UpdateManifestEnvelope
    {
        public string Manifest { get; set; } = string.Empty;

        public string Signature { get; set; } = string.Empty;

        public string Kid { get; set; } = string.Empty;
    }

    /// <summary>A-09 manifest JSON (inside the signed base64 bytes).</summary>
    public sealed class UpdateManifest
    {
        public string Product { get; set; } = string.Empty;

        public string Version { get; set; } = string.Empty;

        public string Channel { get; set; } = string.Empty;

        public string Url { get; set; } = string.Empty;

        public string Sha256 { get; set; } = string.Empty;

        public long Size { get; set; }

        public string MinOs { get; set; } = string.Empty;

        public int MinProtocol { get; set; }

        public int RolloutPct { get; set; } = 100;

        public string? ReleasedAt { get; set; }

        public string? NotesUz { get; set; }

        public string? NotesRu { get; set; }
    }

    /// <summary>A-10 request.</summary>
    public sealed class UnpairRequest
    {
        public string Reason { get; set; } = "user";
    }

    /// <summary>RFC 8628 device authorization response (33 §9.2).</summary>
    public sealed class DeviceAuthorizationResponse
    {
        public string DeviceCode { get; set; } = string.Empty;

        public string UserCode { get; set; } = string.Empty;

        public string VerificationUri { get; set; } = string.Empty;

        public string? VerificationUriComplete { get; set; }

        public int ExpiresIn { get; set; } = 600;

        public int Interval { get; set; } = 5;
    }

    /// <summary>/oauth/token success (33 §9.2) — device grant adds agent_id, agent_client_id, tenant_name, task_keyset.</summary>
    public sealed class TokenResponse
    {
        public string AccessToken { get; set; } = string.Empty;

        public string TokenType { get; set; } = "Bearer";

        public int ExpiresIn { get; set; } = 600;

        public string? Scope { get; set; }

        public string? AgentId { get; set; }

        public string? AgentClientId { get; set; }

        public string? TenantName { get; set; }

        public string? TaskKeyset { get; set; }
    }

    /// <summary>RFC 6749 §5.2 error.</summary>
    public sealed class OAuthError
    {
        public string Error { get; set; } = string.Empty;

        public string? ErrorDescription { get; set; }
    }

    /// <summary>17 §7 error envelope.</summary>
    public sealed class ApiErrorEnvelope
    {
        public ApiErrorBody? Error { get; set; }
    }

    public sealed class ApiErrorBody
    {
        public string Code { get; set; } = string.Empty;

        public string? MessageKey { get; set; }

        [JsonPropertyName("params")]
        public Dictionary<string, JsonElement>? Params { get; set; }

        public JsonElement? Details { get; set; }

        public string? RequestId { get; set; }
    }
}

using System;
using System.Collections.Generic;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Core.Errors;
using Erp1C.Core.Json;

#pragma warning disable CA1002
#pragma warning disable CA1054
#pragma warning disable CA1056

namespace Erp1C.Core.Hosting
{
    /// <summary>An authenticated local API request (21 §16.1) after Origin and token checks.</summary>
    public sealed class LocalRequest
    {
        public LocalRequest(string method, string path, IReadOnlyDictionary<string, string> query, byte[] body, IReadOnlyDictionary<string, string> routeValues, string? deviceId)
        {
            Method = method;
            Path = path;
            Query = query;
            Body = body;
            RouteValues = routeValues;
            DeviceId = deviceId;
        }

        public string Method { get; }

        public string Path { get; }

        public IReadOnlyDictionary<string, string> Query { get; }

        public byte[] Body { get; }

        public IReadOnlyDictionary<string, string> RouteValues { get; }

        /// <summary>POS <c>devices.id</c> the local token is bound to (null only for anonymous routes).</summary>
        public string? DeviceId { get; }

        public string? QueryValue(string name) => Query.TryGetValue(name, out var v) ? v : null;

        /// <summary>Parses the body as a JSON object; a missing/invalid body → 422 VALIDATION_ERROR.</summary>
        public JsonElement JsonBody()
        {
            if (Body.Length == 0) throw LocalApiException.Validation("body", "required");
            try
            {
                using var doc = JsonDocument.Parse(Body);
                if (doc.RootElement.ValueKind != JsonValueKind.Object) throw LocalApiException.Validation("body", "object_required");
                return doc.RootElement.Clone();
            }
            catch (JsonException)
            {
                throw LocalApiException.Validation("body", "invalid_json");
            }
        }
    }

    public sealed class LocalResponse
    {
        private LocalResponse(int status, byte[] body)
        {
            Status = status;
            Body = body;
        }

        public int Status { get; }

        public byte[] Body { get; }

        public static LocalResponse Json<T>(T value, int status = 200) => new LocalResponse(status, AgentJson.SerializeUtf8(value));

        public static LocalResponse Raw(int status, string json) => new LocalResponse(status, Encoding.UTF8.GetBytes(json));

        public static LocalResponse Error(string code, IDictionary<string, object?>? parameters = null) =>
            Error(LocalCodes.Status(code), code, parameters);

        public static LocalResponse Error(int status, string code, IDictionary<string, object?>? parameters = null)
        {
            var body = new Dictionary<string, object?>
            {
                ["code"] = code,
                ["message_key"] = LocalCodes.MessageKey(code),
            };
            if (parameters != null && parameters.Count > 0) body["params"] = parameters;
            return new LocalResponse(status, AgentJson.SerializeUtf8(body));
        }
    }

    /// <summary>Thrown by local API handlers; mapped to the 21 §16.1 error shape <c>{code, message_key, params?}</c>.</summary>
    public sealed class LocalApiException : Exception
    {
        public LocalApiException()
            : this(LocalCodes.InternalError)
        {
        }

        public LocalApiException(string code)
            : this(code, (IDictionary<string, object?>?)null)
        {
        }

        public LocalApiException(string code, Exception inner)
            : base(code, inner)
        {
            Code = code;
            Status = LocalCodes.Status(code);
        }

        public LocalApiException(string code, IDictionary<string, object?>? parameters, int? status = null)
            : base(code)
        {
            Code = code;
            Parameters = parameters;
            Status = status ?? LocalCodes.Status(code);
        }

        public string Code { get; } = LocalCodes.InternalError;

        public int Status { get; } = 500;

        public IDictionary<string, object?>? Parameters { get; }

        public static LocalApiException Validation(string field, string reason) =>
            new LocalApiException(LocalCodes.ValidationError, new Dictionary<string, object?> { ["field"] = field, ["reason"] = reason });

        public LocalResponse ToResponse() => LocalResponse.Error(Status, Code, Parameters);
    }

    public delegate Task<LocalResponse> LocalHandler(LocalRequest request, CancellationToken ct);

    /// <summary>One local API route; <c>{name}</c> segments bind route values (e.g. <c>/v1/card/tx/{attempt_id}</c>).</summary>
    public sealed class LocalRoute
    {
        public LocalRoute(string method, string pattern, LocalHandler handler, bool anonymous = false)
        {
            Method = method;
            Pattern = pattern;
            Handler = handler;
            Anonymous = anonymous;
            Segments = pattern.Trim('/').Split('/');
        }

        public string Method { get; }

        public string Pattern { get; }

        public LocalHandler Handler { get; }

        /// <summary>No local token required (only <c>POST /v1/pair</c>); the Origin allow-list still applies.</summary>
        public bool Anonymous { get; }

        internal string[] Segments { get; }

        public bool TryMatch(string path, out Dictionary<string, string> values)
        {
            values = new Dictionary<string, string>(StringComparer.Ordinal);
            var parts = path.Trim('/').Split('/');
            if (parts.Length != Segments.Length) return false;
            for (var i = 0; i < parts.Length; i++)
            {
                var seg = Segments[i];
                if (seg.StartsWith("{", StringComparison.Ordinal) && seg.EndsWith("}", StringComparison.Ordinal))
                {
                    if (parts[i].Length == 0) return false;
                    values[seg.Substring(1, seg.Length - 2)] = Uri.UnescapeDataString(parts[i]);
                }
                else if (!string.Equals(seg, parts[i], StringComparison.Ordinal))
                {
                    return false;
                }
            }

            return true;
        }
    }

    /// <summary>A module (fiscal, print, card terminal) that contributes local API routes.</summary>
    public interface ILocalApiModule
    {
        IEnumerable<LocalRoute> Routes { get; }
    }
}

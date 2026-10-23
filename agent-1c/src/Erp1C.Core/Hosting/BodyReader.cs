using System;
using System.Text.Json;

namespace Erp1C.Core.Hosting
{
    /// <summary>Typed reads of a local API JSON body; any violation → 422 VALIDATION_ERROR with <c>params.field</c>.</summary>
    public readonly struct BodyReader
    {
        public const long MaxSafeInteger = 9007199254740991;

        private readonly JsonElement _o;

        public BodyReader(JsonElement o)
        {
            _o = o;
        }

        public JsonElement Element => _o;

        public bool Has(string name) => _o.TryGetProperty(name, out var v) && v.ValueKind != JsonValueKind.Null;

        public Guid RequireGuid(string name)
        {
            var g = OptionalGuid(name);
            if (g is null) throw LocalApiException.Validation(name, "required");
            return g.Value;
        }

        public Guid? OptionalGuid(string name)
        {
            if (!_o.TryGetProperty(name, out var v) || v.ValueKind == JsonValueKind.Null) return null;
            if (v.ValueKind != JsonValueKind.String || !Guid.TryParse(v.GetString(), out var g)) throw LocalApiException.Validation(name, "uuid");
            return g;
        }

        public string RequireString(string name, int maxLength = 256)
        {
            var s = OptionalString(name, maxLength);
            if (string.IsNullOrEmpty(s)) throw LocalApiException.Validation(name, "required");
            return s!;
        }

        public string? OptionalString(string name, int maxLength = 256)
        {
            if (!_o.TryGetProperty(name, out var v) || v.ValueKind == JsonValueKind.Null) return null;
            if (v.ValueKind != JsonValueKind.String) throw LocalApiException.Validation(name, "string");
            var s = v.GetString()!;
            if (s.Length > maxLength) throw LocalApiException.Validation(name, "too_long");
            return s;
        }

        /// <summary>Integer JSON number (never a string or a fraction) within ±(2^53−1) — tiyin amounts (qaror #12).</summary>
        public long RequireLong(string name, long min = long.MinValue, long max = MaxSafeInteger)
        {
            var v = OptionalLong(name, min, max);
            if (v is null) throw LocalApiException.Validation(name, "required");
            return v.Value;
        }

        public long? OptionalLong(string name, long min = long.MinValue, long max = MaxSafeInteger)
        {
            if (!_o.TryGetProperty(name, out var v) || v.ValueKind == JsonValueKind.Null) return null;
            if (v.ValueKind != JsonValueKind.Number || !v.TryGetInt64(out var n)) throw LocalApiException.Validation(name, "integer");
            if (n < Math.Max(min, -MaxSafeInteger) || n > Math.Min(max, MaxSafeInteger)) throw LocalApiException.Validation(name, "range");
            return n;
        }

        public JsonElement? OptionalObject(string name)
        {
            if (!_o.TryGetProperty(name, out var v) || v.ValueKind == JsonValueKind.Null) return null;
            if (v.ValueKind != JsonValueKind.Object) throw LocalApiException.Validation(name, "object");
            return v;
        }

        public JsonElement RequireObject(string name) => OptionalObject(name) ?? throw LocalApiException.Validation(name, "required");

        public JsonElement? OptionalArray(string name)
        {
            if (!_o.TryGetProperty(name, out var v) || v.ValueKind == JsonValueKind.Null) return null;
            if (v.ValueKind != JsonValueKind.Array) throw LocalApiException.Validation(name, "array");
            return v;
        }

        public BodyReader Child(string name) => new BodyReader(RequireObject(name));
    }
}

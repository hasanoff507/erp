using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Erp1C.Core.Json
{
    /// <summary>
    /// Shared System.Text.Json options: snake_case wire names (33 §9.1, 32 §1.3), nulls written (the wire shapes
    /// carry explicit nulls), unknown fields ignored on read (34 §7.1).
    /// </summary>
    public static class AgentJson
    {
        public static readonly JsonSerializerOptions Options = Create(indented: false);

        public static readonly JsonSerializerOptions Indented = Create(indented: true);

        private static JsonSerializerOptions Create(bool indented)
        {
            var o = new JsonSerializerOptions
            {
                PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
                DictionaryKeyPolicy = null,
                DefaultIgnoreCondition = JsonIgnoreCondition.Never,
                WriteIndented = indented,
                Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
                NumberHandling = JsonNumberHandling.Strict,
                ReadCommentHandling = JsonCommentHandling.Disallow,
            };
            o.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.SnakeCaseLower));
            return o;
        }

        public static string Serialize<T>(T value) => JsonSerializer.Serialize(value, Options);

        public static byte[] SerializeUtf8<T>(T value) => JsonSerializer.SerializeToUtf8Bytes(value, Options);

        public static T? Deserialize<T>(string json) => JsonSerializer.Deserialize<T>(json, Options);

        public static T? Deserialize<T>(byte[] utf8) => JsonSerializer.Deserialize<T>(utf8, Options);

        public static T? Deserialize<T>(JsonElement element) => element.Deserialize<T>(Options);

        public static JsonElement ToElement<T>(T value)
        {
            using var doc = JsonDocument.Parse(SerializeUtf8(value));
            return doc.RootElement.Clone();
        }
    }
}

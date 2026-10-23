using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using System.Text.Json;

namespace Erp1C.Core.Json
{
    /// <summary>
    /// RFC 8785 JSON Canonicalization Scheme (https://www.rfc-editor.org/rfc/rfc8785): members sorted by UTF-16 code
    /// units, ECMAScript JSON.stringify string escaping, ECMAScript Number.prototype.toString number form; no
    /// insignificant whitespace. Duplicate member names are rejected (I-JSON, RFC 7493).
    /// </summary>
    public static class Jcs
    {
        public static string Canonicalize(string json)
        {
            if (json is null) throw new ArgumentNullException(nameof(json));
            return Canonicalize(Encoding.UTF8.GetBytes(json));
        }

        public static string Canonicalize(byte[] utf8Json)
        {
            using var doc = Parse(utf8Json);
            return Canonicalize(doc.RootElement);
        }

        public static string Canonicalize(JsonElement element)
        {
            var sb = new StringBuilder();
            Write(sb, element);
            return sb.ToString();
        }

        public static byte[] CanonicalUtf8(JsonElement element) => Encoding.UTF8.GetBytes(Canonicalize(element));

        private static JsonDocument Parse(byte[] utf8)
        {
            try
            {
                return JsonDocument.Parse(utf8, new JsonDocumentOptions { AllowTrailingCommas = false, CommentHandling = JsonCommentHandling.Disallow, MaxDepth = 128 });
            }
            catch (JsonException e)
            {
                throw new JcsException("invalid JSON: " + e.Message, e);
            }
        }

        private static void Write(StringBuilder sb, JsonElement e)
        {
            switch (e.ValueKind)
            {
                case JsonValueKind.Object:
                    WriteObject(sb, e);
                    break;
                case JsonValueKind.Array:
                    sb.Append('[');
                    var first = true;
                    foreach (var item in e.EnumerateArray())
                    {
                        if (!first) sb.Append(',');
                        first = false;
                        Write(sb, item);
                    }

                    sb.Append(']');
                    break;
                case JsonValueKind.String:
                    WriteString(sb, e.GetString()!);
                    break;
                case JsonValueKind.Number:
                    sb.Append(FormatNumber(e.GetRawText()));
                    break;
                case JsonValueKind.True:
                    sb.Append("true");
                    break;
                case JsonValueKind.False:
                    sb.Append("false");
                    break;
                case JsonValueKind.Null:
                    sb.Append("null");
                    break;
                default:
                    throw new JcsException("unsupported JSON value");
            }
        }

        private static void WriteObject(StringBuilder sb, JsonElement e)
        {
            var members = new List<KeyValuePair<string, JsonElement>>();
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var p in e.EnumerateObject())
            {
                if (!seen.Add(p.Name)) throw new JcsException("duplicate member name: " + p.Name);
                members.Add(new KeyValuePair<string, JsonElement>(p.Name, p.Value));
            }

            // string.CompareOrdinal compares UTF-16 code units — exactly RFC 8785 §3.2.3.
            members.Sort((a, b) => string.CompareOrdinal(a.Key, b.Key));
            sb.Append('{');
            for (var i = 0; i < members.Count; i++)
            {
                if (i > 0) sb.Append(',');
                WriteString(sb, members[i].Key);
                sb.Append(':');
                Write(sb, members[i].Value);
            }

            sb.Append('}');
        }

        internal static void WriteString(StringBuilder sb, string s)
        {
            sb.Append('"');
            foreach (var c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\b': sb.Append("\\b"); break;
                    case '\f': sb.Append("\\f"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 0x20)
                        {
                            sb.Append("\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                        }
                        else
                        {
                            sb.Append(c);
                        }

                        break;
                }
            }

            sb.Append('"');
        }

        /// <summary>ECMAScript Number::toString of the IEEE-754 double the JSON number text denotes.</summary>
        public static string FormatNumber(string rawJsonNumber)
        {
            if (!double.TryParse(rawJsonNumber, NumberStyles.Float, CultureInfo.InvariantCulture, out var d) || double.IsInfinity(d) || double.IsNaN(d))
            {
                throw new JcsException("number out of IEEE-754 range: " + rawJsonNumber);
            }

            return FormatDouble(d);
        }

        public static string FormatDouble(double d)
        {
            if (double.IsNaN(d) || double.IsInfinity(d)) throw new JcsException("NaN/Infinity are not JSON");
            if (d == 0) return "0"; // also -0
            var negative = d < 0;
            var abs = Math.Abs(d);

            // Shortest decimal digits that round-trip (net48 "R" is not always shortest — search the precisions).
            var digits = string.Empty;
            var exp10 = 0;
            for (var p = 1; p <= 17; p++)
            {
                var s = abs.ToString("E" + (p - 1).ToString(CultureInfo.InvariantCulture), CultureInfo.InvariantCulture);
                if (double.Parse(s, NumberStyles.Float, CultureInfo.InvariantCulture) != abs) continue;
                var ePos = s.IndexOf('E');
                digits = s.Substring(0, ePos).Replace(".", string.Empty);
                exp10 = int.Parse(s.Substring(ePos + 1), NumberStyles.AllowLeadingSign, CultureInfo.InvariantCulture);
                break;
            }

            digits = digits.TrimEnd('0');
            if (digits.Length == 0) digits = "0";
            var k = digits.Length;
            var n = exp10 + 1; // value = 0.digits × 10^n
            var sb = new StringBuilder();
            if (negative) sb.Append('-');
            if (k <= n && n <= 21)
            {
                sb.Append(digits).Append('0', n - k);
            }
            else if (0 < n && n <= 21)
            {
                sb.Append(digits, 0, n).Append('.').Append(digits, n, k - n);
            }
            else if (-6 < n && n <= 0)
            {
                sb.Append("0.").Append('0', -n).Append(digits);
            }
            else
            {
                sb.Append(digits[0]);
                if (k > 1) sb.Append('.').Append(digits, 1, k - 1);
                sb.Append('e').Append(n - 1 >= 0 ? "+" : "-").Append(Math.Abs(n - 1).ToString(CultureInfo.InvariantCulture));
            }

            return sb.ToString();
        }
    }

    public sealed class JcsException : Exception
    {
        public JcsException()
        {
        }

        public JcsException(string message)
            : base(message)
        {
        }

        public JcsException(string message, Exception inner)
            : base(message, inner)
        {
        }
    }
}

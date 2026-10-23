using System;
using System.Security.Cryptography;
using System.Text;

namespace Erp1C.Core.Crypto
{
    /// <summary>RFC 4648 §5 base64url without padding (RFC 7515 §2).</summary>
    public static class Base64Url
    {
        public static string Encode(byte[] data)
        {
            if (data is null) throw new ArgumentNullException(nameof(data));
            return Convert.ToBase64String(data).TrimEnd('=').Replace('+', '-').Replace('/', '_');
        }

        public static string EncodeUtf8(string text) => Encode(Encoding.UTF8.GetBytes(text));

        public static byte[] Decode(string text)
        {
            if (text is null) throw new ArgumentNullException(nameof(text));
            foreach (var c in text)
            {
                var ok = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-' || c == '_';
                if (!ok) throw new FormatException("not base64url");
            }

            if (text.Length % 4 == 1) throw new FormatException("not base64url");
            var s = text.Replace('-', '+').Replace('_', '/');
            s += (s.Length % 4) switch { 2 => "==", 3 => "=", _ => string.Empty };
            return Convert.FromBase64String(s);
        }

        public static bool TryDecode(string? text, out byte[] bytes)
        {
            bytes = Array.Empty<byte>();
            if (text is null) return false;
            try
            {
                bytes = Decode(text);
                return true;
            }
            catch (FormatException)
            {
                return false;
            }
        }
    }

    public static class Hashing
    {
        public static byte[] Sha256(byte[] data)
        {
            using var sha = SHA256.Create();
            return sha.ComputeHash(data);
        }

        /// <summary>Lower-case hex SHA-256 (33 §9.4 payload_sha256, manifest sha256).</summary>
        public static string Sha256Hex(byte[] data) => Hex(Sha256(data));

        public static string Sha256Hex(string utf8) => Sha256Hex(Encoding.UTF8.GetBytes(utf8));

        public static string Hex(byte[] data)
        {
            var sb = new StringBuilder(data.Length * 2);
            foreach (var b in data) sb.Append(b.ToString("x2", System.Globalization.CultureInfo.InvariantCulture));
            return sb.ToString();
        }

        /// <summary>Constant-time comparison of two byte arrays.</summary>
        public static bool FixedTimeEquals(byte[] a, byte[] b)
        {
            if (a is null || b is null || a.Length != b.Length) return false;
            var diff = 0;
            for (var i = 0; i < a.Length; i++) diff |= a[i] ^ b[i];
            return diff == 0;
        }
    }
}

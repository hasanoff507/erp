using System;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Erp1C.Core.Crypto
{
    /// <summary>
    /// RFC 7515 compact JWS with EdDSA/Ed25519 (RFC 8037): <c>b64u(header).b64u(payload).b64u(signature)</c>, the
    /// signature covers the ASCII bytes of <c>b64u(header).b64u(payload)</c>.
    /// </summary>
    public static class CompactJws
    {
        public static string Sign(JsonObject header, JsonObject claims, Func<byte[], byte[]> sign)
        {
            if (header is null) throw new ArgumentNullException(nameof(header));
            if (claims is null) throw new ArgumentNullException(nameof(claims));
            if (sign is null) throw new ArgumentNullException(nameof(sign));
            var h = Base64Url.EncodeUtf8(header.ToJsonString());
            var p = Base64Url.EncodeUtf8(claims.ToJsonString());
            var input = h + "." + p;
            var sig = sign(Encoding.ASCII.GetBytes(input));
            return input + "." + Base64Url.Encode(sig);
        }

        public static string SignEd25519(JsonObject header, JsonObject claims, byte[] seed) =>
            Sign(header, claims, data => Ed25519.Sign(seed, data));

        /// <summary>Splits and decodes a compact JWS; throws <see cref="JwsFormatException"/> on any format error.</summary>
        public static JwsParts Parse(string token)
        {
            if (string.IsNullOrEmpty(token)) throw new JwsFormatException("empty JWS");
            var parts = token.Split('.');
            if (parts.Length != 3) throw new JwsFormatException("JWS must have 3 parts");
            if (!Base64Url.TryDecode(parts[0], out var headerBytes)) throw new JwsFormatException("header is not base64url");
            if (!Base64Url.TryDecode(parts[1], out var payloadBytes)) throw new JwsFormatException("payload is not base64url");
            if (!Base64Url.TryDecode(parts[2], out var sig)) throw new JwsFormatException("signature is not base64url");
            JsonElement header;
            try
            {
                using var doc = JsonDocument.Parse(headerBytes);
                header = doc.RootElement.Clone();
            }
            catch (JsonException e)
            {
                throw new JwsFormatException("header is not JSON", e);
            }

            if (header.ValueKind != JsonValueKind.Object) throw new JwsFormatException("header is not an object");
            return new JwsParts(header, payloadBytes, Encoding.ASCII.GetBytes(parts[0] + "." + parts[1]), sig);
        }

        /// <summary>Checks <c>alg == "EdDSA"</c>, the expected <c>typ</c> and the signature under <paramref name="publicKey"/>.</summary>
        public static bool VerifyEd25519(JwsParts jws, byte[] publicKey) =>
            jws.Alg == "EdDSA" && Ed25519.Verify(publicKey, jws.SigningInput, jws.Signature);
    }

    public sealed class JwsParts
    {
        public JwsParts(JsonElement header, byte[] payload, byte[] signingInput, byte[] signature)
        {
            Header = header;
            Payload = payload;
            SigningInput = signingInput;
            Signature = signature;
        }

        public JsonElement Header { get; }

        public byte[] Payload { get; }

        public byte[] SigningInput { get; }

        public byte[] Signature { get; }

        public string? Alg => HeaderString("alg");

        public string? Typ => HeaderString("typ");

        public string? Kid => HeaderString("kid");

        public string? HeaderString(string name) =>
            Header.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;

        public JsonElement PayloadJson()
        {
            try
            {
                using var doc = JsonDocument.Parse(Payload);
                if (doc.RootElement.ValueKind != JsonValueKind.Object) throw new JwsFormatException("payload is not an object");
                return doc.RootElement.Clone();
            }
            catch (JsonException e)
            {
                throw new JwsFormatException("payload is not JSON", e);
            }
        }
    }

    public sealed class JwsFormatException : Exception
    {
        public JwsFormatException()
        {
        }

        public JwsFormatException(string message)
            : base(message)
        {
        }

        public JwsFormatException(string message, Exception inner)
            : base(message, inner)
        {
        }
    }

    /// <summary>RFC 7638 JWK thumbprint of an Ed25519 OKP key (34 §5.1) — the agent <c>kid</c>.</summary>
    public static class JwkThumbprint
    {
        public static string Ed25519(string xBase64Url) =>
            Base64Url.Encode(Hashing.Sha256(Encoding.UTF8.GetBytes("{\"crv\":\"Ed25519\",\"kty\":\"OKP\",\"x\":\"" + xBase64Url + "\"}")));

        public static string Ed25519(byte[] x) => Ed25519(Base64Url.Encode(x));

        /// <summary>Public JWK JSON sent to the server (33 §9.2 <c>public_jwk</c>).</summary>
        public static string PublicJwkJson(byte[] x) => "{\"kty\":\"OKP\",\"crv\":\"Ed25519\",\"x\":\"" + Base64Url.Encode(x) + "\"}";
    }
}

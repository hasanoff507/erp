using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using Erp1C.Core.Crypto;

namespace Erp1C.Core.Trust
{
    /// <summary>An Ed25519 public key with its key id (root <c>agent_update</c> key or <c>onec_task</c> key).</summary>
    public sealed class TrustKey
    {
        public TrustKey(string kid, byte[] x, DateTimeOffset? notBefore = null, DateTimeOffset? expires = null)
        {
            if (string.IsNullOrEmpty(kid)) throw new ArgumentException("kid required", nameof(kid));
            if (x is null || x.Length != Ed25519.KeySize) throw new ArgumentException("x must be 32 bytes", nameof(x));
            Kid = kid;
            X = x;
            NotBefore = notBefore;
            Expires = expires;
        }

        public string Kid { get; }

        public byte[] X { get; }

        public DateTimeOffset? NotBefore { get; }

        public DateTimeOffset? Expires { get; }

        public static TrustKey FromBase64Url(string kid, string x) => new TrustKey(kid, Base64Url.Decode(x));
    }

    /// <summary>
    /// Root <c>agent_update</c> public keys (current + next, 33 §9.4, 34 §5.5). The production keys are compiled into
    /// <see cref="RootKeys.Embedded"/> by the release pipeline (offline key, 34 §2.5); a DEV build may add keys from
    /// <c>dev-root-keys.json</c> (34 §6.8 — only the DEV configuration accepts local overrides).
    /// </summary>
    public sealed class RootKeys
    {
        private readonly Dictionary<string, TrustKey> _keys;

        public RootKeys(IEnumerable<TrustKey> keys)
        {
            _keys = new Dictionary<string, TrustKey>(StringComparer.Ordinal);
            foreach (var k in keys) _keys[k.Kid] = k;
        }

        /// <summary>
        /// Compiled-in production roots. Empty until the offline <c>agent_update</c> key exists (26 #105 release
        /// pipeline); with no root an agent accepts no keyset and no update — fail closed.
        /// </summary>
        public static IReadOnlyList<TrustKey> Embedded { get; } = Array.Empty<TrustKey>();

        public int Count => _keys.Count;

        public bool TryGet(string? kid, out TrustKey key)
        {
            key = null!;
            if (kid is null) return false;
            if (_keys.TryGetValue(kid, out var k))
            {
                key = k;
                return true;
            }

            return false;
        }
    }

    /// <summary>A verified task keyset (33 §9.4).</summary>
    public sealed class TaskKeyset
    {
        public const string Typ = "onec-task-keyset+jwt";
        public const int MaxSkewSeconds = 120;

        private TaskKeyset(int version, DateTimeOffset expires, IReadOnlyList<TrustKey> keys, string jws)
        {
            Version = version;
            Expires = expires;
            Keys = keys;
            Jws = jws;
        }

        public int Version { get; }

        public DateTimeOffset Expires { get; }

        public IReadOnlyList<TrustKey> Keys { get; }

        public string Jws { get; }

        public TrustKey? Find(string? kid) => kid is null ? null : Keys.FirstOrDefault(k => k.Kid == kid);

        /// <summary>
        /// Verifies a keyset JWS (34 §5.5): alg EdDSA, typ <c>onec-task-keyset+jwt</c>, kid among the roots, valid
        /// signature, <c>exp &gt; now</c>, <c>ver ≥ minVersion</c> (no downgrade), every key OKP/Ed25519 with 32-byte x.
        /// </summary>
        public static TaskKeyset Verify(string jws, RootKeys roots, DateTimeOffset now, int minVersion)
        {
            if (roots is null) throw new ArgumentNullException(nameof(roots));
            JwsParts parts;
            try
            {
                parts = CompactJws.Parse(jws);
            }
            catch (JwsFormatException e)
            {
                throw new KeysetException("format", e.Message);
            }

            if (parts.Alg != "EdDSA") throw new KeysetException("alg", "alg must be EdDSA");
            if (parts.Typ != Typ) throw new KeysetException("typ", "typ must be " + Typ);
            if (!roots.TryGet(parts.Kid, out var root)) throw new KeysetException("kid", "unknown root kid");
            if (!Ed25519.Verify(root.X, parts.SigningInput, parts.Signature)) throw new KeysetException("signature", "bad keyset signature");

            JsonElement p;
            try
            {
                p = parts.PayloadJson();
            }
            catch (JwsFormatException e)
            {
                throw new KeysetException("format", e.Message);
            }

            if (!TryInt(p, "ver", out var ver)) throw new KeysetException("format", "ver missing");
            if (!TryLong(p, "exp", out var exp)) throw new KeysetException("format", "exp missing");
            var expires = DateTimeOffset.FromUnixTimeSeconds(exp);
            if (expires <= now) throw new KeysetException("expired", "keyset expired");
            if (ver < minVersion) throw new KeysetException("downgrade", "keyset version is lower than the stored one");
            if (!p.TryGetProperty("keys", out var keysEl) || keysEl.ValueKind != JsonValueKind.Array) throw new KeysetException("format", "keys missing");

            var keys = new List<TrustKey>();
            foreach (var k in keysEl.EnumerateArray())
            {
                if (k.ValueKind != JsonValueKind.Object) throw new KeysetException("format", "key is not an object");
                if (Str(k, "kty") != "OKP" || Str(k, "crv") != "Ed25519") throw new KeysetException("format", "key must be OKP/Ed25519");
                var kid = Str(k, "kid");
                var x = Str(k, "x");
                if (string.IsNullOrEmpty(kid) || !Base64Url.TryDecode(x, out var xb) || xb.Length != Ed25519.KeySize)
                {
                    throw new KeysetException("format", "bad key");
                }

                DateTimeOffset? nbf = TryLong(k, "nbf", out var nbfS) ? DateTimeOffset.FromUnixTimeSeconds(nbfS) : (DateTimeOffset?)null;
                DateTimeOffset? kexp = TryLong(k, "exp", out var expS) ? DateTimeOffset.FromUnixTimeSeconds(expS) : (DateTimeOffset?)null;
                keys.Add(new TrustKey(kid!, xb, nbf, kexp));
            }

            return new TaskKeyset(ver, expires, keys, jws);
        }

        public static string? Str(JsonElement o, string name) =>
            o.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;

        public static bool TryLong(JsonElement o, string name, out long value)
        {
            value = 0;
            return o.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.Number && v.TryGetInt64(out value);
        }

        public static bool TryInt(JsonElement o, string name, out int value)
        {
            value = 0;
            return o.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.Number && v.TryGetInt32(out value);
        }
    }

    public sealed class KeysetException : Exception
    {
        public KeysetException()
            : this("format", "keyset rejected")
        {
        }

        public KeysetException(string message)
            : this("format", message)
        {
        }

        public KeysetException(string message, Exception inner)
            : base(message, inner)
        {
            Reason = "format";
        }

        public KeysetException(string reason, string message)
            : base(message)
        {
            Reason = reason;
        }

        public string Reason { get; } = "format";
    }
}

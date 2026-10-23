using System;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Erp1C.Core.Crypto;
using Erp1C.Core.Json;
using Erp1C.Core.Trust;
using Erp1C.Tests.Common;
using Shouldly;
using Xunit;

namespace Erp1C.Core.Tests
{
    public class JcsTests
    {
        public static TheoryData<string> CaseNames()
        {
            var d = new TheoryData<string>();
            foreach (var c in Repo.LoadVector("jcs.json").GetProperty("cases").EnumerateArray()) d.Add(c.GetProperty("name").GetString()!);
            return d;
        }

        [Theory]
        [MemberData(nameof(CaseNames))]
        public void Shared_vector_canonical_bytes_and_sha256(string name)
        {
            var c = Repo.LoadVector("jcs.json").GetProperty("cases").EnumerateArray().Single(x => x.GetProperty("name").GetString() == name);
            var canonical = Jcs.Canonicalize(c.GetProperty("input").GetString()!);
            canonical.ShouldBe(c.GetProperty("canonical").GetString());
            Hashing.Hex(Encoding.UTF8.GetBytes(canonical)).ShouldBe(c.GetProperty("canonical_utf8_hex").GetString());
            Hashing.Sha256Hex(canonical).ShouldBe(c.GetProperty("sha256").GetString());
        }

        [Fact]
        public void Duplicate_member_names_are_rejected()
        {
            Should.Throw<JcsException>(() => Jcs.Canonicalize("{\"a\":1,\"a\":2}"));
        }

        [Theory]
        [InlineData(0.1, "0.1")]
        [InlineData(1e21, "1e+21")]
        [InlineData(123456789, "123456789")]
        [InlineData(-0.0000005, "-5e-7")]
        [InlineData(0.000001, "0.000001")]
        [InlineData(1.5e300, "1.5e+300")]
        public void Numbers_use_ecmascript_form(double d, string expected)
        {
            Jcs.FormatDouble(d).ShouldBe(expected);
        }
    }

    public class Ed25519AndJwsTests
    {
        // RFC 8032 §7.1 TEST 1 (empty message).
        private const string Rfc8032Seed = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60";
        private const string Rfc8032Public = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a";
        private const string Rfc8032Sig = "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b";

        private static byte[] Hex(string h) => Enumerable.Range(0, h.Length / 2).Select(i => Convert.ToByte(h.Substring(i * 2, 2), 16)).ToArray();

        [Fact]
        public void Rfc8032_test1_signature_and_public_key()
        {
            Ed25519.PublicKeyFromSeed(Hex(Rfc8032Seed)).ShouldBe(Hex(Rfc8032Public));
            Ed25519.Sign(Hex(Rfc8032Seed), Array.Empty<byte>()).ShouldBe(Hex(Rfc8032Sig));
            Ed25519.Verify(Hex(Rfc8032Public), Array.Empty<byte>(), Hex(Rfc8032Sig)).ShouldBeTrue();
        }

        [Fact]
        public void Tampered_message_or_signature_fails()
        {
            var sig = Hex(Rfc8032Sig);
            Ed25519.Verify(Hex(Rfc8032Public), new byte[] { 1 }, sig).ShouldBeFalse();
            sig[0] ^= 1;
            Ed25519.Verify(Hex(Rfc8032Public), Array.Empty<byte>(), sig).ShouldBeFalse();
            Ed25519.Verify(new byte[31], Array.Empty<byte>(), sig).ShouldBeFalse();
        }

        [Fact]
        public void Shared_task_envelope_jws_verifies_over_received_bytes()
        {
            var v = Repo.LoadVector("task_envelope.json");
            var x = Base64Url.Decode(v.GetProperty("task_key").GetProperty("public_jwk").GetProperty("x").GetString()!);
            Ed25519.PublicKeyFromSeed(Hex(v.GetProperty("task_key").GetProperty("private_seed_hex").GetString()!)).ShouldBe(x);
            var jws = CompactJws.Parse(v.GetProperty("envelope").GetProperty("signature").GetString()!);
            jws.Alg.ShouldBe("EdDSA");
            jws.Typ.ShouldBe("onec-task+jwt");
            jws.Kid.ShouldBe(v.GetProperty("task_key").GetProperty("kid").GetString());
            CompactJws.VerifyEd25519(jws, x).ShouldBeTrue();
            var claims = jws.PayloadJson();
            foreach (var p in v.GetProperty("expected_claims").EnumerateObject())
            {
                claims.GetProperty(p.Name).GetRawText().ShouldBe(p.Value.GetRawText(), p.Name);
            }

            var flipped = CompactJws.Parse(v.GetProperty("negative").EnumerateArray().Single(n => n.GetProperty("name").GetString() == "signature_flipped").GetProperty("signature").GetString()!);
            CompactJws.VerifyEd25519(flipped, x).ShouldBeFalse();
        }

        [Fact]
        public void Payload_sha256_of_envelope_vector_matches_jcs()
        {
            var env = Repo.LoadVector("task_envelope.json").GetProperty("envelope");
            Hashing.Sha256Hex(Jcs.Canonicalize(env.GetProperty("payload"))).ShouldBe(env.GetProperty("payload_sha256").GetString());
        }

        [Fact]
        public void Wrong_alg_is_not_accepted()
        {
            var (seed, x) = Ed25519.Generate();
            var token = CompactJws.SignEd25519(new JsonObject { ["alg"] = "HS256", ["typ"] = "JWT" }, new JsonObject { ["a"] = 1 }, seed);
            CompactJws.VerifyEd25519(CompactJws.Parse(token), x).ShouldBeFalse();
        }

        [Fact]
        public void Malformed_jws_throws_format_exception()
        {
            Should.Throw<JwsFormatException>(() => CompactJws.Parse("a.b"));
            Should.Throw<JwsFormatException>(() => CompactJws.Parse("!!.e30.AA"));
        }

        [Fact]
        public void Jwk_thumbprint_matches_shared_root_key_vector()
        {
            var root = Repo.LoadVector("task_keyset.json").GetProperty("root_key");
            JwkThumbprint.Ed25519(root.GetProperty("public_jwk").GetProperty("x").GetString()!).ShouldBe(root.GetProperty("thumbprint").GetString());
        }

        [Fact]
        public void Base64url_round_trip_without_padding()
        {
            var bytes = Enumerable.Range(0, 33).Select(i => (byte)(i * 7)).ToArray();
            var s = Base64Url.Encode(bytes);
            s.ShouldNotContain("=");
            s.ShouldNotContain("+");
            Base64Url.Decode(s).ShouldBe(bytes);
            Should.Throw<FormatException>(() => Base64Url.Decode("a+b"));
        }
    }

    public class TaskKeysetTests
    {
        private static (RootKeys Roots, string Jws, DateTimeOffset Now) Vector()
        {
            var v = Repo.LoadVector("task_keyset.json");
            var root = v.GetProperty("root_key");
            var roots = new RootKeys(new[] { TrustKey.FromBase64Url(root.GetProperty("kid").GetString()!, root.GetProperty("public_jwk").GetProperty("x").GetString()!) });
            return (roots, v.GetProperty("task_keyset").GetString()!, DateTimeOffset.FromUnixTimeSeconds(v.GetProperty("now_unix_valid").GetInt64()));
        }

        [Fact]
        public void Shared_keyset_vector_verifies()
        {
            var (roots, jws, now) = Vector();
            var ks = TaskKeyset.Verify(jws, roots, now, 0);
            ks.Version.ShouldBe(3);
            var k = ks.Find("0192f0c4-7a00-7000-8000-000000000001").ShouldNotBeNull();
            Base64Url.Encode(k.X).ShouldBe("11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo");
            k.NotBefore.ShouldBe(DateTimeOffset.FromUnixTimeSeconds(1760413600));
        }

        [Fact]
        public void Downgrade_is_rejected()
        {
            var (roots, jws, now) = Vector();
            Should.Throw<KeysetException>(() => TaskKeyset.Verify(jws, roots, now, 4)).Reason.ShouldBe("downgrade");
        }

        [Fact]
        public void Expired_keyset_is_rejected()
        {
            var (roots, jws, _) = Vector();
            Should.Throw<KeysetException>(() => TaskKeyset.Verify(jws, roots, DateTimeOffset.FromUnixTimeSeconds(1776052001), 0)).Reason.ShouldBe("expired");
        }

        [Fact]
        public void Unknown_root_kid_is_rejected()
        {
            var (_, jws, now) = Vector();
            var (_, other) = Ed25519.Generate();
            Should.Throw<KeysetException>(() => TaskKeyset.Verify(jws, new RootKeys(new[] { new TrustKey("other", other) }), now, 0)).Reason.ShouldBe("kid");
        }

        [Fact]
        public void Keyset_signed_by_another_key_with_same_kid_is_rejected()
        {
            var (_, jws, now) = Vector();
            var (_, other) = Ed25519.Generate();
            Should.Throw<KeysetException>(() => TaskKeyset.Verify(jws, new RootKeys(new[] { new TrustKey("FtIu-VbGrfe_KB6CH7GNwODB72MNxj_ml11dEvO-7kk", other) }), now, 0)).Reason.ShouldBe("signature");
        }

        [Fact]
        public void Wrong_typ_is_rejected()
        {
            var (seed, x) = Ed25519.Generate();
            var roots = new RootKeys(new[] { new TrustKey("r", x) });
            var jws = CompactJws.SignEd25519(new JsonObject { ["alg"] = "EdDSA", ["typ"] = "JWT", ["kid"] = "r" }, new JsonObject { ["ver"] = 1, ["exp"] = 4102444800L, ["keys"] = new JsonArray() }, seed);
            Should.Throw<KeysetException>(() => TaskKeyset.Verify(jws, roots, DateTimeOffset.UtcNow, 0)).Reason.ShouldBe("typ");
        }
    }
}

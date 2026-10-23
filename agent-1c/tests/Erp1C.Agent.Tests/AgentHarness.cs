using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Agent.Net;
using Erp1C.Agent.State;
using Erp1C.Agent.Tasks;
using Erp1C.Core.Crypto;
using Erp1C.Core.Hosting;
using Erp1C.Core.Json;
using Erp1C.Core.Trust;
using Erp1C.Fiscal;
using Erp1C.Tests.Common;

namespace Erp1C.Agent.Tests
{
    /// <summary>Recorded request (body read eagerly, gzip undone).</summary>
    internal sealed class Recorded
    {
        public HttpMethod Method { get; set; } = HttpMethod.Get;

        public string Path { get; set; } = string.Empty;

        public Dictionary<string, string> Headers { get; } = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        public string Body { get; set; } = string.Empty;

        public bool Gzipped { get; set; }
    }

    /// <summary>In-memory server: routes by path, records every request.</summary>
    internal sealed class StubHandler : HttpMessageHandler
    {
        private readonly Func<Recorded, HttpResponseMessage> _respond;

        public StubHandler(Func<Recorded, HttpResponseMessage> respond)
        {
            _respond = respond;
        }

        public List<Recorded> Requests { get; } = new List<Recorded>();

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            var r = new Recorded { Method = request.Method, Path = request.RequestUri!.PathAndQuery };
            foreach (var h in request.Headers) r.Headers[h.Key] = string.Join(",", h.Value);
            if (request.Content != null)
            {
                foreach (var h in request.Content.Headers) r.Headers[h.Key] = string.Join(",", h.Value);
                var bytes = await request.Content.ReadAsByteArrayAsync();
                if (request.Content.Headers.ContentEncoding.Contains("gzip"))
                {
                    r.Gzipped = true;
                    using var gz = new GZipStream(new MemoryStream(bytes), CompressionMode.Decompress);
                    using var ms = new MemoryStream();
                    gz.CopyTo(ms);
                    bytes = ms.ToArray();
                }

                r.Body = Encoding.UTF8.GetString(bytes);
            }

            lock (Requests) Requests.Add(r);
            return _respond(r);
        }

        public static HttpResponseMessage Json(HttpStatusCode code, object body) =>
            new HttpResponseMessage(code) { Content = new StringContent(AgentJson.Serialize(body), Encoding.UTF8, "application/json") };

        public static HttpResponseMessage Raw(HttpStatusCode code, string json) =>
            new HttpResponseMessage(code) { Content = new StringContent(json, Encoding.UTF8, "application/json") };

        public static HttpResponseMessage Empty(HttpStatusCode code) => new HttpResponseMessage(code);
    }

    /// <summary>A paired agent wired to a stub server (no Windows/DPAPI dependency).</summary>
    internal sealed class AgentRig : IDisposable
    {
        public const string Server = "https://erp.test";
        public const string AgentId = "0192f0c4-7a00-7000-8000-0000000000bb";
        public const string TenantId = "0192f0c4-7a00-7000-8000-0000000000aa";

        public AgentRig(Func<Recorded, HttpResponseMessage>? api = null, DateTimeOffset? now = null)
        {
            Dir = new TempDir();
            var t = now ?? new DateTimeOffset(2026, 10, 18, 9, 0, 0, TimeSpan.Zero);
            Clock = new ClockSync(() => t + Advance);
            Paths = new AgentPaths(Dir.Path);
            Paths.Ensure();
            Settings = new SettingsStore(Paths.Settings);
            Settings.Update(s =>
            {
                s.AgentId = AgentId;
                s.AgentClientId = "onec-agent:" + AgentId;
                s.TenantName = "Test MChJ";
            });
            Keys = new AgentKeyStore(Paths.AgentKey, new XorProtector(), new string('a', 64));
            KeyFile = Keys.EnsureKey(t);
            Api = api ?? (_ => StubHandler.Empty(HttpStatusCode.NoContent));
            Handler = new StubHandler(Route);
            Http = new HttpClient(Handler);
            Auth = new AuthClient(Http, () => Server, Keys, Settings, Clock, new string('a', 64), (d, ct) => Task.CompletedTask);
            Client = new ApiClient(Http, () => Server, Auth, Clock);
        }

        public TimeSpan Advance { get; set; }

        public TempDir Dir { get; }

        public ClockSync Clock { get; }

        public AgentPaths Paths { get; }

        public SettingsStore Settings { get; }

        public AgentKeyStore Keys { get; }

        public AgentKeyFile KeyFile { get; }

        public Func<Recorded, HttpResponseMessage> Api { get; set; }

        public StubHandler Handler { get; }

        public HttpClient Http { get; }

        public AuthClient Auth { get; }

        public ApiClient Client { get; }

        public int TokenRequests { get; private set; }

        public static string AccessToken(string tenant = TenantId) =>
            "eyJhbGciOiJFZERTQSJ9." + Base64Url.EncodeUtf8("{\"tenant_id\":\"" + tenant + "\",\"agent_id\":\"" + AgentId + "\",\"device_id\":\"d\"}") + ".c2ln";

        private HttpResponseMessage Route(Recorded r)
        {
            if (r.Path == "/oauth/token")
            {
                TokenRequests++;
                return StubHandler.Json(HttpStatusCode.OK, new { access_token = AccessToken(), token_type = "Bearer", expires_in = 600, scope = "onec.agent" });
            }

            return Api(r);
        }

        public void Dispose()
        {
            Http.Dispose();
            Auth.Dispose();
            Dir.Dispose();
        }
    }

    /// <summary>Task envelopes signed with the shared vector key (shared/agent/task_envelope.json).</summary>
    internal static class Envelopes
    {
        public static JsonElement Vector => Repo.LoadVector("task_envelope.json");

        public static byte[] Seed => Enumerable.Range(0, 32).Select(i => Convert.ToByte(Vector.GetProperty("task_key").GetProperty("private_seed_hex").GetString()!.Substring(i * 2, 2), 16)).ToArray();

        public static string Kid => Vector.GetProperty("task_key").GetProperty("kid").GetString()!;

        public static DateTimeOffset NowValid => DateTimeOffset.FromUnixTimeSeconds(Vector.GetProperty("now_unix_valid").GetInt64());

        public static DateTimeOffset NowExpired => DateTimeOffset.FromUnixTimeSeconds(Vector.GetProperty("now_unix_expired").GetInt64());

        /// <summary>A keyset (signed by a test root) that holds the vector task key.</summary>
        public static (RootKeys Roots, TaskKeyset Keyset) Keyset(DateTimeOffset now)
        {
            var (rootSeed, rootX) = Ed25519.Generate();
            var rootKid = JwkThumbprint.Ed25519(rootX);
            var x = Vector.GetProperty("task_key").GetProperty("public_jwk").GetProperty("x").GetString()!;
            var payload = new JsonObject
            {
                ["ver"] = 3,
                ["iat"] = now.ToUnixTimeSeconds() - 60,
                ["exp"] = now.ToUnixTimeSeconds() + (180 * 86400),
                ["keys"] = new JsonArray(new JsonObject { ["kid"] = Kid, ["kty"] = "OKP", ["crv"] = "Ed25519", ["x"] = x, ["nbf"] = now.ToUnixTimeSeconds() - 3600, ["exp"] = now.ToUnixTimeSeconds() + (90 * 86400) }),
            };
            var jws = CompactJws.SignEd25519(new JsonObject { ["alg"] = "EdDSA", ["typ"] = "onec-task-keyset+jwt", ["kid"] = rootKid }, payload, rootSeed);
            var roots = new RootKeys(new[] { new TrustKey(rootKid, rootX) });
            return (roots, TaskKeyset.Verify(jws, roots, now, 0));
        }

        /// <summary>Builds a correctly signed envelope; <paramref name="mutateClaims"/>/<paramref name="mutateEnv"/> tamper after hashing.</summary>
        public static JsonElement Build(string kind, object payload, Action<JsonObject>? mutateClaims = null, Action<JsonObject>? mutateEnv = null, DateTimeOffset? now = null, string? baseId = null)
        {
            var n = now ?? NowValid;
            var taskId = Guid.NewGuid().ToString();
            var leaseId = Guid.NewGuid().ToString();
            var p = AgentJson.ToElement(payload);
            var psh = Hashing.Sha256Hex(Erp1C.Core.Json.Jcs.Canonicalize(p));
            var claims = new JsonObject
            {
                ["iss"] = "urn:erp:onec",
                ["aud"] = "urn:erp:onec-agent:" + AgentRig.AgentId,
                ["tid"] = taskId,
                ["att"] = 1,
                ["lid"] = leaseId,
                ["ten"] = AgentRig.TenantId,
                ["aid"] = AgentRig.AgentId,
                ["bid"] = baseId,
                ["knd"] = kind,
                ["psh"] = psh,
                ["iat"] = n.ToUnixTimeSeconds(),
                ["exp"] = n.ToUnixTimeSeconds() + 360,
            };
            mutateClaims?.Invoke(claims);
            var sig = CompactJws.SignEd25519(new JsonObject { ["alg"] = "EdDSA", ["typ"] = "onec-task+jwt", ["kid"] = Kid }, claims, Seed);
            var env = new JsonObject
            {
                ["task_id"] = taskId,
                ["kind"] = kind,
                ["purpose"] = "device_service",
                ["base_id"] = baseId,
                ["local_id"] = null,
                ["attempt"] = 1,
                ["lease_id"] = leaseId,
                ["lease_until"] = "2026-10-15T18:03:42Z",
                ["timeout_s"] = 60,
                ["payload"] = JsonNode.Parse(p.GetRawText()),
                ["payload_sha256"] = psh,
                ["kid"] = Kid,
                ["signature"] = sig,
            };
            mutateEnv?.Invoke(env);
            using var doc = JsonDocument.Parse(env.ToJsonString());
            return doc.RootElement.Clone();
        }
    }

    internal sealed class FixedKeys : ITaskKeyProvider
    {
        public FixedKeys(TaskKeyset? current)
        {
            Current = current;
        }

        public TaskKeyset? Current { get; set; }

        public int Refreshes { get; private set; }

        public TaskKeyset? AfterRefresh { get; set; }

        public Task<TaskKeyset?> RefreshAsync(CancellationToken ct)
        {
            Refreshes++;
            if (AfterRefresh != null) Current = AfterRefresh;
            return Task.FromResult(Current);
        }
    }

    internal sealed class FiscalCfg : IFiscalConfig
    {
        public IReadOnlyList<FiscalDeviceConfig> Devices { get; } = new List<FiscalDeviceConfig> { new FiscalDeviceConfig { LocalId = "fm1", Provider = "fake" } };

        public bool AllowFakeBridge => true;
    }
}

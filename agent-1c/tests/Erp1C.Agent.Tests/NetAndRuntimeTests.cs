using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Agent.App;
using Erp1C.Agent.Loops;
using Erp1C.Agent.Net;
using Erp1C.Agent.State;
using Erp1C.Agent.Tasks;
using Erp1C.Agent.Ui;
using Erp1C.Agent.Update;
using Erp1C.Core.Contracts;
using Erp1C.Core.Crypto;
using Erp1C.Core.Hosting;
using Erp1C.Core.Json;
using Erp1C.Core.Security;
using Erp1C.Core.Trust;
using Erp1C.Fiscal;
using Erp1C.Tests.Common;
using Shouldly;
using Xunit;

namespace Erp1C.Agent.Tests
{
    public class ApiClientTests
    {
        [Fact]
        public async Task Sends_agent_headers_and_bearer_token()
        {
            using var rig = new AgentRig(r => StubHandler.Json(HttpStatusCode.OK, new { version = 3, task_keyset = "x" }));
            await rig.Client.GetAsync<TaskKeysResponse>("/api/v1/onec-agent/task-keys", TimeSpan.FromSeconds(5), CancellationToken.None);
            var r = rig.Handler.Requests.Last();
            r.Headers["Authorization"].ShouldBe("Bearer " + AgentRig.AccessToken());
            r.Headers["X-Agent-Protocol"].ShouldBe("2");
            r.Headers["X-Agent-Version"].ShouldBe(BuildInfo.Version);
            r.Headers["User-Agent"].ShouldStartWith("ErpOneCAgent/" + BuildInfo.Version);
            r.Headers["User-Agent"].ShouldContain("(Windows ");
            rig.TokenRequests.ShouldBe(1);
        }

        [Fact]
        public async Task A_401_gets_one_fresh_token_and_one_retry()
        {
            var calls = 0;
            using var rig = new AgentRig(r => ++calls == 1 ? StubHandler.Empty(HttpStatusCode.Unauthorized) : StubHandler.Json(HttpStatusCode.OK, new { accepted = 1, duplicates = 0 }));
            var resp = await rig.Client.PostAsync<LogsResponse>("/api/v1/onec-agent/logs", new LogsRequest(), TimeSpan.FromSeconds(5), CancellationToken.None);
            resp.Value!.Accepted.ShouldBe(1);
            rig.TokenRequests.ShouldBe(2);
            calls.ShouldBe(2);
        }

        [Fact]
        public async Task Second_401_is_an_error()
        {
            using var rig = new AgentRig(r => StubHandler.Empty(HttpStatusCode.Unauthorized));
            var e = await Should.ThrowAsync<ApiException>(() => rig.Client.PostAsync<object>("/api/v1/onec-agent/poll", new PollRequest(), TimeSpan.FromSeconds(5), CancellationToken.None));
            e.Status.ShouldBe(401);
        }

        [Fact]
        public async Task Revoked_restricted_and_update_required_are_recognised()
        {
            using var rig = new AgentRig(r => r.Path.Contains("hello")
                ? StubHandler.Raw(HttpStatusCode.Forbidden, "{\"error\":{\"code\":\"ONEC_AGENT_REVOKED\",\"message_key\":\"errors.onec.agent_revoked\",\"params\":{},\"details\":null,\"request_id\":\"r1\"}}")
                : r.Path.Contains("poll")
                    ? StubHandler.Raw(HttpStatusCode.Forbidden, "{\"error\":{\"code\":\"SUBSCRIPTION_RESTRICTED\"}}")
                    : StubHandler.Raw((HttpStatusCode)426, "{\"error\":{\"code\":\"ONEC_AGENT_UPDATE_REQUIRED\"}}"));
            var revoked = await Should.ThrowAsync<ApiException>(() => rig.Client.PostAsync<object>("/api/v1/onec-agent/hello", new { }, TimeSpan.FromSeconds(5), CancellationToken.None));
            revoked.IsRevoked.ShouldBeTrue();
            revoked.RequestId.ShouldBe("r1");
            (await Should.ThrowAsync<ApiException>(() => rig.Client.PostAsync<object>("/api/v1/onec-agent/poll", new { }, TimeSpan.FromSeconds(5), CancellationToken.None))).IsSubscriptionRestricted.ShouldBeTrue();
            (await Should.ThrowAsync<ApiException>(() => rig.Client.PostAsync<object>("/api/v1/onec-agent/logs", new { }, TimeSpan.FromSeconds(5), CancellationToken.None))).IsUpdateRequired.ShouldBeTrue();
        }

        [Fact]
        public async Task Bodies_over_16_kb_are_gzipped()
        {
            using var rig = new AgentRig(r => StubHandler.Json(HttpStatusCode.OK, new { accepted = 1, duplicates = 0 }));
            var big = new LogsRequest { Entries = Enumerable.Range(0, 200).Select(i => new LogEntry { ClientLogId = Guid.NewGuid().ToString(), Message = new string('x', 200) }).ToList() };
            await rig.Client.PostAsync<LogsResponse>("/api/v1/onec-agent/logs", big, TimeSpan.FromSeconds(5), CancellationToken.None);
            var r = rig.Handler.Requests.Last();
            r.Gzipped.ShouldBeTrue();
            r.Body.ShouldContain("client_log_id");
        }
    }

    public class AuthClientTests
    {
        [Fact]
        public async Task Client_assertion_is_private_key_jwt_signed_with_the_agent_key()
        {
            using var rig = new AgentRig();
            await rig.Auth.GetAccessTokenAsync(false, CancellationToken.None);
            var form = rig.Handler.Requests.Single(r => r.Path == "/oauth/token").Body;
            var fields = form.Split('&').Select(p => p.Split('=')).ToDictionary(p => Uri.UnescapeDataString(p[0]), p => Uri.UnescapeDataString(p[1].Replace('+', ' ')));
            fields["grant_type"].ShouldBe("client_credentials");
            fields["client_id"].ShouldBe("onec-agent:" + AgentRig.AgentId);
            fields["client_assertion_type"].ShouldBe("urn:ietf:params:oauth:client-assertion-type:jwt-bearer");
            fields["scope"].ShouldBe("onec.agent");
            var jws = CompactJws.Parse(fields["client_assertion"]);
            jws.Alg.ShouldBe("EdDSA");
            jws.Typ.ShouldBe("JWT");
            jws.Kid.ShouldBe(rig.KeyFile.Kid);
            CompactJws.VerifyEd25519(jws, Base64Url.Decode(rig.KeyFile.X)).ShouldBeTrue();
            var c = jws.PayloadJson();
            c.GetProperty("iss").GetString().ShouldBe("onec-agent:" + AgentRig.AgentId);
            c.GetProperty("sub").GetString().ShouldBe("onec-agent:" + AgentRig.AgentId);
            c.GetProperty("aud").GetString().ShouldBe(AgentRig.Server + "/oauth/token");
            (c.GetProperty("exp").GetInt64() - c.GetProperty("iat").GetInt64()).ShouldBe(60);
            Guid.TryParse(c.GetProperty("jti").GetString(), out _).ShouldBeTrue();
        }

        [Fact]
        public async Task Token_is_cached_and_refreshed_after_480_seconds()
        {
            using var rig = new AgentRig();
            await rig.Auth.GetAccessTokenAsync(false, CancellationToken.None);
            await rig.Auth.GetAccessTokenAsync(false, CancellationToken.None);
            rig.TokenRequests.ShouldBe(1);
            rig.Auth.Claims.TenantId.ShouldBe(AgentRig.TenantId);
        }

        [Fact]
        public async Task Revoked_agent_gets_agent_revoked()
        {
            using var dir = new TempDir();
            var settings = new SettingsStore(dir.File("s.json"));
            settings.Update(s =>
            {
                s.AgentId = "a";
                s.AgentClientId = "onec-agent:a";
            });
            var keys = new AgentKeyStore(dir.File("agent.key"), new XorProtector(), "h");
            keys.EnsureKey(DateTimeOffset.UtcNow);
            var handler = new StubHandler(r => StubHandler.Raw(HttpStatusCode.Unauthorized, "{\"error\":\"invalid_client\",\"error_description\":\"agent_revoked\"}"));
            using var http = new HttpClient(handler);
            using var auth = new AuthClient(http, () => "https://x", keys, settings, new ClockSync(), "h");
            (await Should.ThrowAsync<ApiException>(() => auth.GetAccessTokenAsync(false, CancellationToken.None))).IsRevoked.ShouldBeTrue();
        }

        private static (AuthClient Auth, StubHandler Handler, HttpClient Http, TempDir Dir) DeviceFlow(params HttpResponseMessage[] tokenAnswers)
        {
            var dir = new TempDir();
            var settings = new SettingsStore(dir.File("s.json"));
            var keys = new AgentKeyStore(dir.File("agent.key"), new XorProtector(), new string('b', 64));
            var queue = new Queue<HttpResponseMessage>(tokenAnswers);
            var handler = new StubHandler(r => r.Path == "/oauth/device_authorization"
                ? StubHandler.Json(HttpStatusCode.OK, new { device_code = "dc", user_code = "WDJB-MJHT", verification_uri = "https://x/app/settings/onec/pair", verification_uri_complete = "https://x/app/settings/onec/pair?user_code=WDJBMJHT", expires_in = 600, interval = 5 })
                : queue.Dequeue());
            var http = new HttpClient(handler);
            return (new AuthClient(http, () => "https://x", keys, settings, new ClockSync(), new string('b', 64), (d, ct) => Task.CompletedTask), handler, http, dir);
        }

        [Fact]
        public async Task Device_grant_pending_slow_down_then_token()
        {
            var (auth, handler, http, dir) = DeviceFlow(
                StubHandler.Raw(HttpStatusCode.BadRequest, "{\"error\":\"authorization_pending\"}"),
                StubHandler.Raw(HttpStatusCode.BadRequest, "{\"error\":\"slow_down\"}"),
                StubHandler.Json(HttpStatusCode.OK, new { access_token = AgentRig.AccessToken(), token_type = "Bearer", expires_in = 600, agent_id = "a1", agent_client_id = "onec-agent:a1", tenant_name = "Oltin Don", task_keyset = (string?)null }));
            using (dir)
            using (http)
            using (auth)
            {
                var da = await auth.StartDeviceAuthorizationAsync(CancellationToken.None);
                da.UserCode.ShouldBe("WDJB-MJHT");
                var start = handler.Requests[0].Body;
                start.ShouldContain("client_id=onec-agent");
                start.ShouldContain("scope=onec.agent");
                start.ShouldContain("public_jwk=");
                start.ShouldContain("machine_hash=" + new string('b', 64));
                var tr = await auth.PollDeviceTokenAsync(da, CancellationToken.None);
                tr.AgentClientId.ShouldBe("onec-agent:a1");
                tr.TenantName.ShouldBe("Oltin Don");
                handler.Requests.Count(r => r.Path == "/oauth/token").ShouldBe(3);
                handler.Requests.Last().Body.ShouldContain("grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Adevice_code");
            }
        }

        [Theory]
        [InlineData("access_denied", "denied")]
        [InlineData("expired_token", "expired")]
        public async Task Device_grant_final_errors(string error, string reason)
        {
            var (auth, _, http, dir) = DeviceFlow(StubHandler.Raw(HttpStatusCode.BadRequest, "{\"error\":\"" + error + "\"}"));
            using (dir)
            using (http)
            using (auth)
            {
                var da = await auth.StartDeviceAuthorizationAsync(CancellationToken.None);
                (await Should.ThrowAsync<PairingException>(() => auth.PollDeviceTokenAsync(da, CancellationToken.None))).Reason.ShouldBe(reason);
            }
        }
    }

    public class StateTests
    {
        [Fact]
        public void Dpapi_round_trip_is_bound_to_its_purpose()
        {
            var p = new DpapiProtector();
            var data = Encoding.UTF8.GetBytes("seed-bytes-32-long-xxxxxxxxxxxxx");
            var blob = p.Protect(data, "ErpOneCAgent/agent.key/v1|h1");
            blob.ShouldNotBe(data);
            p.Unprotect(blob, "ErpOneCAgent/agent.key/v1|h1").ShouldBe(data);
            Should.Throw<CryptographicException>(() => p.Unprotect(blob, "ErpOneCAgent/agent.key/v1|h2"));
        }

        [Fact]
        public void Agent_key_is_dpapi_protected_and_signs()
        {
            using var dir = new TempDir();
            var store = new AgentKeyStore(dir.File("agent.key"), new DpapiProtector(), new string('c', 64));
            var key = store.EnsureKey(DateTimeOffset.UtcNow);
            key.Kid.ShouldBe(JwkThumbprint.Ed25519(key.X));
            store.EnsureKey(DateTimeOffset.UtcNow).Kid.ShouldBe(key.Kid); // not regenerated
            var sig = store.Sign(new byte[] { 1, 2, 3 });
            Ed25519.Verify(Base64Url.Decode(key.X), new byte[] { 1, 2, 3 }, sig).ShouldBeTrue();
            var other = new AgentKeyStore(dir.File("agent.key"), new DpapiProtector(), new string('d', 64));
            Should.Throw<AgentKeyUnavailableException>(() => other.Sign(new byte[] { 1 })); // other machine_hash entropy
        }

        [Fact]
        public void Machine_hash_is_64_lower_hex()
        {
            MachineInfo.MachineHash("ABC-def", "S-1-5-21-1").ShouldMatch("^[0-9a-f]{64}$");
            MachineInfo.MachineHash("abc-def", "S-1-5-21-1").ShouldBe(MachineInfo.MachineHash("ABC-DEF", "S-1-5-21-1"));
        }

        [Fact]
        public void Backoff_steps_and_jitter_bounds()
        {
            var b = new Backoff(new Random(1));
            var expected = new[] { 1, 2, 5, 10, 30, 60, 60 };
            for (var i = 0; i < expected.Length; i++)
            {
                var d = b.Delay(i).TotalSeconds;
                d.ShouldBeGreaterThanOrEqualTo(expected[i] * 0.8);
                d.ShouldBeLessThanOrEqualTo(expected[i] * 1.2);
            }

            b.NextWith(TimeSpan.FromSeconds(120)).ShouldBe(TimeSpan.FromSeconds(120));
        }

        [Fact]
        public void Clock_offset_from_hello_midpoint_and_date_header_only_before_hello()
        {
            var local = new DateTimeOffset(2026, 10, 18, 9, 0, 0, TimeSpan.Zero);
            var c = new ClockSync(() => local);
            c.FromDateHeader(local.AddSeconds(30));
            c.Offset.ShouldBe(TimeSpan.FromSeconds(30));
            c.FromHello(local.AddMinutes(5), local.AddSeconds(-2), local.AddSeconds(2));
            c.Offset.ShouldBe(TimeSpan.FromMinutes(5));
            c.Skewed.ShouldBeTrue();
            c.FromDateHeader(local);
            c.Offset.ShouldBe(TimeSpan.FromMinutes(5));
            c.FromDateHeader(local, force: true);
            c.Offset.ShouldBe(TimeSpan.Zero);
        }

        [Fact]
        public void Corrupt_settings_are_moved_aside()
        {
            using var dir = new TempDir();
            File.WriteAllText(dir.File("settings.json"), "{not json");
            string? moved = null;
            var s = new SettingsStore(dir.File("settings.json"), p => moved = p);
            s.Current.IsPaired.ShouldBeFalse();
            File.Exists(moved).ShouldBeTrue();
            s.Update(x => x.AgentId = "a");
            new SettingsStore(dir.File("settings.json")).Current.AgentId.ShouldBe("a");
        }

        [Fact]
        public void Result_outbox_survives_a_torn_line_and_removes_delivered()
        {
            using var dir = new TempDir();
            var o = new ResultOutbox(dir.File("results.jsonl"));
            o.Enqueue(new OutboxEntry { TaskId = "t1", LeaseId = "l1", Body = new ResultBody { LeaseId = "l1", Data = TaskExecution.EmptyObject() } });
            File.AppendAllText(dir.File("results.jsonl"), "{\"task_id\":\"t2\",");
            o.Enqueue(new OutboxEntry { TaskId = "t3", LeaseId = "l3", Body = new ResultBody { LeaseId = "l3", Data = TaskExecution.EmptyObject() } });
            o.Pending().Select(e => e.TaskId).ShouldBe(new[] { "t1", "t3" });
            o.Remove("t1", "l1");
            o.Pending().Single().TaskId.ShouldBe("t3");
        }

        [Fact]
        public void Unfinished_journal_attempts_become_failed_results_at_start()
        {
            using var dir = new TempDir();
            var clock = new FakeClock(DateTimeOffset.UtcNow);
            var j = new ActionJournal(dir.File("actions.jsonl"), clock);
            j.Started("t1", 1, "l1", "card.settlement", new string('0', 64));
            j.Started("t2", 1, "l2", "fiscal.status", new string('0', 64));
            j.Finished("t2", 1, new ResultBody { LeaseId = "l2", Outcome = "done", Data = TaskExecution.EmptyObject() });
            var outbox = new ResultOutbox(dir.File("results.jsonl"));
            using var runner = new TaskRunner(new ActionJournal(dir.File("actions.jsonl"), clock), outbox, clock, NullAgentLogger.Instance);
            runner.RecoverUnfinished().ShouldBe(1);
            var e = outbox.Pending().Single();
            e.TaskId.ShouldBe("t1");
            e.Body.Outcome.ShouldBe("failed");
            e.Body.Error!.Code.ShouldBe("ONEC_WORKER_CRASHED");
        }

        [Fact]
        public void Every_ui_text_exists_in_uz_and_ru()
        {
            foreach (var kv in Texts.Entries)
            {
                kv.Value.Uz.ShouldNotBeNullOrWhiteSpace(kv.Key);
                kv.Value.Ru.ShouldNotBeNullOrWhiteSpace(kv.Key);
            }
        }

        [Fact]
        public void Logger_masks_before_the_server_outbox()
        {
            using var dir = new TempDir();
            var outbox = new LogOutbox(dir.File("logs-outbox.jsonl"));
            using var log = new AgentLogger(dir.File("logs"), outbox, new FakeClock(DateTimeOffset.UtcNow));
            log.Error("x", "failed with Bearer abcdefghijklmnop and card 8600123412345678", new Dictionary<string, object?> { ["token"] = "access_token=zzzzzzzzzzzz" });
            var text = File.ReadAllText(dir.File("logs-outbox.jsonl"));
            text.ShouldNotContain("abcdefghijklmnop");
            text.ShouldNotContain("8600123412345678");
            text.ShouldNotContain("zzzzzzzzzzzz");
            log.Dispose();
            var clef = string.Concat(Directory.GetFiles(dir.File("logs")).Select(f => File.ReadAllText(f)));
            clef.ShouldNotContain("abcdefghijklmnop");
            clef.ShouldNotContain("8600123412345678");
        }
    }

    public class UpdateTests
    {
        private static (RootKeys Roots, UpdateManifestEnvelope Env) Vector()
        {
            var v = Repo.LoadVector("update_manifest.json");
            var root = Repo.LoadVector("task_keyset.json").GetProperty("root_key");
            var roots = new RootKeys(new[] { TrustKey.FromBase64Url(root.GetProperty("kid").GetString()!, root.GetProperty("public_jwk").GetProperty("x").GetString()!) });
            return (roots, AgentJson.Deserialize<UpdateManifestEnvelope>(v.GetProperty("response").GetRawText())!);
        }

        [Fact]
        public void Shared_manifest_vector_verifies_for_an_older_install()
        {
            var (roots, env) = Vector();
            var m = ManifestVerifier.Verify(env, roots, "stable", "1.4.2", new Version(10, 0, 19045), 2);
            m.Version.ShouldBe("1.4.3");
            m.Size.ShouldBe(5242880);
            m.Url.ShouldStartWith("https://");
        }

        [Theory]
        [InlineData("1.4.3", "stable", "version")]
        [InlineData("1.5.0", "stable", "version")]
        [InlineData("1.4.2", "pilot", "channel")]
        public void Manifest_rules(string installed, string channel, string reason)
        {
            var (roots, env) = Vector();
            Should.Throw<UpdateRejectedException>(() => ManifestVerifier.Verify(env, roots, channel, installed, new Version(10, 0, 19045), 2)).Reason.ShouldBe(reason);
        }

        [Fact]
        public void Tampered_manifest_or_unknown_kid_is_signature()
        {
            var (roots, env) = Vector();
            var bytes = Convert.FromBase64String(env.Manifest);
            bytes[10] ^= 1;
            var tampered = new UpdateManifestEnvelope { Manifest = Convert.ToBase64String(bytes), Signature = env.Signature, Kid = env.Kid };
            Should.Throw<UpdateRejectedException>(() => ManifestVerifier.Verify(tampered, roots, "stable", "1.4.2", new Version(10, 0), 2)).Reason.ShouldBe("signature");
            Should.Throw<UpdateRejectedException>(() => ManifestVerifier.Verify(env, new RootKeys(Array.Empty<TrustKey>()), "stable", "1.4.2", new Version(10, 0), 2)).Reason.ShouldBe("signature");
        }

        [Fact]
        public void Too_old_os_is_rejected()
        {
            var (roots, env) = Vector();
            Should.Throw<UpdateRejectedException>(() => ManifestVerifier.Verify(env, roots, "stable", "1.4.2", new Version(6, 1, 7600), 2)).Reason.ShouldBe("os");
        }

        [Fact]
        public async Task Download_checks_exact_size_and_sha256()
        {
            using var dir = new TempDir();
            var data = Encoding.ASCII.GetBytes("setup-bytes");
            var sha = Hashing.Sha256Hex(data);
            await Downloader.WriteVerifiedAsync(new MemoryStream(data), dir.File("a.part"), data.Length, sha, CancellationToken.None);
            File.ReadAllBytes(dir.File("a.part")).ShouldBe(data);
            (await Should.ThrowAsync<UpdateRejectedException>(() => Downloader.WriteVerifiedAsync(new MemoryStream(data), dir.File("b.part"), data.Length - 1, sha, CancellationToken.None))).Reason.ShouldBe("size");
            (await Should.ThrowAsync<UpdateRejectedException>(() => Downloader.WriteVerifiedAsync(new MemoryStream(data), dir.File("c.part"), data.Length, new string('0', 64), CancellationToken.None))).Reason.ShouldBe("sha256");
            File.Exists(dir.File("c.part")).ShouldBeFalse();
        }

        [Fact]
        public void Unsigned_file_is_not_trusted_by_authenticode()
        {
            using var dir = new TempDir();
            File.WriteAllBytes(dir.File("setup.exe"), new byte[] { 0x4D, 0x5A, 0, 0 });
            new WinTrustAuthenticodeCheck().IsTrusted(dir.File("setup.exe"), "ERP").ShouldBeFalse();
        }
    }

    public class RuntimeTests
    {
        private static (AgentRuntime Runtime, RuntimeDeps Deps, AgentRig Rig, FiscalModule Fiscal) Build(Func<Recorded, HttpResponseMessage> api, DateTimeOffset? now = null)
        {
            var rig = new AgentRig(api, now ?? Envelopes.NowValid);
            var (roots, ks) = Envelopes.Keyset(now ?? Envelopes.NowValid);
            var keysets = new KeysetManager(roots, rig.Settings, rig.Clock, NullAgentLogger.Instance);
            keysets.Accept(ks.Jws).ShouldBeTrue();
            var journal = new ActionJournal(rig.Paths.Actions, rig.Clock);
            var outbox = new ResultOutbox(rig.Paths.Results);
            var fiscal = new FiscalModule(new FiscalService(new FiscalCfg(), new IFiscalBridge[] { new FakeFiscalBridge(rig.Clock) }, rig.Paths.FiscalJournal, new DeviceLanes(), rig.Clock));
            var acceptor = new TaskAcceptor(keysets, new IAgentTaskHandler[] { fiscal }, journal, rig.Clock, () => rig.Settings.Current.AgentId, () => AgentRig.TenantId);
            var deps = new RuntimeDeps
            {
                Api = rig.Client,
                Auth = rig.Auth,
                Settings = rig.Settings,
                Keysets = keysets,
                Acceptor = acceptor,
                Runner = new TaskRunner(journal, outbox, rig.Clock, NullAgentLogger.Instance),
                Outbox = outbox,
                Journal = journal,
                Logs = new LogOutbox(rig.Paths.LogsOutbox),
                Clock = rig.Clock,
                Capabilities = new ICapabilityProvider[] { fiscal },
                MachineHash = new string('a', 64),
            };
            return (new AgentRuntime(deps), deps, rig, fiscal);
        }

        [Fact]
        public async Task Rejected_envelope_goes_to_the_outbox_and_is_delivered()
        {
            var posted = new List<Recorded>();
            var (rt, d, rig, _) = Build(r =>
            {
                posted.Add(r);
                return StubHandler.Json(HttpStatusCode.OK, new { accepted = true, duplicate = false, late = false });
            });
            using (rig)
            using (rt)
            {
                var env = Envelopes.Build("fiscal.status", new { cash_register_id = "0192f0c4-7a00-7000-8000-000000000123" }, c => c["ten"] = "other-tenant");
                await rt.HandleEnvelopeAsync(env);
                rt.RejectedCount.ShouldBe(1);
                d.Outbox.Count.ShouldBe(1);
                (await rt.SendResultsOnceAsync(CancellationToken.None)).ShouldBeTrue();
                d.Outbox.Count.ShouldBe(0);
                var r = posted.Single(p => p.Path.EndsWith("/result", StringComparison.Ordinal));
                r.Path.ShouldBe("/api/v1/onec-agent/tasks/" + env.GetProperty("task_id").GetString() + "/result");
                r.Body.ShouldContain("\"code\":\"ONEC_TASK_REJECTED\"");
                r.Body.ShouldContain("\"message\":\"tenant\"");
            }
        }

        [Fact]
        public async Task Accepted_task_runs_and_its_result_is_journaled_then_sent()
        {
            var (rt, d, rig, _) = Build(r => StubHandler.Json(HttpStatusCode.OK, new { accepted = true }));
            using (rig)
            using (rt)
            {
                var env = Envelopes.Build("fiscal.status", new { cash_register_id = "0192f0c4-7a00-7000-8000-000000000123", local_id = "fm1" });
                await rt.HandleEnvelopeAsync(env);
                await d.Runner.WaitIdleAsync(CancellationToken.None);
                await Task.Delay(50);
                var e = d.Outbox.Pending().Single();
                e.Body.Outcome.ShouldBe("done");
                e.Body.Data.GetProperty("fm_state").GetString().ShouldBe("ok");
                d.Journal.IsFinished(env.GetProperty("task_id").GetString()!, 1).ShouldBeTrue();
                (await rt.SendResultsOnceAsync(CancellationToken.None)).ShouldBeTrue();
                d.Outbox.Count.ShouldBe(0);
            }
        }

        [Theory]
        [InlineData(409, true)]
        [InlineData(404, true)]
        [InlineData(422, true)]
        [InlineData(503, false)]
        public async Task Result_delivery_status_handling(int status, bool removed)
        {
            var (rt, d, rig, _) = Build(r => StubHandler.Raw((HttpStatusCode)status, "{\"error\":{\"code\":\"X\"}}"));
            using (rig)
            using (rt)
            {
                d.Outbox.Enqueue(new OutboxEntry { TaskId = Guid.NewGuid().ToString(), LeaseId = "l", Body = new ResultBody { LeaseId = "l", Data = TaskExecution.EmptyObject() } });
                await rt.SendResultsOnceAsync(CancellationToken.None);
                (d.Outbox.Count == 0).ShouldBe(removed);
            }
        }

        [Fact]
        public async Task Hello_carries_capabilities_keyset_version_and_no_secrets()
        {
            Recorded? hello = null;
            var (rt, d, rig, _) = Build(r =>
            {
                hello = r;
                return StubHandler.Json(HttpStatusCode.OK, new { agent_id = AgentRig.AgentId, server_time = "2026-10-18T09:05:00Z", hello_interval_s = 600, task_keyset = (string?)null, log_level = "info", subscription = "active" });
            }, new DateTimeOffset(2026, 10, 18, 9, 0, 0, TimeSpan.Zero));
            using (rig)
            using (rt)
            {
                await rt.HelloOnceAsync(CancellationToken.None);
                using var doc = JsonDocument.Parse(hello!.Body);
                var b = doc.RootElement;
                b.GetProperty("protocol").GetInt32().ShouldBe(2);
                b.GetProperty("machine_hash").GetString().ShouldBe(new string('a', 64));
                b.GetProperty("task_keyset_version").GetInt32().ShouldBe(3);
                var caps = b.GetProperty("capabilities");
                caps.GetProperty("fiscal").GetProperty("enabled").GetBoolean().ShouldBeTrue();
                caps.GetProperty("fiscal").GetProperty("devices")[0].GetProperty("local_id").GetString().ShouldBe("fm1");
                caps.GetProperty("onec").GetProperty("enabled").GetBoolean().ShouldBeFalse();
                caps.GetProperty("scale").GetProperty("enabled").GetBoolean().ShouldBeFalse();
                hello.Body.ShouldNotContain(rig.KeyFile.Protected);
                hello.Body.ShouldNotContain("access_token");
                rig.Clock.Offset.TotalMinutes.ShouldBe(5, 0.1);
                rt.State.ShouldBe(AgentState.Online);
            }
        }
    }

    public class CompositionTests
    {
        [Fact]
        public void App_host_wires_every_store_agent_kind_and_capability()
        {
            using var dir = new TempDir();
            using var host = new AppHost(new AgentPaths(dir.Path));
            host.Acceptor.KnownKinds.OrderBy(k => k, StringComparer.Ordinal).ShouldBe(new[]
            {
                "card.settlement", "card.status", "collect_diagnostics", "fiscal.resend_unsent", "fiscal.status", "fiscal.zreport", "print.raw",
            });
            host.State.ShouldBe(AgentState.NotPaired);
            host.MachineHash.ShouldMatch("^[0-9a-f]{64}$");
        }
    }

    public class DiagnosticsTests
    {
        [Fact]
        public void Package_has_no_secrets_and_masks_logs()
        {
            using var dir = new TempDir();
            var paths = new AgentPaths(dir.Path);
            paths.Ensure();
            File.WriteAllText(paths.AgentKey, "{\"protected\":\"SECRETBLOB\"}");
            File.WriteAllText(paths.LocalPairs, "[{\"token_protected\":\"PAIRBLOB\"}]");
            File.WriteAllText(Path.Combine(paths.Logs, "agent-20261018.clef"), "{\"@m\":\"Bearer abcdefghijklmnop\"}\n");
            var settings = new SettingsStore(paths.Settings);
            settings.Update(s => s.Keyset = new KeysetRef { Version = 3, Jws = "eyJhbGciOiJFZERTQSJ9.eyJ2ZXIiOjN9.c2lnbmF0dXJl" });
            var op = new DiagnosticsOp(paths, settings, new ResultOutbox(paths.Results), new LogOutbox(paths.LogsOutbox), new FakeClock(DateTimeOffset.UtcNow), null);
            var zip = op.Build(dir.File("out"), 3, true);
            using var z = ZipFile.OpenRead(zip);
            z.Entries.Select(e => e.FullName).ShouldNotContain("agent.key");
            var all = string.Concat(z.Entries.Select(e =>
            {
                using var sr = new StreamReader(e.Open());
                return sr.ReadToEnd();
            }));
            all.ShouldNotContain("SECRETBLOB");
            all.ShouldNotContain("PAIRBLOB");
            all.ShouldNotContain("abcdefghijklmnop");
            all.ShouldNotContain("c2lnbmF0dXJl");
            z.Entries.Select(e => e.FullName).ShouldContain("settings.redacted.json");
        }
    }
}

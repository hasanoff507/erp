using System;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Agent.State;
using Erp1C.Agent.Tasks;
using Erp1C.Core.Contracts;
using Erp1C.Core.Hosting;
using Erp1C.Core.Json;
using Erp1C.Fiscal;
using Erp1C.Tests.Common;
using Shouldly;
using Xunit;

namespace Erp1C.Agent.Tests
{
    /// <summary>33 §9.11 / 34 §7.5 — every check positive and negative, shared vectors included.</summary>
    public class TaskAcceptorTests : IDisposable
    {
        private readonly TempDir _dir = new TempDir();
        private readonly FakeClock _clock = new FakeClock(Envelopes.NowValid);
        private readonly FixedKeys _keys;
        private readonly ActionJournal _journal;
        private string? _agentId = AgentRig.AgentId;
        private string? _tenantId = AgentRig.TenantId;

        public TaskAcceptorTests()
        {
            _keys = new FixedKeys(Envelopes.Keyset(Envelopes.NowValid).Keyset);
            _journal = new ActionJournal(_dir.File("actions.jsonl"), _clock);
        }

        public void Dispose() => _dir.Dispose();

        private TaskAcceptor Acceptor()
        {
            var fiscal = new FiscalModule(new FiscalService(new FiscalCfg(), new IFiscalBridge[] { new FakeFiscalBridge(_clock) }, _dir.File("fj.jsonl"), new DeviceLanes(), _clock));
            return new TaskAcceptor(_keys, new IAgentTaskHandler[] { fiscal }, _journal, _clock, () => _agentId, () => _tenantId);
        }

        private Task<AcceptResult> Accept(JsonElement env) => Acceptor().AcceptAsync(env, CancellationToken.None);

        private static object Payload => new { cash_register_id = "0192f0c4-7a00-7000-8000-000000000123" };

        [Fact]
        public async Task Shared_vector_envelope_is_accepted()
        {
            var r = await Accept(Envelopes.Vector.GetProperty("envelope"));
            r.Decision.ShouldBe(AcceptDecision.Accepted);
            r.Envelope!.Kind.ShouldBe("fiscal.status");
            r.Handler.ShouldNotBeNull();
        }

        private static JsonElement VectorWith(Action<JsonObject> change)
        {
            var o = JsonNode.Parse(Envelopes.Vector.GetProperty("envelope").GetRawText())!.AsObject();
            change(o);
            using var d = JsonDocument.Parse(o.ToJsonString());
            return d.RootElement.Clone();
        }

        [Fact]
        public async Task Vector_payload_tampered_is_payload_hash()
        {
            var neg = Envelopes.Vector.GetProperty("negative").EnumerateArray().Single(n => n.GetProperty("name").GetString() == "payload_tampered");
            var r = await Accept(VectorWith(o => o["payload"] = JsonNode.Parse(neg.GetProperty("payload").GetRawText())));
            AssertRejected(r, "payload_hash");
        }

        [Fact]
        public async Task Vector_wrong_agent_is_agent()
        {
            _agentId = "0192f0c4-7a00-7000-8000-0000000000ee";
            AssertRejected(await Accept(Envelopes.Vector.GetProperty("envelope")), "agent");
        }

        [Fact]
        public async Task Vector_wrong_tenant_is_tenant()
        {
            _tenantId = "0192f0c4-7a00-7000-8000-0000000000ef";
            AssertRejected(await Accept(Envelopes.Vector.GetProperty("envelope")), "tenant");
        }

        [Fact]
        public async Task Vector_signature_flipped_is_signature()
        {
            var neg = Envelopes.Vector.GetProperty("negative").EnumerateArray().Single(n => n.GetProperty("name").GetString() == "signature_flipped");
            AssertRejected(await Accept(VectorWith(o => o["signature"] = neg.GetProperty("signature").GetString())), "signature");
        }

        [Fact]
        public async Task Vector_unknown_kid_is_signature()
        {
            AssertRejected(await Accept(VectorWith(o => o["kid"] = "0192f0c4-7a00-7000-8000-000000000099")), "signature");
        }

        [Fact]
        public async Task Vector_expired_is_expired()
        {
            _clock.UtcNow = Envelopes.NowExpired;
            AssertRejected(await Accept(Envelopes.Vector.GetProperty("envelope")), "expired");
        }

        [Fact]
        public async Task Kid_missing_from_the_keyset_triggers_one_refresh_then_rejects()
        {
            _keys.Current = null;
            AssertRejected(await Accept(Envelopes.Build("fiscal.status", Payload)), "signature");
            _keys.Refreshes.ShouldBe(1);
        }

        [Fact]
        public async Task Kid_found_after_refresh_is_accepted()
        {
            var ks = _keys.Current;
            _keys.Current = null;
            _keys.AfterRefresh = ks;
            (await Accept(Envelopes.Build("fiscal.status", Payload))).Decision.ShouldBe(AcceptDecision.Accepted);
        }

        [Fact]
        public async Task Unknown_kind_is_rejected()
        {
            AssertRejected(await Accept(Envelopes.Build("write_object", Payload)), "kind");
            AssertRejected(await Accept(Envelopes.Build("scale.plu_upload", Payload)), "kind");
        }

        [Fact]
        public async Task Kind_claim_differs_from_envelope_is_rejected()
        {
            AssertRejected(await Accept(Envelopes.Build("fiscal.status", Payload, c => c["knd"] = "fiscal.zreport")), "kind");
        }

        [Fact]
        public async Task Wrong_issuer_or_audience_is_agent()
        {
            AssertRejected(await Accept(Envelopes.Build("fiscal.status", Payload, c => c["iss"] = "urn:evil")), "agent");
            AssertRejected(await Accept(Envelopes.Build("fiscal.status", Payload, c => c["aud"] = "urn:erp:onec-agent:other")), "agent");
        }

        [Fact]
        public async Task Task_lease_or_attempt_mismatch_is_agent()
        {
            AssertRejected(await Accept(Envelopes.Build("fiscal.status", Payload, c => c["lid"] = Guid.NewGuid().ToString())), "agent");
            AssertRejected(await Accept(Envelopes.Build("fiscal.status", Payload, c => c["att"] = 2)), "agent");
        }

        [Fact]
        public async Task A_base_id_on_a_store_agent_task_is_base()
        {
            AssertRejected(await Accept(Envelopes.Build("fiscal.status", Payload, baseId: Guid.NewGuid().ToString())), "base");
        }

        [Fact]
        public async Task Unknown_payload_member_is_schema_with_field()
        {
            var r = await Accept(Envelopes.Build("fiscal.status", new { cash_register_id = "0192f0c4-7a00-7000-8000-000000000123", extra = 1 }));
            AssertRejected(r, "schema");
            r.Result!.Error!.Field.ShouldBe("payload.extra");
        }

        [Fact]
        public async Task Non_integer_number_in_payload_is_schema()
        {
            AssertRejected(await Accept(Envelopes.Build("fiscal.status", new { cash_register_id = "0192f0c4-7a00-7000-8000-000000000123", local_id = 1.5 })), "schema");
        }

        [Fact]
        public async Task Missing_envelope_field_is_schema_and_without_lease_is_dropped()
        {
            AssertRejected(await Accept(Envelopes.Build("fiscal.status", Payload, mutateEnv: e => e.Remove("payload_sha256"))), "schema");
            (await Accept(Envelopes.Build("fiscal.status", Payload, mutateEnv: e => e.Remove("lease_id")))).Decision.ShouldBe(AcceptDecision.Dropped);
        }

        [Fact]
        public async Task Envelope_payload_sha256_must_equal_the_signed_psh()
        {
            AssertRejected(await Accept(Envelopes.Build("fiscal.status", Payload, mutateEnv: e => e["payload_sha256"] = new string('0', 64))), "payload_hash");
        }

        [Fact]
        public async Task Finished_attempt_is_answered_from_the_journal_with_the_new_lease()
        {
            var env = Envelopes.Build("fiscal.status", Payload);
            var taskId = env.GetProperty("task_id").GetString()!;
            _journal.Finished(taskId, 1, new ResultBody { LeaseId = "old", Attempt = 1, Outcome = "done", Data = AgentJson.ToElement(new { fm_state = "ok" }) });
            var r = await Accept(env);
            r.Decision.ShouldBe(AcceptDecision.Replay);
            r.Result!.LeaseId.ShouldBe(env.GetProperty("lease_id").GetString());
            r.Result.Data.GetProperty("fm_state").GetString().ShouldBe("ok");
        }

        [Fact]
        public async Task Rejection_result_has_the_33_9_11_shape()
        {
            _tenantId = "x";
            var r = await Accept(Envelopes.Build("fiscal.status", Payload));
            var json = AgentJson.Serialize(r.Result);
            using var d = JsonDocument.Parse(json);
            var root = d.RootElement;
            root.GetProperty("outcome").GetString().ShouldBe("failed");
            root.GetProperty("data").GetRawText().ShouldBe("{}");
            var err = root.GetProperty("error");
            err.GetProperty("code").GetString().ShouldBe("ONEC_TASK_REJECTED");
            err.GetProperty("message").GetString().ShouldBe("tenant");
            err.GetProperty("retryable_hint").GetBoolean().ShouldBeFalse();
            err.GetProperty("onec_messages").GetArrayLength().ShouldBe(0);
            err.TryGetProperty("params", out _).ShouldBeFalse();
            root.GetProperty("lease_id").GetString().ShouldBe(r.Envelope!.LeaseId);
        }

        private static void AssertRejected(AcceptResult r, string reason)
        {
            r.Decision.ShouldBe(AcceptDecision.Rejected);
            r.Reason.ShouldBe(reason);
            r.Result!.Outcome.ShouldBe("failed");
            r.Result.Error!.Code.ShouldBe("ONEC_TASK_REJECTED");
            r.Result.Error.Message.ShouldBe(reason);
        }
    }
}

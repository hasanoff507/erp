using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.CardTerminal.Drivers.Fake;
using Erp1C.Core.Hosting;
using Erp1C.Core.Json;
using Erp1C.Tests.Common;
using Shouldly;
using Xunit;

namespace Erp1C.CardTerminal.Tests
{
    internal sealed class Config : ICardTerminalConfig
    {
        public List<TerminalConfig> List { get; } = new List<TerminalConfig>();

        public IReadOnlyList<TerminalConfig> Terminals => List;

        public bool AllowFakeDriver { get; set; } = true;
    }

    /// <summary>One agent card layer over the fake terminal emulator (34 §14.4; 21 §9.4 fake table).</summary>
    internal sealed class Rig : IDisposable
    {
        public Rig(FakeCardTerminalDriver? driver = null)
        {
            Dir = new TempDir();
            Clock = new FakeClock(new DateTimeOffset(2026, 10, 18, 9, 0, 0, TimeSpan.Zero));
            Driver = driver ?? new FakeCardTerminalDriver(TimeSpan.Zero, () => Clock.UtcNow);
            Config.List.Add(new TerminalConfig { LocalId = "t1", Driver = "fake", Host = "192.168.1.60", Port = 27015, Tid = "T0000001" });
            Journal = new CardJournal(Dir.File("card_journal.jsonl"), Clock);
            Service = new CardTerminalService(Config, new DriverRegistry(new ICardTerminalDriver[] { Driver }), Journal, new DeviceLanes(), Clock, null, new CardTimeouts { SafeRetryDelay = TimeSpan.Zero }, (d, ct) => Task.CompletedTask);
        }

        public TempDir Dir { get; }

        public FakeClock Clock { get; }

        public FakeCardTerminalDriver Driver { get; }

        public Config Config { get; } = new Config();

        public CardJournal Journal { get; }

        public CardTerminalService Service { get; }

        public static CardPurchase Purchase(long amountTiyin, Guid? id = null) => new CardPurchase { AttemptId = id ?? Guid.NewGuid(), AmountTiyin = amountTiyin, CashRegisterId = Guid.NewGuid().ToString() };

        public Task<CardCallResult> Buy(long amountTiyin, Guid? id = null) => Service.PurchaseAsync("t1", Purchase(amountTiyin, id), CancellationToken.None);

        public void Dispose() => Dir.Dispose();
    }

    public class CardPurchaseTests
    {
        [Fact]
        public async Task Approved_purchase_normalises_the_mask_and_journals_no_pan()
        {
            using var rig = new Rig();
            var r = await rig.Buy(12_000_00);
            r.Status.ShouldBe(200);
            r.Tx!.Status.ShouldBe("approved");
            r.Tx.CardMask.ShouldBe("8600********1234");
            r.Tx.CardScheme.ShouldBe("uzcard");
            r.Tx.AmountTiyin.ShouldBe(12_000_00);
            r.Tx.Rrn!.ShouldMatch("^[0-9A-Za-z]{6,32}$");
            var journal = File.ReadAllText(rig.Journal.Path);
            journal.ShouldNotContain("860031");
            journal.ShouldContain("8600********1234");
        }

        [Fact]
        public async Task Declined_is_200_with_status_declined()
        {
            using var rig = new Rig();
            var r = await rig.Buy(15_001_00);
            r.Status.ShouldBe(200);
            r.Tx!.Status.ShouldBe("declined");
            r.Tx.DeclineCode.ShouldBe("51");
        }

        [Fact]
        public async Task Same_attempt_id_hits_the_terminal_once()
        {
            using var rig = new Rig();
            var id = Guid.NewGuid();
            var a = await rig.Buy(10_000_00, id);
            var b = await rig.Buy(10_000_00, id);
            rig.Driver.PurchaseCalls.ShouldBe(1);
            b.Tx!.Rrn.ShouldBe(a.Tx!.Rrn);
        }

        [Fact]
        public async Task Reused_attempt_id_with_another_amount_is_rejected()
        {
            using var rig = new Rig();
            var id = Guid.NewGuid();
            await rig.Buy(10_000_00, id);
            var b = await rig.Buy(11_000_00, id);
            b.Status.ShouldBe(422);
            rig.Driver.PurchaseCalls.ShouldBe(1);
        }

        [Fact]
        public async Task Timeout_gives_504_unknown_and_is_never_resent_then_status_query_resolves_it()
        {
            using var rig = new Rig();
            var id = Guid.NewGuid();
            var r = await rig.Buy(20_002_00, id);
            r.Status.ShouldBe(504);
            r.ErrorCode.ShouldBe("CARD_TERMINAL_TIMEOUT");
            rig.Journal.Get(id.ToString())!.Result!.Status.ShouldBe("unknown");

            var again = await rig.Buy(20_002_00, id);
            again.Status.ShouldBe(504);
            rig.Driver.PurchaseCalls.ShouldBe(1); // purchase is never automatically repeated

            var tx = await rig.Service.GetTxAsync(id.ToString(), CancellationToken.None);
            tx.Status.ShouldBe(200);
            tx.Tx!.Status.ShouldBe("approved");
            rig.Journal.Get(id.ToString())!.ResolvedBy.ShouldBe("status_query");
            rig.Driver.PurchaseCalls.ShouldBe(1);

            (await rig.Buy(20_002_00, id)).Status.ShouldBe(200); // replay now returns the resolved result
        }

        [Fact]
        public async Task Unresolvable_unknown_stays_unknown_for_the_manager()
        {
            using var rig = new Rig();
            var id = Guid.NewGuid();
            (await rig.Buy(30_003_00, id)).Status.ShouldBe(504);
            var tx = await rig.Service.GetTxAsync(id.ToString(), CancellationToken.None);
            tx.Tx!.Status.ShouldBe("unknown");
        }

        [Fact]
        public async Task Status_query_not_found_becomes_declined_not_found()
        {
            using var rig = new Rig();
            var id = Guid.NewGuid();
            (await rig.Buy(40_010_00, id)).Status.ShouldBe(504);
            var tx = await rig.Service.GetTxAsync(id.ToString(), CancellationToken.None);
            tx.Tx!.Status.ShouldBe("declined");
            tx.Tx.DeclineCode.ShouldBe("not_found");
        }

        [Fact]
        public async Task Terminal_busy_is_409()
        {
            using var rig = new Rig();
            var r = await rig.Buy(50_004_00);
            r.Status.ShouldBe(409);
            r.ErrorCode.ShouldBe("CARD_TERMINAL_BUSY");
        }

        [Fact]
        public async Task Second_purchase_while_one_runs_is_busy_and_not_queued()
        {
            using var rig = new Rig(new FakeCardTerminalDriver(TimeSpan.FromMilliseconds(400)));
            var first = rig.Buy(10_000_00);
            await Task.Delay(100);
            var second = await rig.Buy(10_000_00);
            second.Status.ShouldBe(409);
            second.ErrorCode.ShouldBe("CARD_TERMINAL_BUSY");
            (await first).Status.ShouldBe(200);
            rig.Driver.PurchaseCalls.ShouldBe(1);
        }

        [Fact]
        public async Task Amount_mismatch_is_voided_automatically_and_422()
        {
            using var rig = new Rig();
            var id = Guid.NewGuid();
            var r = await rig.Buy(60_005_00, id);
            r.Status.ShouldBe(422);
            r.ErrorCode.ShouldBe("CARD_AMOUNT_MISMATCH");
            r.Params!["void_status"].ShouldBe("voided");
            rig.Driver.VoidCalls.ShouldBe(1);
            rig.Journal.Get(id.ToString())!.VoidedBy.ShouldNotBeNull();

            // the POS's own void for the same original answers from the journal (no second terminal void)
            var v = await rig.Service.VoidAsync("t1", new CardVoid { AttemptId = Guid.NewGuid(), AmountTiyin = 59_905_00, OriginalAttemptId = id }, CancellationToken.None);
            v.Status.ShouldBe(200);
            rig.Driver.VoidCalls.ShouldBe(1);
        }

        [Fact]
        public async Task Void_after_sale_cancel_and_void_failure()
        {
            using var rig = new Rig();
            var ok = Guid.NewGuid();
            await rig.Buy(70_000_00, ok);
            var v = await rig.Service.VoidAsync("t1", new CardVoid { AttemptId = Guid.NewGuid(), AmountTiyin = 70_000_00, OriginalAttemptId = ok }, CancellationToken.None);
            v.Status.ShouldBe(200);
            v.Tx!.Kind.ShouldBe("void");

            var bad = Guid.NewGuid();
            await rig.Buy(80_006_00, bad);
            var f = await rig.Service.VoidAsync("t1", new CardVoid { AttemptId = Guid.NewGuid(), AmountTiyin = 80_006_00, OriginalAttemptId = bad }, CancellationToken.None);
            f.Status.ShouldBe(502);
            f.ErrorCode.ShouldBe("CARD_VOID_FAILED");
        }

        [Fact]
        public async Task Refund_by_original_attempt_uses_its_rrn()
        {
            using var rig = new Rig();
            var orig = Guid.NewGuid();
            var p = await rig.Buy(90_000_00, orig);
            var r = await rig.Service.RefundAsync("t1", new CardRefund { AttemptId = Guid.NewGuid(), AmountTiyin = 30_000_00, OriginalAttemptId = orig }, CancellationToken.None);
            r.Status.ShouldBe(200);
            r.Tx!.Kind.ShouldBe("refund");
            rig.Journal.All().Single(a => a.Kind == "refund").OriginalRrn.ShouldBe(p.Tx!.Rrn);
        }

        [Fact]
        public async Task Refund_without_any_original_is_422()
        {
            using var rig = new Rig();
            var r = await rig.Service.RefundAsync("t1", new CardRefund { AttemptId = Guid.NewGuid(), AmountTiyin = 100 }, CancellationToken.None);
            r.Status.ShouldBe(422);
        }

        [Theory]
        [InlineData(10_007_00, "cancelled")]
        [InlineData(10_008_00, "error")]
        [InlineData(10_011_00, "declined")]
        public async Task Terminal_side_failures_are_final(long amount, string status)
        {
            using var rig = new Rig();
            var r = await rig.Buy(amount);
            r.Status.ShouldBe(200);
            r.Tx!.Status.ShouldBe(status);
        }

        [Fact]
        public async Task Social_card_type_from_terminal_is_kept()
        {
            using var rig = new Rig();
            (await rig.Buy(10_009_00)).Tx!.CardType.ShouldBe("social");
        }

        [Fact]
        public async Task Unreachable_terminal_is_503_and_nothing_charged()
        {
            using var rig = new Rig();
            rig.Driver.Scenario(FakeOutcome.Unreachable);
            var r = await rig.Buy(10_000_00);
            r.Status.ShouldBe(503);
            r.ErrorCode.ShouldBe("CARD_TERMINAL_UNREACHABLE");
        }

        [Fact]
        public async Task Cancel_pending_on_a_finished_attempt_is_not_cancellable()
        {
            using var rig = new Rig();
            var id = Guid.NewGuid();
            await rig.Buy(10_000_00, id);
            (await rig.Service.CancelPendingAsync(id.ToString(), CancellationToken.None)).ShouldBe("not_cancellable");
        }

        [Fact]
        public async Task Cancel_pending_during_the_customer_wait_cancels()
        {
            using var rig = new Rig(new FakeCardTerminalDriver(TimeSpan.FromMilliseconds(300)));
            var id = Guid.NewGuid();
            var buy = rig.Buy(10_000_00, id);
            await Task.Delay(80);
            (await rig.Service.CancelPendingAsync(id.ToString(), CancellationToken.None)).ShouldBe("cancelled");
            (await buy).Tx!.Status.ShouldBe("cancelled");
        }

        [Fact]
        public async Task Settlement_reports_gross_purchases_and_refunds()
        {
            using var rig = new Rig();
            var a = Guid.NewGuid();
            await rig.Buy(10_000_00, a);
            await rig.Buy(5_000_00);
            await rig.Service.RefundAsync("t1", new CardRefund { AttemptId = Guid.NewGuid(), AmountTiyin = 2_000_00, OriginalAttemptId = a }, CancellationToken.None);
            var s = await rig.Service.SettlementAsync("t1", CancellationToken.None);
            s.Count.ShouldBe(2);
            s.TotalTiyin.ShouldBe(15_000_00);
            s.RefundCount.ShouldBe(1);
            s.RefundTotalTiyin.ShouldBe(2_000_00);
            s.ByScheme.Single().CardScheme.ShouldBe("uzcard");
            rig.Journal.LastSettlement("t1").ShouldNotBeNull();
        }

        [Fact]
        public async Task Journal_survives_a_restart_and_keeps_idempotency()
        {
            using var rig = new Rig();
            var id = Guid.NewGuid();
            await rig.Buy(10_000_00, id);
            var reloaded = new CardJournal(rig.Journal.Path, rig.Clock);
            reloaded.Get(id.ToString())!.Result!.Status.ShouldBe("approved");
        }

        [Fact]
        public async Task Journal_entries_older_than_90_days_are_pruned()
        {
            using var rig = new Rig();
            var id = Guid.NewGuid();
            await rig.Buy(10_000_00, id);
            rig.Clock.Advance(TimeSpan.FromDays(91));
            new CardJournal(rig.Journal.Path, rig.Clock).Get(id.ToString()).ShouldBeNull();
        }
    }

    public class CardTerminalPolicyTests
    {
        [Fact]
        public async Task Terminal_on_a_public_or_loopback_address_is_never_used()
        {
            using var rig = new Rig();
            rig.Config.List[0].Host = "8.8.8.8";
            rig.Service.Enabled.ShouldBeFalse();
            (await rig.Buy(10_000_00)).Status.ShouldBe(404);
            rig.Config.List[0].Host = "127.0.0.1";
            rig.Service.Enabled.ShouldBeFalse();
            rig.Driver.PurchaseCalls.ShouldBe(0);
        }

        [Fact]
        public void Fake_driver_is_not_announced_outside_dev_or_demo()
        {
            using var rig = new Rig();
            rig.Config.AllowFakeDriver = false;
            rig.Service.Enabled.ShouldBeFalse();
            JsonSerializer.Serialize(new CardTaskHandler(rig.Service).Describe()).ShouldContain("\"enabled\":false");
        }

        [Theory]
        [InlineData("860031******1234", "8600********1234")]
        [InlineData("8600123412345678", "8600********5678")]
        [InlineData("9860 1234 5678 9012", "9860********9012")]
        [InlineData("4111XXXXXXXX1111", "4111********1111")]
        [InlineData("garbage", null)]
        public void Mask_normalisation(string raw, string? expected) => CardNormalizer.NormalizeMask(raw).ShouldBe(expected);

        [Fact]
        public void A_driver_returning_a_full_pan_never_leaks_it()
        {
            var r = CardNormalizer.Normalize(new CardTxResult { Status = "approved", CardMask = "9860123456789012", SlipText = "Card 9860123456789012" }, "a", "purchase");
            r.CardMask.ShouldBe("9860********9012");
            r.CardScheme.ShouldBe("humo");
            r.SlipText!.ShouldNotContain("9860123456789012");
        }
    }

    public class CardTaskTests
    {
        private static JsonElement J(object o) => AgentJson.ToElement(o);

        [Fact]
        public async Task Card_status_reports_health_and_resolved_unknown_attempts_once()
        {
            using var rig = new Rig();
            var id = Guid.NewGuid();
            (await rig.Buy(20_002_00, id)).Status.ShouldBe(504);
            var handler = new CardTaskHandler(rig.Service);
            var payload = J(new { terminals = new[] { new { card_terminal_id = Guid.NewGuid().ToString(), local_id = "t1" } } });
            handler.ValidatePayload("card.status", payload).ShouldBeNull();
            var exec = await handler.ExecuteAsync(new TaskContext(Guid.NewGuid().ToString(), "card.status", 1, Guid.NewGuid().ToString()), payload, CancellationToken.None);
            exec.Outcome.ShouldBe("done");
            exec.Data.GetProperty("terminals")[0].GetProperty("status").GetString().ShouldBe("online");
            var unresolved = exec.Data.GetProperty("unresolved");
            unresolved.GetArrayLength().ShouldBe(1);
            unresolved[0].GetProperty("attempt_id").GetString().ShouldBe(id.ToString());
            unresolved[0].GetProperty("status").GetString().ShouldBe("approved");
            unresolved[0].GetProperty("resolved_by").GetString().ShouldBe("status_query");

            var again = await handler.ExecuteAsync(new TaskContext(Guid.NewGuid().ToString(), "card.status", 1, Guid.NewGuid().ToString()), payload, CancellationToken.None);
            again.Data.GetProperty("unresolved").GetArrayLength().ShouldBe(0);
        }

        [Fact]
        public async Task Card_settlement_task_result_shape()
        {
            using var rig = new Rig();
            await rig.Buy(10_000_00);
            var handler = new CardTaskHandler(rig.Service);
            var payload = J(new { card_terminal_id = Guid.NewGuid().ToString(), local_id = "t1", shift_id = (string?)null });
            handler.ValidatePayload("card.settlement", payload).ShouldBeNull();
            var exec = await handler.ExecuteAsync(new TaskContext(Guid.NewGuid().ToString(), "card.settlement", 1, Guid.NewGuid().ToString()), payload, CancellationToken.None);
            exec.Outcome.ShouldBe("done");
            exec.Data.GetProperty("total_tiyin").GetInt64().ShouldBe(10_000_00);
            exec.Data.GetProperty("refund_count").GetInt32().ShouldBe(0);
            exec.Data.GetProperty("local_id").GetString().ShouldBe("t1");
        }

        [Fact]
        public async Task Card_settlement_on_an_unknown_terminal_fails_with_not_found()
        {
            using var rig = new Rig();
            var handler = new CardTaskHandler(rig.Service);
            var exec = await handler.ExecuteAsync(new TaskContext("t", "card.settlement", 1, "l"), J(new { card_terminal_id = Guid.NewGuid().ToString(), local_id = "nope" }), CancellationToken.None);
            exec.Outcome.ShouldBe("failed");
            exec.Error!.Code.ShouldBe("NOT_FOUND");
        }

        [Fact]
        public void Payload_schema_is_strict()
        {
            using var rig = new Rig();
            var handler = new CardTaskHandler(rig.Service);
            handler.ValidatePayload("card.settlement", J(new { card_terminal_id = Guid.NewGuid().ToString(), local_id = "t1", amount = 5 })).ShouldBe("payload.amount");
            handler.ValidatePayload("card.status", J(new { terminals = new[] { new { local_id = "t1" } } })).ShouldBe("payload.terminals");
        }

        [Fact]
        public void Card_terminal_capability_lists_the_configured_device()
        {
            using var rig = new Rig();
            var d = AgentJson.ToElement(new CardTaskHandler(rig.Service).Describe());
            d.GetProperty("enabled").GetBoolean().ShouldBeTrue();
            d.GetProperty("devices")[0].GetProperty("driver").GetString().ShouldBe("fake");
            d.GetProperty("devices")[0].GetProperty("host").GetString().ShouldBe("192.168.1.60");
        }
    }
}

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Core.Hosting;
using Erp1C.Core.Json;
using Erp1C.Tests.Common;
using Shouldly;
using Xunit;

namespace Erp1C.Fiscal.Tests
{
    internal sealed class Cfg : IFiscalConfig
    {
        public List<FiscalDeviceConfig> List { get; } = new List<FiscalDeviceConfig>();

        public IReadOnlyList<FiscalDeviceConfig> Devices => List;

        public bool AllowFakeBridge { get; set; } = true;
    }

    internal sealed class FiscalRig : IDisposable
    {
        public const string Register = "0192f0c4-7a00-7000-8000-000000000123";

        public FiscalRig()
        {
            Dir = new TempDir();
            Clock = new FakeClock(new DateTimeOffset(2026, 10, 18, 9, 0, 0, TimeSpan.Zero));
            Bridge = new FakeFiscalBridge(Clock, Dir.File("fake-fm.json"));
            Cfg.List.Add(new FiscalDeviceConfig { LocalId = "fm1", Provider = "fake", Name = "FM" });
            Service = new FiscalService(Cfg, new IFiscalBridge[] { Bridge, new UnavailableFiscalBridge("multikassa_local") }, Dir.File("fiscal_journal.jsonl"), new DeviceLanes(), Clock);
            Module = new FiscalModule(Service);
        }

        public TempDir Dir { get; }

        public FakeClock Clock { get; }

        public FakeFiscalBridge Bridge { get; }

        public Cfg Cfg { get; } = new Cfg();

        public FiscalService Service { get; }

        public FiscalModule Module { get; }

        public static CashRegisterRef Ref => new CashRegisterRef { CashRegisterId = Register, LocalId = "fm1" };

        public static JsonElement SaleBody(long seq, long amount = 12_000_00, string kind = "sale", string? mask = null, object? refundInfo = null)
        {
            var body = new Dictionary<string, object?>
            {
                ["cash_register"] = new { cash_register_id = Register, local_id = "fm1" },
                ["receipt_seq"] = seq,
                ["kind"] = kind,
                ["items"] = new[]
                {
                    new { name = "Coca-Cola 1,5 l", mxik = "02202001001000000", package_code = "1234567", unit_code = "796", qty_milli = 2000, price_tiyin = amount / 2, amount_tiyin = amount, vat_rate = 12, vat_tiyin = amount * 12 / 112, marking_codes = new[] { "0104600000000001215abc\u001d91EE07" } },
                },
                ["payments"] = new { payment_form = mask is null ? "cash" : "card", cash_tiyin = mask is null ? amount : 0, card_tiyin = mask is null ? 0 : amount, qr_tiyin = 0, card_type = mask is null ? null : "personal", card_mask = mask, rrn = mask is null ? null : "123456789012" },
            };
            if (refundInfo != null) body["refund_info"] = refundInfo;
            return AgentJson.ToElement(body);
        }

        public async Task<FiscalResult> Sale(long seq, long amount = 12_000_00)
        {
            var b = SaleBody(seq, amount);
            return await Service.RegisterAsync(FiscalModule.ParseReceipt(new BodyReader(b), false), b, false, CancellationToken.None);
        }

        public void Dispose() => Dir.Dispose();
    }

    public class FiscalSaleTests
    {
        [Fact]
        public async Task Fake_fm_signs_a_sale_with_fiscal_requisites()
        {
            using var rig = new FiscalRig();
            await rig.Service.OpenShiftAsync(FiscalRig.Ref, 1, "Kassir", CancellationToken.None);
            var r = await rig.Sale(1);
            r.FmTerminalId.ShouldMatch("^ZZ[0-9]{12}$");
            r.FmReceiptSeq.ShouldBe(1);
            r.FiscalSign.ShouldMatch("^[0-9]{12}$");
            r.QrUrl.ShouldMatch("^https://ofd\\.soliq\\.uz/check\\?t=ZZ[0-9]{12}&r=1&c=[0-9]{14}&s=[0-9]{12}$");
            r.FiscalAt.ShouldBe("2026-10-18T09:00:00Z");
        }

        [Fact]
        public async Task Same_receipt_seq_and_body_answers_from_the_journal_without_signing_again()
        {
            using var rig = new FiscalRig();
            await rig.Service.OpenShiftAsync(FiscalRig.Ref, 1, "K", CancellationToken.None);
            var a = await rig.Sale(7);
            var b = await rig.Sale(7);
            b.FiscalSign.ShouldBe(a.FiscalSign);
            rig.Bridge.SaleCalls.ShouldBe(1);
        }

        [Fact]
        public async Task Same_receipt_seq_with_another_body_is_receipt_seq_conflict()
        {
            using var rig = new FiscalRig();
            await rig.Service.OpenShiftAsync(FiscalRig.Ref, 1, "K", CancellationToken.None);
            await rig.Sale(7);
            var e = await Should.ThrowAsync<LocalApiException>(() => rig.Sale(7, 99_000_00));
            e.Code.ShouldBe("RECEIPT_SEQ_CONFLICT");
            e.Status.ShouldBe(409);
        }

        [Fact]
        public async Task Interrupted_call_is_resolved_from_the_fm_before_signing_again()
        {
            using var rig = new FiscalRig();
            await rig.Service.OpenShiftAsync(FiscalRig.Ref, 1, "K", CancellationToken.None);
            var first = await rig.Sale(3);

            // simulate a crash after "sent": a fresh service over a journal that has only the "sent" line
            var lines = System.IO.File.ReadAllLines(rig.Dir.File("fiscal_journal.jsonl")).Where(l => !l.Contains("\"e\":\"result\"")).ToArray();
            System.IO.File.WriteAllLines(rig.Dir.File("fiscal_journal2.jsonl"), lines);
            var svc = new FiscalService(rig.Cfg, new IFiscalBridge[] { rig.Bridge }, rig.Dir.File("fiscal_journal2.jsonl"), new DeviceLanes(), rig.Clock);
            var b = FiscalRig.SaleBody(3);
            var again = await svc.RegisterAsync(FiscalModule.ParseReceipt(new BodyReader(b), false), b, false, CancellationToken.None);
            again.FiscalSign.ShouldBe(first.FiscalSign);
            rig.Bridge.SaleCalls.ShouldBe(1);
        }

        [Fact]
        public async Task Refund_needs_refund_info_and_return_kind()
        {
            using var rig = new FiscalRig();
            await rig.Service.OpenShiftAsync(FiscalRig.Ref, 1, "K", CancellationToken.None);
            var sale = await rig.Sale(1);
            var body = FiscalRig.SaleBody(2, kind: "return", refundInfo: new { fm_terminal_id = sale.FmTerminalId, fm_receipt_seq = sale.FmReceiptSeq, fiscal_sign = sale.FiscalSign });
            var r = await rig.Service.RegisterAsync(FiscalModule.ParseReceipt(new BodyReader(body), true), body, true, CancellationToken.None);
            r.FmReceiptSeq.ShouldBe(2);
            Should.Throw<LocalApiException>(() => FiscalModule.ParseReceipt(new BodyReader(FiscalRig.SaleBody(3, kind: "return")), true)).Code.ShouldBe("VALIDATION_ERROR");
            Should.Throw<LocalApiException>(() => FiscalModule.ParseReceipt(new BodyReader(FiscalRig.SaleBody(3, kind: "sale")), true)).Code.ShouldBe("VALIDATION_ERROR");
        }

        [Fact]
        public void Card_number_instead_of_a_mask_is_rejected()
        {
            var e = Should.Throw<LocalApiException>(() => FiscalModule.ParseReceipt(new BodyReader(FiscalRig.SaleBody(1, mask: "8600123412345678")), false));
            e.Code.ShouldBe("VALIDATION_ERROR");
            FiscalModule.ParseReceipt(new BodyReader(FiscalRig.SaleBody(1, mask: "8600********5678")), false).Payments.CardMask.ShouldBe("8600********5678");
        }

        [Fact]
        public void Money_must_be_integer_tiyin_and_payments_must_sum()
        {
            var good = FiscalRig.SaleBody(1);
            var text = good.GetRawText().Replace("\"cash_tiyin\":1200000", "\"cash_tiyin\":1199999");
            using var d = JsonDocument.Parse(text);
            Should.Throw<LocalApiException>(() => FiscalModule.ParseReceipt(new BodyReader(d.RootElement), false)).Parameters!["reason"].ShouldBe("sum_mismatch");
            using var d2 = JsonDocument.Parse(good.GetRawText().Replace("\"price_tiyin\":600000", "\"price_tiyin\":6000.5"));
            Should.Throw<LocalApiException>(() => FiscalModule.ParseReceipt(new BodyReader(d2.RootElement), false)).Parameters!["field"].ShouldBe("price_tiyin");
        }

        [Fact]
        public async Task Sale_without_an_open_shift_is_shift_not_open()
        {
            using var rig = new FiscalRig();
            (await Should.ThrowAsync<LocalApiException>(() => rig.Sale(1))).Code.ShouldBe("SHIFT_NOT_OPEN");
        }

        [Fact]
        public async Task Open_shift_is_idempotent_and_a_second_shift_is_already_open()
        {
            using var rig = new FiscalRig();
            var a = await rig.Service.OpenShiftAsync(FiscalRig.Ref, 5, "K", CancellationToken.None);
            var b = await rig.Service.OpenShiftAsync(FiscalRig.Ref, 5, "K", CancellationToken.None);
            b.OpenedAt.ShouldBe(a.OpenedAt);
            (await Should.ThrowAsync<LocalApiException>(() => rig.Service.OpenShiftAsync(FiscalRig.Ref, 6, "K", CancellationToken.None))).Code.ShouldBe("SHIFT_ALREADY_OPEN");
        }

        [Fact]
        public async Task Close_shift_returns_z_totals_in_tiyin_and_repeats_idempotently()
        {
            using var rig = new FiscalRig();
            await rig.Service.OpenShiftAsync(FiscalRig.Ref, 1, "K", CancellationToken.None);
            await rig.Sale(1, 10_000_00);
            await rig.Sale(2, 5_000_00);
            var z = await rig.Service.CloseShiftAsync(FiscalRig.Ref, 1, CancellationToken.None);
            z.ZNumber.ShouldBe(1);
            z.Totals.Sale.ShouldBe(15_000_00);
            z.Totals.ByPaymentForm["cash"].ShouldBe(15_000_00);
            (await rig.Service.CloseShiftAsync(FiscalRig.Ref, 1, CancellationToken.None)).ZNumber.ShouldBe(1);
        }

        [Fact]
        public async Task Offline_receipts_accumulate_as_unsent_and_resend_acks_them()
        {
            using var rig = new FiscalRig();
            rig.Bridge.OfdOnline = false;
            await rig.Service.OpenShiftAsync(FiscalRig.Ref, 1, "K", CancellationToken.None);
            await rig.Sale(1);
            await rig.Sale(2);
            var st = await rig.Service.DeviceStatusAsync("fm1", CancellationToken.None);
            st.PendingCount.ShouldBe(2);
            st.OldestUnackedAt.ShouldBe("2026-10-18T09:00:00Z");
            (await rig.Service.UnsentAsync("fm1", CancellationToken.None)).Count.ShouldBe(2);
            var failed = await rig.Service.ResendAsync("fm1", CancellationToken.None);
            failed.Failed.ShouldBe(2);
            rig.Bridge.OfdOnline = true;
            var ok = await rig.Service.ResendAsync("fm1", CancellationToken.None);
            ok.Sent.ShouldBe(2);
            ok.Acked.Count.ShouldBe(2);
            (await rig.Service.UnsentAsync("fm1", CancellationToken.None)).ShouldBeEmpty();
        }

        [Fact]
        public async Task Oldest_unacked_receipt_48h_blocks_new_receipts()
        {
            using var rig = new FiscalRig();
            rig.Bridge.OfdOnline = false;
            await rig.Service.OpenShiftAsync(FiscalRig.Ref, 1, "K", CancellationToken.None);
            await rig.Sale(1);
            rig.Clock.Advance(TimeSpan.FromHours(47.9));
            await rig.Sale(2);
            rig.Clock.Advance(TimeSpan.FromHours(0.2));
            var e = await Should.ThrowAsync<LocalApiException>(() => rig.Sale(3));
            e.Code.ShouldBe("FISCAL_OFFLINE_48H_BLOCKED");
            e.Status.ShouldBe(409);
            rig.Bridge.OfdOnline = true;
            await rig.Service.ResendAsync("fm1", CancellationToken.None);
            (await rig.Sale(3)).FmReceiptSeq.ShouldBe(3);
        }

        [Fact]
        public async Task Locked_fm_is_fiscal_device_locked()
        {
            using var rig = new FiscalRig();
            await rig.Service.OpenShiftAsync(FiscalRig.Ref, 1, "K", CancellationToken.None);
            rig.Bridge.ForcedFmState = "locked";
            (await Should.ThrowAsync<LocalApiException>(() => rig.Sale(1))).Code.ShouldBe("FISCAL_DEVICE_LOCKED");
        }

        [Fact]
        public async Task Unknown_device_is_not_found_and_unavailable_partner_bridge_is_not_announced()
        {
            using var rig = new FiscalRig();
            rig.Cfg.List.Add(new FiscalDeviceConfig { LocalId = "mk", Provider = "multikassa_local" });
            rig.Service.Active().Select(a => a.Device.LocalId).ShouldBe(new[] { "fm1" });
            (await Should.ThrowAsync<LocalApiException>(() => rig.Service.DeviceStatusAsync("mk", CancellationToken.None))).Code.ShouldBe("NOT_FOUND");
            rig.Cfg.AllowFakeBridge = false;
            JsonSerializer.Serialize(rig.Module.Describe()).ShouldContain("\"enabled\":false");
        }
    }

    public class FiscalTaskTests
    {
        private static JsonElement J(object o) => AgentJson.ToElement(o);

        private static TaskContext Ctx(string kind) => new TaskContext(Guid.NewGuid().ToString(), kind, 1, Guid.NewGuid().ToString());

        [Fact]
        public async Task Fiscal_status_reports_state_and_new_acks_once()
        {
            using var rig = new FiscalRig();
            await rig.Service.OpenShiftAsync(FiscalRig.Ref, 1, "K", CancellationToken.None);
            await rig.Sale(1);
            var payload = J(new { cash_register_id = FiscalRig.Register, local_id = "fm1" });
            rig.Module.ValidatePayload("fiscal.status", payload).ShouldBeNull();
            var r = await rig.Module.ExecuteAsync(Ctx("fiscal.status"), payload, CancellationToken.None);
            r.Outcome.ShouldBe("done");
            r.Data.GetProperty("cash_register_id").GetString().ShouldBe(FiscalRig.Register);
            r.Data.GetProperty("fm_state").GetString().ShouldBe("ok");
            r.Data.GetProperty("pending_count").GetInt32().ShouldBe(0);
            r.Data.GetProperty("acked").GetArrayLength().ShouldBe(1);
            var again = await rig.Module.ExecuteAsync(Ctx("fiscal.status"), payload, CancellationToken.None);
            again.Data.GetProperty("acked").GetArrayLength().ShouldBe(0);
        }

        [Fact]
        public async Task Fiscal_status_without_local_id_uses_the_mapping_learned_from_the_pos()
        {
            using var rig = new FiscalRig();
            await rig.Service.OpenShiftAsync(FiscalRig.Ref, 1, "K", CancellationToken.None);
            var r = await rig.Module.ExecuteAsync(Ctx("fiscal.status"), J(new { cash_register_id = FiscalRig.Register }), CancellationToken.None);
            r.Outcome.ShouldBe("done");
            var unknown = await rig.Module.ExecuteAsync(Ctx("fiscal.status"), J(new { cash_register_id = Guid.NewGuid().ToString() }), CancellationToken.None);
            unknown.Outcome.ShouldBe("failed");
            unknown.Error!.Field.ShouldBe("payload.local_id");
        }

        [Fact]
        public async Task Resend_unsent_task_result_shape()
        {
            using var rig = new FiscalRig();
            rig.Bridge.OfdOnline = false;
            await rig.Service.OpenShiftAsync(FiscalRig.Ref, 1, "K", CancellationToken.None);
            await rig.Sale(1);
            rig.Bridge.OfdOnline = true;
            var r = await rig.Module.ExecuteAsync(Ctx("fiscal.resend_unsent"), J(new { cash_register_id = FiscalRig.Register, local_id = "fm1" }), CancellationToken.None);
            r.Data.GetProperty("sent").GetInt32().ShouldBe(1);
            r.Data.GetProperty("failed").GetInt32().ShouldBe(0);
            r.Data.GetProperty("acked")[0].GetProperty("fm_receipt_seq").GetInt64().ShouldBe(1);
        }

        [Fact]
        public async Task Zreport_task_closes_the_shift_the_pos_left_open()
        {
            using var rig = new FiscalRig();
            await rig.Service.OpenShiftAsync(FiscalRig.Ref, 1, "K", CancellationToken.None);
            await rig.Sale(1, 7_000_00);
            var shift = Guid.NewGuid().ToString();
            var payload = J(new { cash_register_id = FiscalRig.Register, local_id = "fm1", shift_id = shift });
            rig.Module.ValidatePayload("fiscal.zreport", payload).ShouldBeNull();
            var r = await rig.Module.ExecuteAsync(Ctx("fiscal.zreport"), payload, CancellationToken.None);
            r.Outcome.ShouldBe("done");
            r.Data.GetProperty("z_number").GetInt64().ShouldBe(1);
            r.Data.GetProperty("totals").GetProperty("sale").GetInt64().ShouldBe(7_000_00);
            r.Data.GetProperty("shift_id").GetString().ShouldBe(shift);
        }

        [Fact]
        public void Task_payloads_are_strict()
        {
            using var rig = new FiscalRig();
            rig.Module.ValidatePayload("fiscal.status", J(new { cash_register_id = FiscalRig.Register, extra = 1 })).ShouldBe("payload.extra");
            rig.Module.ValidatePayload("fiscal.zreport", J(new { cash_register_id = FiscalRig.Register })).ShouldBe("payload.shift_id");
        }
    }

    /// <summary>
    /// FiscalBridge contract suite (26 #109): one scenario run against the Fake now and against a real partner bridge
    /// once one exists (<c>ERP_FISCAL_BRIDGE_CONTRACT=&lt;provider&gt;</c>; without it that run is skipped).
    /// </summary>
    public sealed class FiscalBridgeContractTests
    {
        private static FiscalReceiptPayload Receipt(long seq, long amount) => FiscalModule.ParseReceipt(new BodyReader(FiscalRig.SaleBody(seq, amount)), false);

        internal static async Task RunContract(IFiscalBridge b)
        {
            var d = new FiscalDeviceConfig { LocalId = "fm1", Provider = b.Provider };
            await b.OpenShiftAsync(d, 1, "K", CancellationToken.None);
            var sale = await b.RegisterSaleAsync(d, Receipt(1, 5_000_00), CancellationToken.None);
            sale.FiscalSign.ShouldNotBeNullOrEmpty();
            sale.QrUrl.ShouldStartWith("https://ofd.soliq.uz/check?");
            (await b.FindReceiptAsync(d, FiscalRig.Register, 1, CancellationToken.None))!.FmReceiptSeq.ShouldBe(sale.FmReceiptSeq);
            (await b.FindReceiptAsync(d, FiscalRig.Register, 99, CancellationToken.None)).ShouldBeNull();
            var z = await b.CloseShiftAsync(d, 1, CancellationToken.None);
            z.Totals.Sale.ShouldBe(5_000_00);
            (await b.GetDeviceStatusAsync(d, CancellationToken.None)).FmState.ShouldBe("ok");
        }

        [Fact]
        public async Task Contract_fiscal_bridge_fake()
        {
            using var dir = new TempDir();
            await RunContract(new FakeFiscalBridge(new FakeClock(new DateTimeOffset(2026, 10, 18, 9, 0, 0, TimeSpan.Zero)), dir.File("fm.json")));
        }

        [RealBridgeFact]
        public async Task Contract_fiscal_bridge_partner()
        {
            // ⛔ 26 #109: no partner local-service protocol yet — this run fails until a real bridge replaces the placeholder.
            await RunContract(new UnavailableFiscalBridge(Environment.GetEnvironmentVariable("ERP_FISCAL_BRIDGE_CONTRACT")!));
        }
    }

    public sealed class RealBridgeFactAttribute : FactAttribute
    {
        public RealBridgeFactAttribute()
        {
            if (string.IsNullOrEmpty(Environment.GetEnvironmentVariable("ERP_FISCAL_BRIDGE_CONTRACT"))) Skip = "real fiscal partner bridge not available (26 #109)";
        }
    }
}

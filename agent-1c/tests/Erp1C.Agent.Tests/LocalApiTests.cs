using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Agent.LocalApi;
using Erp1C.CardTerminal;
using Erp1C.CardTerminal.Drivers.Fake;
using Erp1C.Core.Hosting;
using Erp1C.Core.Json;
using Erp1C.Devices;
using Erp1C.Fiscal;
using Erp1C.Tests.Common;
using Shouldly;
using Xunit;

namespace Erp1C.Agent.Tests
{
    internal sealed class OneTerminal : ICardTerminalConfig
    {
        public IReadOnlyList<TerminalConfig> Terminals => new[] { new TerminalConfig { LocalId = "t1", Driver = "fake", Host = "192.168.1.60", Port = 27015 } };

        public bool AllowFakeDriver => true;
    }

    internal sealed class NoPrinters : IPrinterConfig
    {
        public IReadOnlyList<PrinterConfig> Printers => Array.Empty<PrinterConfig>();
    }

    /// <summary>The real local API server on 127.0.0.1 (ephemeral port) with the real modules over fakes.</summary>
    internal sealed class LocalApiRig : IDisposable
    {
        public const string Origin = "https://app.erp.test";

        public LocalApiRig()
        {
            Dir = new TempDir();
            Clock = new FakeClock(new DateTimeOffset(2026, 10, 18, 9, 0, 0, TimeSpan.Zero));
            Pairing = new LocalPairing(Dir.File("local-pairs.json"), new XorProtector(), Clock);
            var lanes = new DeviceLanes();
            Fiscal = new FiscalModule(new FiscalService(new FiscalCfg(), new IFiscalBridge[] { new FakeFiscalBridge(Clock) }, Dir.File("fj.jsonl"), lanes, Clock));
            Cards = new CardTerminalService(new OneTerminal(), new DriverRegistry(new ICardTerminalDriver[] { new FakeCardTerminalDriver() }), new CardJournal(Dir.File("cj.jsonl"), Clock), lanes, Clock, null, new CardTimeouts { SafeRetryDelay = TimeSpan.Zero });
            var printers = new PrinterService(new NoPrinters(), new TcpRawPrinterTransport(), lanes);
            Server = new LocalApiServer(0, new OriginPolicy(new[] { Origin }), Pairing, new ILocalApiModule[]
            {
                new AgentLocalModule(Pairing, Fiscal, printers, Cards),
                Fiscal,
                new PrinterModule(printers),
                new CardLocalApi(Cards),
            });
            Server.Start();
            Http = new HttpClient { BaseAddress = new Uri("http://127.0.0.1:" + Server.Port) };
        }

        public TempDir Dir { get; }

        public FakeClock Clock { get; }

        public LocalPairing Pairing { get; }

        public FiscalModule Fiscal { get; }

        public CardTerminalService Cards { get; }

        public LocalApiServer Server { get; }

        public HttpClient Http { get; }

        public async Task<(HttpStatusCode Status, JsonElement Body, HttpResponseMessage Resp)> Send(HttpMethod m, string path, object? body = null, string? origin = Origin, string? token = null, string? deviceId = null, Action<HttpRequestMessage>? extra = null)
        {
            using var req = new HttpRequestMessage(m, path);
            if (origin != null) req.Headers.TryAddWithoutValidation("Origin", origin);
            if (token != null) req.Headers.TryAddWithoutValidation("Authorization", "Bearer " + token);
            if (deviceId != null) req.Headers.TryAddWithoutValidation("X-Device-Id", deviceId);
            if (body != null) req.Content = new StringContent(AgentJson.Serialize(body), Encoding.UTF8, "application/json");
            extra?.Invoke(req);
            var resp = await Http.SendAsync(req);
            var text = await resp.Content.ReadAsStringAsync();
            JsonElement json = default;
            if (!string.IsNullOrEmpty(text))
            {
                using var d = JsonDocument.Parse(text);
                json = d.RootElement.Clone();
            }

            return (resp.StatusCode, json, resp);
        }

        public async Task<(string Device, string Token)> PairAsync()
        {
            var (code, _) = Pairing.NewCode();
            var device = Guid.NewGuid().ToString();
            var (status, body, _) = await Send(HttpMethod.Post, "/v1/pair", new { code, device_id = device });
            status.ShouldBe(HttpStatusCode.OK);
            body.GetProperty("expires_at").ValueKind.ShouldBe(JsonValueKind.Null);
            return (device, body.GetProperty("local_token").GetString()!);
        }

        public void Dispose()
        {
            Http.Dispose();
            Server.Dispose();
            Dir.Dispose();
        }
    }

    public class LocalApiSecurityTests
    {
        [Fact]
        public void Listener_is_bound_to_loopback_only()
        {
            using var rig = new LocalApiRig();
            rig.Server.LocalEndpoint!.Address.ShouldBe(IPAddress.Loopback);
        }

        [Fact]
        public async Task Not_reachable_on_a_lan_address()
        {
            using var rig = new LocalApiRig();
            var lan = NetworkInterface.GetAllNetworkInterfaces()
                .Where(n => n.OperationalStatus == OperationalStatus.Up)
                .SelectMany(n => n.GetIPProperties().UnicastAddresses)
                .Select(a => a.Address)
                .FirstOrDefault(a => a.AddressFamily == AddressFamily.InterNetwork && !IPAddress.IsLoopback(a));
            if (lan is null) return; // no LAN interface on this machine
            using var c = new TcpClient();
            await Should.ThrowAsync<SocketException>(() => c.ConnectAsync(lan, rig.Server.Port));
        }

        [Fact]
        public async Task Missing_origin_is_403()
        {
            using var rig = new LocalApiRig();
            var (status, body, resp) = await rig.Send(HttpMethod.Get, "/v1/status", origin: null);
            status.ShouldBe(HttpStatusCode.Forbidden);
            body.GetProperty("code").GetString().ShouldBe("PERMISSION_DENIED");
            resp.Headers.Contains("Access-Control-Allow-Origin").ShouldBeFalse();
        }

        [Theory]
        [InlineData("https://evil.example")]
        [InlineData("http://app.erp.test")]
        [InlineData("null")]
        public async Task Foreign_origin_is_403_without_cors_headers(string origin)
        {
            using var rig = new LocalApiRig();
            var (status, _, resp) = await rig.Send(HttpMethod.Get, "/v1/status", origin: origin);
            status.ShouldBe(HttpStatusCode.Forbidden);
            resp.Headers.Contains("Access-Control-Allow-Origin").ShouldBeFalse();
        }

        [Fact]
        public async Task Foreign_host_header_is_403_dns_rebinding_guard()
        {
            using var rig = new LocalApiRig();
            var (status, _, _) = await rig.Send(HttpMethod.Get, "/v1/status", extra: r => r.Headers.Host = "evil.example:" + rig.Server.Port);
            status.ShouldBe(HttpStatusCode.Forbidden);
        }

        [Fact]
        public async Task Preflight_answers_cors_and_private_network_access_for_the_allowed_origin_only()
        {
            using var rig = new LocalApiRig();
            var (status, _, resp) = await rig.Send(HttpMethod.Options, "/v1/card/purchase", extra: r =>
            {
                r.Headers.TryAddWithoutValidation("Access-Control-Request-Method", "POST");
                r.Headers.TryAddWithoutValidation("Access-Control-Request-Private-Network", "true");
            });
            status.ShouldBe(HttpStatusCode.NoContent);
            resp.Headers.GetValues("Access-Control-Allow-Origin").Single().ShouldBe(LocalApiRig.Origin);
            resp.Headers.GetValues("Access-Control-Allow-Private-Network").Single().ShouldBe("true");
            resp.Headers.GetValues("Access-Control-Allow-Headers").Single().ShouldContain("X-Device-Id");

            var (bad, _, badResp) = await rig.Send(HttpMethod.Options, "/v1/card/purchase", origin: "https://evil.example", extra: r => r.Headers.TryAddWithoutValidation("Access-Control-Request-Private-Network", "true"));
            bad.ShouldBe(HttpStatusCode.Forbidden);
            badResp.Headers.Contains("Access-Control-Allow-Private-Network").ShouldBeFalse();
        }

        [Fact]
        public async Task No_token_is_401()
        {
            using var rig = new LocalApiRig();
            var (status, body, resp) = await rig.Send(HttpMethod.Get, "/v1/status");
            status.ShouldBe(HttpStatusCode.Unauthorized);
            body.GetProperty("code").GetString().ShouldBe("UNAUTHORIZED");
            body.GetProperty("message_key").GetString().ShouldBe("errors.unauthorized");
            resp.Headers.GetValues("Access-Control-Allow-Origin").Single().ShouldBe(LocalApiRig.Origin);
        }

        [Fact]
        public async Task Token_works_only_with_its_own_device_id()
        {
            using var rig = new LocalApiRig();
            var (device, token) = await rig.PairAsync();
            (await rig.Send(HttpMethod.Get, "/v1/status", token: token, deviceId: device)).Status.ShouldBe(HttpStatusCode.OK);
            (await rig.Send(HttpMethod.Get, "/v1/status", token: token, deviceId: Guid.NewGuid().ToString())).Status.ShouldBe(HttpStatusCode.Unauthorized);
            (await rig.Send(HttpMethod.Get, "/v1/status", token: token)).Status.ShouldBe(HttpStatusCode.Unauthorized);
            (await rig.Send(HttpMethod.Get, "/v1/status", token: token + "x", deviceId: device)).Status.ShouldBe(HttpStatusCode.Unauthorized);
        }

        [Fact]
        public async Task Revoked_pos_loses_access()
        {
            using var rig = new LocalApiRig();
            var (device, token) = await rig.PairAsync();
            rig.Pairing.Revoke(device);
            (await rig.Send(HttpMethod.Get, "/v1/status", token: token, deviceId: device)).Status.ShouldBe(HttpStatusCode.Unauthorized);
        }

        [Fact]
        public async Task Pairing_code_is_single_use()
        {
            using var rig = new LocalApiRig();
            var (code, _) = rig.Pairing.NewCode();
            (await rig.Send(HttpMethod.Post, "/v1/pair", new { code, device_id = Guid.NewGuid().ToString() })).Status.ShouldBe(HttpStatusCode.OK);
            var (status, body, _) = await rig.Send(HttpMethod.Post, "/v1/pair", new { code, device_id = Guid.NewGuid().ToString() });
            status.ShouldBe(HttpStatusCode.BadRequest);
            body.GetProperty("code").GetString().ShouldBe("OTP_EXPIRED");
        }

        [Fact]
        public async Task Pairing_code_expires_after_5_minutes()
        {
            using var rig = new LocalApiRig();
            var (code, exp) = rig.Pairing.NewCode();
            exp.ShouldBe(rig.Clock.UtcNow.AddMinutes(5));
            rig.Clock.Advance(TimeSpan.FromMinutes(5));
            var (status, body, _) = await rig.Send(HttpMethod.Post, "/v1/pair", new { code, device_id = Guid.NewGuid().ToString() });
            status.ShouldBe(HttpStatusCode.BadRequest);
            body.GetProperty("code").GetString().ShouldBe("OTP_EXPIRED");
        }

        [Fact]
        public async Task Five_wrong_codes_burn_the_code()
        {
            using var rig = new LocalApiRig();
            var (code, _) = rig.Pairing.NewCode();
            var wrong = code == "000000" ? "111111" : "000000";
            for (var i = 0; i < 4; i++)
            {
                var (s, b, _) = await rig.Send(HttpMethod.Post, "/v1/pair", new { code = wrong, device_id = Guid.NewGuid().ToString() });
                s.ShouldBe(HttpStatusCode.BadRequest);
                b.GetProperty("code").GetString().ShouldBe("OTP_INVALID");
            }

            var (last, lb, _) = await rig.Send(HttpMethod.Post, "/v1/pair", new { code = wrong, device_id = Guid.NewGuid().ToString() });
            last.ShouldBe((HttpStatusCode)429);
            lb.GetProperty("code").GetString().ShouldBe("OTP_MAX_ATTEMPTS");
            (await rig.Send(HttpMethod.Post, "/v1/pair", new { code, device_id = Guid.NewGuid().ToString() })).Status.ShouldBe(HttpStatusCode.BadRequest);
        }

        [Fact]
        public async Task Pairs_survive_a_restart_and_the_file_holds_no_plain_token()
        {
            using var rig = new LocalApiRig();
            var (device, token) = await rig.PairAsync();
            System.IO.File.ReadAllText(rig.Dir.File("local-pairs.json")).ShouldNotContain(token);
            var reloaded = new LocalPairing(rig.Dir.File("local-pairs.json"), new XorProtector(), rig.Clock);
            reloaded.Validate(token, device).ShouldBeTrue();
        }

        [Fact]
        public async Task Unknown_route_is_404_and_bad_json_is_422()
        {
            using var rig = new LocalApiRig();
            var (device, token) = await rig.PairAsync();
            (await rig.Send(HttpMethod.Get, "/v1/nope", token: token, deviceId: device)).Status.ShouldBe(HttpStatusCode.NotFound);
            var (status, body, _) = await rig.Send(HttpMethod.Post, "/v1/card/purchase", token: token, deviceId: device, extra: r => r.Content = new StringContent("{oops", Encoding.UTF8, "application/json"));
            status.ShouldBe((HttpStatusCode)422);
            body.GetProperty("code").GetString().ShouldBe("VALIDATION_ERROR");
        }
    }

    /// <summary>B5-DoD-02 agent part: card purchase / void / settlement through the agent local API with the driver emulator.</summary>
    public class LocalApiCardFlowTests
    {
        [Fact]
        public async Task Purchase_void_settlement_through_the_local_api()
        {
            using var rig = new LocalApiRig();
            var (device, token) = await rig.PairAsync();
            var attempt = Guid.NewGuid().ToString();
            var (ps, pb, _) = await rig.Send(HttpMethod.Post, "/v1/card/purchase", new { attempt_id = attempt, local_id = "t1", amount_tiyin = 12_000_00, currency = "UZS", cash_register_id = Guid.NewGuid().ToString(), client_event_id = Guid.NewGuid().ToString(), receipt_seq = 15 }, token: token, deviceId: device);
            ps.ShouldBe(HttpStatusCode.OK);
            pb.GetProperty("status").GetString().ShouldBe("approved");
            pb.GetProperty("card_mask").GetString().ShouldBe("8600********1234");
            pb.GetProperty("amount_tiyin").GetInt64().ShouldBe(12_000_00);

            var (ts, tb, _) = await rig.Send(HttpMethod.Get, "/v1/card/tx/" + attempt, token: token, deviceId: device);
            ts.ShouldBe(HttpStatusCode.OK);
            tb.GetProperty("rrn").GetString().ShouldBe(pb.GetProperty("rrn").GetString());

            var (vs, vb, _) = await rig.Send(HttpMethod.Post, "/v1/card/void", new { attempt_id = Guid.NewGuid().ToString(), local_id = "t1", amount_tiyin = 12_000_00, original_attempt_id = attempt }, token: token, deviceId: device);
            vs.ShouldBe(HttpStatusCode.OK);
            vb.GetProperty("kind").GetString().ShouldBe("void");

            var second = Guid.NewGuid().ToString();
            await rig.Send(HttpMethod.Post, "/v1/card/purchase", new { attempt_id = second, local_id = "t1", amount_tiyin = 5_000_00, currency = "UZS" }, token: token, deviceId: device);
            var (ss, sb, _) = await rig.Send(HttpMethod.Post, "/v1/card/settlement", new { local_id = "t1" }, token: token, deviceId: device);
            ss.ShouldBe(HttpStatusCode.OK);
            sb.GetProperty("count").GetInt32().ShouldBe(1); // the voided purchase left the batch
            sb.GetProperty("total_tiyin").GetInt64().ShouldBe(5_000_00);
            sb.GetProperty("batch_no").GetString().ShouldNotBeNullOrEmpty();
        }

        [Fact]
        public async Task Status_reports_capabilities_fm_state_and_terminals()
        {
            using var rig = new LocalApiRig();
            var (device, token) = await rig.PairAsync();
            var (s, b, _) = await rig.Send(HttpMethod.Get, "/v1/status", token: token, deviceId: device);
            s.ShouldBe(HttpStatusCode.OK);
            b.GetProperty("agent_version").GetString()!.ShouldMatch("^[0-9]+\\.[0-9]+\\.[0-9]+$");
            b.GetProperty("capabilities").GetProperty("fiscal").GetProperty("enabled").GetBoolean().ShouldBeTrue();
            b.GetProperty("capabilities").GetProperty("fiscal").GetProperty("provider").GetString().ShouldBe("fake");
            b.GetProperty("capabilities").GetProperty("print").GetProperty("enabled").GetBoolean().ShouldBeFalse();
            b.GetProperty("capabilities").GetProperty("card_terminal").GetProperty("enabled").GetBoolean().ShouldBeTrue();
            b.GetProperty("fiscal_devices")[0].GetProperty("fm_state").GetString().ShouldBe("ok");
            b.GetProperty("card_terminals")[0].GetProperty("local_id").GetString().ShouldBe("t1");
        }

        [Fact]
        public async Task Card_error_codes_map_to_21_16_1_http_statuses()
        {
            using var rig = new LocalApiRig();
            var (device, token) = await rig.PairAsync();
            async Task<(HttpStatusCode, JsonElement)> Buy(long amount)
            {
                var (s, b, _) = await rig.Send(HttpMethod.Post, "/v1/card/purchase", new { attempt_id = Guid.NewGuid().ToString(), local_id = "t1", amount_tiyin = amount, currency = "UZS" }, token: token, deviceId: device);
                return (s, b);
            }

            var (busy, bb) = await Buy(10_004_00);
            busy.ShouldBe(HttpStatusCode.Conflict);
            bb.GetProperty("code").GetString().ShouldBe("CARD_TERMINAL_BUSY");
            var (timeout, tb) = await Buy(10_002_00);
            timeout.ShouldBe(HttpStatusCode.GatewayTimeout);
            tb.GetProperty("code").GetString().ShouldBe("CARD_TERMINAL_TIMEOUT");
            var (mismatch, mb) = await Buy(10_005_00);
            mismatch.ShouldBe((HttpStatusCode)422);
            mb.GetProperty("code").GetString().ShouldBe("CARD_AMOUNT_MISMATCH");
            mb.GetProperty("params").GetProperty("void_status").GetString().ShouldBe("voided");
            var (declined, db) = await Buy(10_001_00);
            declined.ShouldBe(HttpStatusCode.OK);
            db.GetProperty("status").GetString().ShouldBe("declined");
            var (unknownTerminal, _, _) = await rig.Send(HttpMethod.Post, "/v1/card/purchase", new { attempt_id = Guid.NewGuid().ToString(), local_id = "nope", amount_tiyin = 100 }, token: token, deviceId: device);
            unknownTerminal.ShouldBe(HttpStatusCode.NotFound);
            var (str, _, _) = await rig.Send(HttpMethod.Post, "/v1/card/purchase", new { attempt_id = Guid.NewGuid().ToString(), local_id = "t1", amount_tiyin = "100.00" }, token: token, deviceId: device);
            str.ShouldBe((HttpStatusCode)422);
        }

        [Fact]
        public async Task Offline_card_payment_needs_no_server()
        {
            // The agent's card path never calls the ERP server: there is no HTTP client in this rig at all.
            using var rig = new LocalApiRig();
            var (device, token) = await rig.PairAsync();
            var (s, b, _) = await rig.Send(HttpMethod.Post, "/v1/card/purchase", new { attempt_id = Guid.NewGuid().ToString(), local_id = "t1", amount_tiyin = 3_000_00, currency = "UZS" }, token: token, deviceId: device);
            s.ShouldBe(HttpStatusCode.OK);
            b.GetProperty("status").GetString().ShouldBe("approved");
        }

        [Fact]
        public async Task Fiscal_sale_through_the_local_api()
        {
            using var rig = new LocalApiRig();
            var (device, token) = await rig.PairAsync();
            var reg = new { cash_register_id = Guid.NewGuid().ToString(), local_id = "fm1" };
            (await rig.Send(HttpMethod.Post, "/v1/fiscal/open-shift", new { cash_register = reg, shift_no = 1, cashier_name = "Kassir" }, token: token, deviceId: device)).Status.ShouldBe(HttpStatusCode.OK);
            var sale = new
            {
                cash_register = reg,
                receipt_seq = 1,
                kind = "sale",
                items = new[] { new { name = "Non", mxik = (string?)null, package_code = (string?)null, unit_code = (string?)null, qty_milli = 1000, price_tiyin = 5_000_00, amount_tiyin = 5_000_00, vat_rate = "12", vat_tiyin = 53_571, marking_codes = Array.Empty<string>() } },
                payments = new { payment_form = "cash", cash_tiyin = 5_000_00, card_tiyin = 0, qr_tiyin = 0, card_type = (string?)null, card_mask = (string?)null, rrn = (string?)null },
            };
            var (s, b, _) = await rig.Send(HttpMethod.Post, "/v1/fiscal/sale", sale, token: token, deviceId: device);
            s.ShouldBe(HttpStatusCode.OK);
            b.GetProperty("fm_terminal_id").GetString()!.ShouldMatch("^ZZ[0-9]{12}$");
            b.GetProperty("fm_receipt_seq").GetInt64().ShouldBe(1);
            var (ds, db, _) = await rig.Send(HttpMethod.Get, "/v1/fiscal/device-status?local_id=fm1", token: token, deviceId: device);
            ds.ShouldBe(HttpStatusCode.OK);
            db.GetProperty("fm_state").GetString().ShouldBe("ok");
            var (closed, zb, _) = await rig.Send(HttpMethod.Post, "/v1/fiscal/close-shift", new { cash_register = reg, shift_no = 1 }, token: token, deviceId: device);
            closed.ShouldBe(HttpStatusCode.OK);
            zb.GetProperty("totals").GetProperty("sale").GetInt64().ShouldBe(5_000_00);
            var (again, ab, _) = await rig.Send(HttpMethod.Post, "/v1/fiscal/sale", sale, token: token, deviceId: device);
            again.ShouldBe(HttpStatusCode.OK); // idempotent replay from the journal even after the shift closed
            ab.GetProperty("fiscal_sign").GetString().ShouldBe(b.GetProperty("fiscal_sign").GetString());
        }
    }
}

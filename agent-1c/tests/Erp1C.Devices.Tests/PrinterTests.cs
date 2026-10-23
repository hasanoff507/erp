using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Core.Hosting;
using Erp1C.Core.Json;
using Shouldly;
using Xunit;

namespace Erp1C.Devices.Tests
{
    internal sealed class PrinterList : IPrinterConfig
    {
        public List<PrinterConfig> List { get; } = new List<PrinterConfig>();

        public IReadOnlyList<PrinterConfig> Printers => List;
    }

    /// <summary>A local TCP "printer" that records the bytes it received.</summary>
    internal sealed class LocalPrinter : IDisposable
    {
        private readonly TcpListener _l = new TcpListener(IPAddress.Loopback, 0);

        public LocalPrinter()
        {
            _l.Start();
            Received = Task.Run(async () =>
            {
                using var c = await _l.AcceptTcpClientAsync();
                using var ms = new MemoryStream();
                await c.GetStream().CopyToAsync(ms);
                return ms.ToArray();
            });
        }

        public int Port => ((IPEndPoint)_l.LocalEndpoint).Port;

        public Task<byte[]> Received { get; }

        public void Dispose() => _l.Stop();
    }

    public class TcpRawPrinterTests
    {
        [Fact]
        public async Task Raw_bytes_reach_a_tcp_listener_unchanged()
        {
            using var printer = new LocalPrinter();
            var data = new byte[] { 0x1B, 0x40, 0x1B, 0x74, 0x11, (byte)'O', (byte)'K', 0x0A, 0x1D, 0x56, 0x00 };
            await new TcpRawPrinterTransport().SendAsync(IPAddress.Loopback, printer.Port, data, CancellationToken.None);
            (await printer.Received).ShouldBe(data);
        }

        [Fact]
        public async Task Closed_port_is_printer_unreachable()
        {
            var l = new TcpListener(IPAddress.Loopback, 0);
            l.Start();
            var port = ((IPEndPoint)l.LocalEndpoint).Port;
            l.Stop();
            await Should.ThrowAsync<PrinterUnreachableException>(() => new TcpRawPrinterTransport { ConnectTimeout = TimeSpan.FromSeconds(2) }.SendAsync(IPAddress.Loopback, port, new byte[] { 1 }, CancellationToken.None));
        }
    }

    public class PrinterServiceTests
    {
        private static PrinterService Service(PrinterList cfg, int loopbackPort) =>
            new PrinterService(cfg, new TcpRawPrinterTransport(), new DeviceLanes(), null, p => true, p => IPAddress.Loopback);

        [Fact]
        public async Task Print_raw_local_api_sends_to_the_registered_printer()
        {
            using var printer = new LocalPrinter();
            var cfg = new PrinterList();
            cfg.List.Add(new PrinterConfig { LocalId = "192.168.1.50:9100", Host = "192.168.1.50", Port = printer.Port });
            var module = new PrinterModule(Service(cfg, printer.Port));
            var body = Encoding.UTF8.GetBytes(AgentJson.Serialize(new { printer_local_id = "192.168.1.50:9100", data_base64 = Convert.ToBase64String(Encoding.ASCII.GetBytes("HELLO\n")), encoding = "cp866" }));
            var route = Assert.Single(module.Routes);
            route.Pattern.ShouldBe("/v1/print/raw");
            var resp = await route.Handler(new LocalRequest("POST", "/v1/print/raw", new Dictionary<string, string>(), body, new Dictionary<string, string>(), "d"), CancellationToken.None);
            resp.Status.ShouldBe(200);
            Encoding.UTF8.GetString(resp.Body).ShouldBe("{\"status\":\"sent\"}");
            Encoding.ASCII.GetString(await printer.Received).ShouldBe("HELLO\n");
        }

        [Fact]
        public async Task Unregistered_printer_is_not_found_and_never_contacted()
        {
            var svc = Service(new PrinterList(), 1);
            var e = await Should.ThrowAsync<LocalApiException>(() => svc.PrintAsync("10.0.0.9:9100", Convert.ToBase64String(new byte[] { 1 }), "cp866", CancellationToken.None));
            e.Code.ShouldBe("NOT_FOUND");
        }

        [Theory]
        [InlineData("8.8.8.8", 9100)]
        [InlineData("127.0.0.1", 9100)]
        [InlineData("printer.local", 9100)]
        [InlineData("192.168.1.50", 80)]
        public void Only_private_lan_port_9100_printers_are_active(string host, int port)
        {
            var cfg = new PrinterList();
            cfg.List.Add(new PrinterConfig { LocalId = "p", Host = host, Port = port });
            var svc = new PrinterService(cfg, new TcpRawPrinterTransport(), new DeviceLanes());
            svc.Enabled.ShouldBeFalse();
            svc.Resolve("p").ShouldBeNull();
        }

        [Fact]
        public async Task Bad_input_is_validation_error()
        {
            var cfg = new PrinterList();
            cfg.List.Add(new PrinterConfig { LocalId = "p", Host = "192.168.1.50", Port = 9100 });
            var svc = new PrinterService(cfg, new TcpRawPrinterTransport(), new DeviceLanes());
            (await Should.ThrowAsync<LocalApiException>(() => svc.PrintAsync("p", "!!notbase64", "cp866", CancellationToken.None))).Code.ShouldBe("VALIDATION_ERROR");
            (await Should.ThrowAsync<LocalApiException>(() => svc.PrintAsync("p", "AQ==", "utf8", CancellationToken.None))).Code.ShouldBe("VALIDATION_ERROR");
        }

        [Fact]
        public async Task Print_raw_task_reports_sent_and_printer_unreachable()
        {
            using var printer = new LocalPrinter();
            var cfg = new PrinterList();
            cfg.List.Add(new PrinterConfig { LocalId = "p1", Host = "192.168.1.50", Port = printer.Port });
            var module = new PrinterModule(Service(cfg, printer.Port));
            var payload = AgentJson.ToElement(new { printer_local_id = "p1", data_base64 = "SEk=", encoding = "raster" });
            module.ValidatePayload("print.raw", payload).ShouldBeNull();
            var ok = await module.ExecuteAsync(new TaskContext("t", "print.raw", 1, "l"), payload, CancellationToken.None);
            ok.Outcome.ShouldBe("done");
            ok.Data.GetProperty("status").GetString().ShouldBe("sent");
            ok.Data.GetProperty("bytes").GetInt32().ShouldBe(2);
            (await printer.Received).ShouldBe(Encoding.ASCII.GetBytes("HI"));

            var dead = new TcpListener(IPAddress.Loopback, 0);
            dead.Start();
            var deadPort = ((IPEndPoint)dead.LocalEndpoint).Port;
            dead.Stop();
            cfg.List[0].Port = deadPort;
            var fail = await module.ExecuteAsync(new TaskContext("t2", "print.raw", 1, "l"), payload, CancellationToken.None);
            fail.Outcome.ShouldBe("failed");
            fail.Error!.Code.ShouldBe("PRINTER_UNREACHABLE");
            fail.Error.RetryableHint.ShouldBeFalse();
            JsonSerializer.Serialize(module.Describe()).ShouldContain("\"status\":\"offline\"");
        }

        [Fact]
        public void Print_raw_payload_is_strict()
        {
            var module = new PrinterModule(new PrinterService(new PrinterList(), new TcpRawPrinterTransport(), new DeviceLanes()));
            module.ValidatePayload("print.raw", AgentJson.ToElement(new { printer_local_id = "p", data_base64 = "AA==", encoding = "cp866", host = "8.8.8.8" })).ShouldBe("payload.host");
            module.ValidatePayload("print.raw", AgentJson.ToElement(new { printer_local_id = "p", data_base64 = "AA==", encoding = "pdf" })).ShouldBe("payload.encoding");
        }
    }
}

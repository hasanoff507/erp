using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Core.Contracts;
using Erp1C.Core.Errors;
using Erp1C.Core.Hosting;
using Erp1C.Core.Security;

namespace Erp1C.Devices
{
    /// <summary>A registered raw TCP 9100 (ESC/POS) LAN printer (agent settings, 34 §14.2).</summary>
    public sealed class PrinterConfig
    {
        /// <summary>Defaults to <c>host:port</c> — the POS sends <c>printer.lan_address</c> as <c>printer_local_id</c> (24 §6.1).</summary>
        public string LocalId { get; set; } = string.Empty;

        public string Name { get; set; } = string.Empty;

        public string Host { get; set; } = string.Empty;

        public int Port { get; set; } = 9100;

        public string Address => Host + ":" + Port.ToString(CultureInfo.InvariantCulture);
    }

    public interface IPrinterConfig
    {
        IReadOnlyList<PrinterConfig> Printers { get; }
    }

    /// <summary>Raw byte sink (TCP 9100). Throws <see cref="PrinterUnreachableException"/> on connect/write failure.</summary>
    public interface IRawPrinterTransport
    {
        Task SendAsync(IPAddress host, int port, byte[] data, CancellationToken ct);
    }

    public sealed class PrinterUnreachableException : Exception
    {
        public PrinterUnreachableException()
        {
        }

        public PrinterUnreachableException(string message)
            : base(message)
        {
        }

        public PrinterUnreachableException(string message, Exception inner)
            : base(message, inner)
        {
        }
    }

    /// <summary>TCP client: connect ≤ 5 s, write ≤ 15 s, graceful shutdown so the printer receives every byte.</summary>
    public sealed class TcpRawPrinterTransport : IRawPrinterTransport
    {
        public TimeSpan ConnectTimeout { get; set; } = TimeSpan.FromSeconds(5);

        public TimeSpan WriteTimeout { get; set; } = TimeSpan.FromSeconds(15);

        public async Task SendAsync(IPAddress host, int port, byte[] data, CancellationToken ct)
        {
            using var client = new TcpClient(AddressFamily.InterNetwork) { NoDelay = true };
            using (var cts = CancellationTokenSource.CreateLinkedTokenSource(ct))
            {
                cts.CancelAfter(ConnectTimeout);
                var connect = client.ConnectAsync(host, port);
                var done = await Task.WhenAny(connect, Task.Delay(Timeout.Infinite, cts.Token)).ConfigureAwait(false);
                if (done != connect || !client.Connected)
                {
                    ObserveFault(connect);
                    throw new PrinterUnreachableException("printer connect timeout");
                }

                try
                {
                    await connect.ConfigureAwait(false);
                }
                catch (SocketException e)
                {
                    throw new PrinterUnreachableException("printer connect failed: " + e.SocketErrorCode, e);
                }
            }

            try
            {
                var stream = client.GetStream();
                using var wcts = CancellationTokenSource.CreateLinkedTokenSource(ct);
                wcts.CancelAfter(WriteTimeout);
                await stream.WriteAsync(data, 0, data.Length, wcts.Token).ConfigureAwait(false);
                await stream.FlushAsync(wcts.Token).ConfigureAwait(false);
                client.Client.Shutdown(SocketShutdown.Send);
            }
            catch (Exception e) when (e is SocketException || e is System.IO.IOException || e is OperationCanceledException || e is ObjectDisposedException)
            {
                throw new PrinterUnreachableException("printer write failed", e);
            }
        }

        private static void ObserveFault(Task t) => t.ContinueWith(x => _ = x.Exception, TaskScheduler.Default);
    }

    /// <summary>
    /// <c>print.raw</c> / <c>POST /v1/print/raw</c> (21 §16, §16.1, 34 §14.3): bytes go only to a REGISTERED printer
    /// on a private LAN address and port 9100 — never to an arbitrary host. One FIFO lane per printer.
    /// </summary>
    public sealed class PrinterService
    {
        public const int MaxBytes = 4 * 1024 * 1024;
        private readonly IPrinterConfig _config;
        private readonly IRawPrinterTransport _transport;
        private readonly DeviceLanes _lanes;
        private readonly IAgentLogger _log;
        private readonly Func<PrinterConfig, bool> _allowed;
        private readonly Func<PrinterConfig, IPAddress> _address;
        private readonly ConcurrentDictionary<string, string> _status = new ConcurrentDictionary<string, string>(StringComparer.Ordinal);

        public PrinterService(IPrinterConfig config, IRawPrinterTransport transport, DeviceLanes lanes, IAgentLogger? log = null, Func<PrinterConfig, bool>? allowed = null, Func<PrinterConfig, IPAddress>? address = null)
        {
            _config = config;
            _transport = transport;
            _lanes = lanes;
            _log = log ?? NullAgentLogger.Instance;
            _allowed = allowed ?? IsAllowedPrinter;
            _address = address ?? (p => PrivateLan.ParsePrivate(p.Host));
        }

        /// <summary>Private LAN IPv4 and port 9100 only (34 §14.3).</summary>
        public static bool IsAllowedPrinter(PrinterConfig p) => PrivateLan.IsPrivateIPv4(p.Host) && p.Port == 9100;

        public IReadOnlyList<PrinterConfig> Active() => _config.Printers.Where(p => _allowed(p)).ToList();

        public bool Enabled => Active().Count > 0;

        public PrinterConfig? Resolve(string printerLocalId) =>
            Active().FirstOrDefault(p => string.Equals(p.LocalId, printerLocalId, StringComparison.Ordinal))
            ?? Active().FirstOrDefault(p => string.Equals(p.Address, printerLocalId, StringComparison.Ordinal));

        public string StatusOf(string localId) => _status.TryGetValue(localId, out var s) ? s : "ok";

        /// <summary>Sends the bytes; throws <see cref="LocalApiException"/> NOT_FOUND / VALIDATION_ERROR / PRINTER_UNREACHABLE.</summary>
        public async Task<int> PrintAsync(string printerLocalId, string dataBase64, string encoding, CancellationToken ct)
        {
            if (encoding != "cp866" && encoding != "raster") throw LocalApiException.Validation("encoding", "invalid_choice");
            byte[] data;
            try
            {
                data = Convert.FromBase64String(dataBase64);
            }
            catch (FormatException)
            {
                throw LocalApiException.Validation("data_base64", "base64");
            }

            if (data.Length == 0) throw LocalApiException.Validation("data_base64", "required");
            if (data.Length > MaxBytes) throw new LocalApiException(LocalCodes.FileTooLarge);
            var printer = Resolve(printerLocalId)
                ?? throw new LocalApiException(LocalCodes.NotFound, new Dictionary<string, object?> { ["printer_local_id"] = printerLocalId });

            var lane = _lanes.For("printer:" + printer.LocalId);
            using (await lane.EnterAsync(true, ct).ConfigureAwait(false))
            {
                try
                {
                    await _transport.SendAsync(_address(printer), printer.Port, data, ct).ConfigureAwait(false);
                    _status[printer.LocalId] = "ok";
                }
                catch (PrinterUnreachableException e)
                {
                    _status[printer.LocalId] = "offline";
                    _log.Warn(LocalCodes.PrinterUnreachable, "printer unreachable: " + e.Message, new Dictionary<string, object?> { ["printer_local_id"] = printer.LocalId });
                    throw new LocalApiException(LocalCodes.PrinterUnreachable, new Dictionary<string, object?> { ["printer_local_id"] = printer.LocalId });
                }
            }

            return data.Length;
        }
    }

    /// <summary>Local API <c>POST /v1/print/raw</c>, server task <c>print.raw</c> and the <c>print</c> capability.</summary>
    public sealed class PrinterModule : ILocalApiModule, IAgentTaskHandler, ICapabilityProvider
    {
        private static readonly string[] KindList = { "print.raw" };
        private static readonly StrictObject Schema = new StrictObject()
            .Required("printer_local_id", StrictObject.IsNonEmptyString)
            .Required("data_base64", StrictObject.IsNonEmptyString)
            .Required("encoding", StrictObject.IsOneOf("cp866", "raster"));

        private readonly PrinterService _svc;

        public PrinterModule(PrinterService svc)
        {
            _svc = svc;
        }

        public IEnumerable<LocalRoute> Routes => new[] { new LocalRoute("POST", "/v1/print/raw", PrintRaw) };

        public IReadOnlyCollection<string> Kinds => KindList;

        public string Family => "print";

        public object Describe()
        {
            var active = _svc.Active();
            if (active.Count == 0) return new { enabled = false, version = 0, devices = Array.Empty<object>() };
            return new
            {
                enabled = true,
                version = 1,
                devices = active.Select(p => new { local_id = p.LocalId, transport = "tcp9100", host = p.Host, port = p.Port, status = _svc.StatusOf(p.LocalId) }).ToArray(),
            };
        }

        private async Task<LocalResponse> PrintRaw(LocalRequest r, CancellationToken ct)
        {
            var b = new BodyReader(r.JsonBody());
            await _svc.PrintAsync(b.RequireString("printer_local_id", 64), b.RequireString("data_base64", 8 * 1024 * 1024), b.RequireString("encoding", 16), ct).ConfigureAwait(false);
            return LocalResponse.Json(new { status = "sent" });
        }

        public string? ValidatePayload(string kind, JsonElement payload) => Schema.Validate(payload);

        public async Task<TaskExecution> ExecuteAsync(TaskContext context, JsonElement payload, CancellationToken ct)
        {
            var id = payload.GetProperty("printer_local_id").GetString()!;
            context.Progress("uploading", 10);
            try
            {
                var bytes = await _svc.PrintAsync(id, payload.GetProperty("data_base64").GetString()!, payload.GetProperty("encoding").GetString()!, ct).ConfigureAwait(false);
                return TaskExecution.Done(new { status = "sent", printer_local_id = id, bytes });
            }
            catch (LocalApiException e)
            {
                return TaskExecution.Failed(ErrorObj.Of(
                    e.Code,
                    e.Code == LocalCodes.NotFound ? "printer is not registered on this agent" : e.Code == LocalCodes.PrinterUnreachable ? "printer unreachable" : "invalid print job",
                    false, // a print job is never retried automatically (no duplicate receipt)
                    e.Code == LocalCodes.NotFound ? "payload.printer_local_id" : e.Code == LocalCodes.ValidationError ? "payload" : null));
            }
        }
    }
}

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Core.Errors;
using Erp1C.Core.Hosting;
using Erp1C.Core.Masking;

namespace Erp1C.Agent.LocalApi
{
    /// <summary>The <c>Origin</c> allow-list of the local API (21 §16 (b)).</summary>
    public sealed class OriginPolicy
    {
        private readonly HashSet<string> _allowed;

        public OriginPolicy(IEnumerable<string> allowed)
        {
            _allowed = new HashSet<string>(allowed.Select(Normalize).Where(o => o.Length > 0), StringComparer.OrdinalIgnoreCase);
        }

        public IReadOnlyCollection<string> Allowed => _allowed;

        public static string Normalize(string origin) => (origin ?? string.Empty).Trim().TrimEnd('/');

        /// <summary>Exact scheme://host[:port] match; a missing Origin or <c>null</c> is never allowed.</summary>
        public bool IsAllowed(string? origin) =>
            !string.IsNullOrEmpty(origin) && !string.Equals(origin, "null", StringComparison.OrdinalIgnoreCase) && _allowed.Contains(Normalize(origin!));
    }

    internal sealed class HttpRequestData
    {
        public string Method { get; set; } = string.Empty;

        public string Target { get; set; } = string.Empty;

        public Dictionary<string, string> Headers { get; } = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        public byte[] Body { get; set; } = Array.Empty<byte>();

        public string? Header(string name) => Headers.TryGetValue(name, out var v) ? v : null;
    }

    internal sealed class HttpBadRequest : Exception
    {
        public HttpBadRequest()
        {
        }

        public HttpBadRequest(string message)
            : base(message)
        {
        }

        public HttpBadRequest(string message, Exception inner)
            : base(message, inner)
        {
        }

        public int Status { get; set; } = 400;
    }

    /// <summary>
    /// Local API server (21 §16, §16.1): a minimal HTTP/1.1 server on a <see cref="TcpListener"/> bound to
    /// <c>127.0.0.1</c> ONLY (never another interface; no URL ACL / admin needed), one request per connection.
    /// Order of checks: Host (loopback names only — DNS-rebinding guard) → Origin allow-list (else 403, no CORS
    /// headers) → CORS/PNA preflight → route → device-bound local token (<c>Authorization: Bearer</c> +
    /// <c>X-Device-Id</c>, else 401) → handler. Errors use the <c>{code, message_key, params?}</c> shape.
    /// </summary>
    public sealed class LocalApiServer : IDisposable
    {
        public const int MaxHeaderBytes = 16 * 1024;
        public const int MaxBodyBytes = 8 * 1024 * 1024;
        private static readonly TimeSpan ReadTimeout = TimeSpan.FromSeconds(15);
        private static readonly string[] CrLf = { "\r\n" };
        private static readonly char[] Amp = { '&' };

        private readonly OriginPolicy _origins;
        private readonly LocalPairing _pairing;
        private readonly List<LocalRoute> _routes;
        private readonly IAgentLogger _log;
        private readonly CancellationTokenSource _stop = new CancellationTokenSource();
        private TcpListener? _listener;

        public LocalApiServer(int port, OriginPolicy origins, LocalPairing pairing, IEnumerable<ILocalApiModule> modules, IAgentLogger? log = null)
        {
            Port = port;
            _origins = origins;
            _pairing = pairing;
            _routes = modules.SelectMany(m => m.Routes).ToList();
            _log = log ?? NullAgentLogger.Instance;
        }

        public int Port { get; private set; }

        public IPEndPoint? LocalEndpoint => _listener?.LocalEndpoint as IPEndPoint;

        public void Start()
        {
            _listener = new TcpListener(IPAddress.Loopback, Port);
            _listener.Server.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ExclusiveAddressUse, true);
            _listener.Start(64);
            Port = ((IPEndPoint)_listener.LocalEndpoint).Port;
            _ = Task.Run(AcceptLoop);
        }

        private async Task AcceptLoop()
        {
            while (!_stop.IsCancellationRequested)
            {
                TcpClient client;
                try
                {
                    client = await _listener!.AcceptTcpClientAsync().ConfigureAwait(false);
                }
                catch (Exception e) when (e is ObjectDisposedException || e is SocketException || e is InvalidOperationException)
                {
                    return;
                }

                _ = Task.Run(() => HandleClientAsync(client));
            }
        }

        private async Task HandleClientAsync(TcpClient client)
        {
            using (client)
            {
                try
                {
                    var remote = (IPEndPoint)client.Client.RemoteEndPoint;
                    if (!IPAddress.IsLoopback(remote.Address)) return; // defence in depth — the socket is loopback-only
                    var stream = client.GetStream();
                    HttpRequestData req;
                    using (var rcts = CancellationTokenSource.CreateLinkedTokenSource(_stop.Token))
                    {
                        rcts.CancelAfter(ReadTimeout);
                        try
                        {
                            req = await ReadRequestAsync(stream, rcts.Token).ConfigureAwait(false);
                        }
                        catch (HttpBadRequest bad)
                        {
                            await WriteAsync(stream, bad.Status, null, LocalResponse.Error(bad.Status, bad.Status == 413 ? LocalCodes.FileTooLarge : LocalCodes.ValidationError).Body, null).ConfigureAwait(false);
                            return;
                        }
                    }

                    var (status, origin, body, extra) = await DispatchAsync(req).ConfigureAwait(false);
                    await WriteAsync(stream, status, origin, body, extra).ConfigureAwait(false);
                }
                catch (Exception e) when (e is IOException || e is SocketException || e is OperationCanceledException || e is ObjectDisposedException)
                {
                    // client went away; a running card purchase continues and is journaled (21 §16.1)
                }
            }
        }

        /// <summary>The whole pipeline for one parsed request (also used by tests).</summary>
        internal async Task<(int Status, string? AllowOrigin, byte[] Body, Dictionary<string, string>? Extra)> DispatchAsync(HttpRequestData req)
        {
            var host = req.Header("Host");
            if (!IsLoopbackHost(host)) return (403, null, LocalResponse.Error(LocalCodes.PermissionDenied, new Dictionary<string, object?> { ["reason"] = "host" }).Body, null);

            var origin = req.Header("Origin");
            if (!_origins.IsAllowed(origin)) return (403, null, LocalResponse.Error(LocalCodes.PermissionDenied, new Dictionary<string, object?> { ["reason"] = "origin" }).Body, null);

            if (req.Method == "OPTIONS")
            {
                var extra = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                {
                    ["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS",
                    ["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Device-Id",
                    ["Access-Control-Max-Age"] = "600",
                };
                if (string.Equals(req.Header("Access-Control-Request-Private-Network"), "true", StringComparison.OrdinalIgnoreCase))
                {
                    extra["Access-Control-Allow-Private-Network"] = "true";
                }

                return (204, origin, Array.Empty<byte>(), extra);
            }

            var q = req.Target.IndexOf('?');
            var path = q >= 0 ? req.Target.Substring(0, q) : req.Target;
            var query = ParseQuery(q >= 0 ? req.Target.Substring(q + 1) : string.Empty);
            LocalRoute? route = null;
            Dictionary<string, string>? values = null;
            foreach (var r in _routes)
            {
                if (r.Method == req.Method && r.TryMatch(path, out var v))
                {
                    route = r;
                    values = v;
                    break;
                }
            }

            if (route is null) return (404, origin, LocalResponse.Error(LocalCodes.NotFound).Body, null);

            string? deviceId = null;
            if (!route.Anonymous)
            {
                var auth = req.Header("Authorization");
                var token = auth != null && auth.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase) ? auth.Substring(7).Trim() : null;
                deviceId = req.Header("X-Device-Id");
                if (!_pairing.Validate(token, deviceId)) return (401, origin, LocalResponse.Error(LocalCodes.Unauthorized).Body, null);
            }

            try
            {
                var resp = await route.Handler(new LocalRequest(req.Method, path, query, req.Body, values!, deviceId), _stop.Token).ConfigureAwait(false);
                return (resp.Status, origin, resp.Body, null);
            }
            catch (LocalApiException e)
            {
                var r = e.ToResponse();
                return (r.Status, origin, r.Body, null);
            }
            catch (OperationCanceledException)
            {
                return (503, origin, LocalResponse.Error(503, LocalCodes.InternalError).Body, null);
            }
            catch (Exception e)
            {
                _log.Error("local_api.error", "local API handler failed: " + SecretMasker.Mask(e.GetType().Name + ": " + e.Message), new Dictionary<string, object?> { ["path"] = path });
                return (500, origin, LocalResponse.Error(LocalCodes.InternalError).Body, null);
            }
        }

        private bool IsLoopbackHost(string? host)
        {
            if (string.IsNullOrEmpty(host)) return false;
            var p = Port.ToString(CultureInfo.InvariantCulture);
            return string.Equals(host, "127.0.0.1:" + p, StringComparison.OrdinalIgnoreCase)
                || string.Equals(host, "localhost:" + p, StringComparison.OrdinalIgnoreCase);
        }

        private static Dictionary<string, string> ParseQuery(string qs)
        {
            var d = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (var part in qs.Split(Amp, StringSplitOptions.RemoveEmptyEntries))
            {
                var i = part.IndexOf('=');
                var k = Uri.UnescapeDataString((i >= 0 ? part.Substring(0, i) : part).Replace('+', ' '));
                var v = i >= 0 ? Uri.UnescapeDataString(part.Substring(i + 1).Replace('+', ' ')) : string.Empty;
                d[k] = v;
            }

            return d;
        }

        internal static async Task<HttpRequestData> ReadRequestAsync(Stream s, CancellationToken ct)
        {
            var head = new MemoryStream();
            var buf = new byte[1];
            var last4 = 0u;
            while (true)
            {
                var n = await s.ReadAsync(buf, 0, 1, ct).ConfigureAwait(false);
                if (n == 0) throw new IOException("connection closed");
                head.WriteByte(buf[0]);
                last4 = (last4 << 8) | buf[0];
                if (last4 == 0x0D0A0D0A) break;
                if (head.Length > MaxHeaderBytes) throw new HttpBadRequest("headers too large") { Status = 431 };
            }

            var text = Encoding.ASCII.GetString(head.ToArray());
            var lines = text.Split(CrLf, StringSplitOptions.None);
            var first = lines[0].Split(' ');
            if (first.Length != 3 || !first[2].StartsWith("HTTP/1.", StringComparison.Ordinal)) throw new HttpBadRequest("bad request line");
            var req = new HttpRequestData { Method = first[0].ToUpperInvariant(), Target = first[1] };
            if (!req.Target.StartsWith("/", StringComparison.Ordinal)) throw new HttpBadRequest("absolute-form not allowed");
            foreach (var l in lines.Skip(1))
            {
                if (l.Length == 0) continue;
                var c = l.IndexOf(':');
                if (c <= 0) throw new HttpBadRequest("bad header");
                var name = l.Substring(0, c).Trim();
                var value = l.Substring(c + 1).Trim();
                if (req.Headers.TryGetValue(name, out var existing))
                {
                    if (string.Equals(name, "Host", StringComparison.OrdinalIgnoreCase) || string.Equals(name, "Content-Length", StringComparison.OrdinalIgnoreCase) || string.Equals(name, "Origin", StringComparison.OrdinalIgnoreCase))
                    {
                        throw new HttpBadRequest("duplicate " + name);
                    }

                    req.Headers[name] = existing + ", " + value;
                }
                else
                {
                    req.Headers[name] = value;
                }
            }

            if (req.Header("Transfer-Encoding") != null) throw new HttpBadRequest("chunked bodies are not supported") { Status = 411 };
            var cl = req.Header("Content-Length");
            if (cl != null)
            {
                if (!long.TryParse(cl, NumberStyles.None, CultureInfo.InvariantCulture, out var len)) throw new HttpBadRequest("bad Content-Length");
                if (len > MaxBodyBytes) throw new HttpBadRequest("body too large") { Status = 413 };
                var body = new byte[len];
                var read = 0;
                while (read < len)
                {
                    var n = await s.ReadAsync(body, read, (int)len - read, ct).ConfigureAwait(false);
                    if (n == 0) throw new IOException("connection closed");
                    read += n;
                }

                req.Body = body;
            }

            return req;
        }

        private static async Task WriteAsync(Stream s, int status, string? allowOrigin, byte[] body, Dictionary<string, string>? extra)
        {
            var sb = new StringBuilder();
            sb.Append("HTTP/1.1 ").Append(status.ToString(CultureInfo.InvariantCulture)).Append(' ').Append(Reason(status)).Append("\r\n");
            if (body.Length > 0) sb.Append("Content-Type: application/json; charset=utf-8\r\n");
            sb.Append("Content-Length: ").Append(body.Length.ToString(CultureInfo.InvariantCulture)).Append("\r\n");
            sb.Append("Cache-Control: no-store\r\n");
            sb.Append("X-Content-Type-Options: nosniff\r\n");
            sb.Append("Connection: close\r\n");
            if (allowOrigin != null)
            {
                sb.Append("Access-Control-Allow-Origin: ").Append(allowOrigin).Append("\r\n");
                sb.Append("Vary: Origin\r\n");
            }

            if (extra != null)
            {
                foreach (var kv in extra) sb.Append(kv.Key).Append(": ").Append(kv.Value).Append("\r\n");
            }

            sb.Append("\r\n");
            var head = Encoding.ASCII.GetBytes(sb.ToString());
            await s.WriteAsync(head, 0, head.Length).ConfigureAwait(false);
            if (body.Length > 0) await s.WriteAsync(body, 0, body.Length).ConfigureAwait(false);
            await s.FlushAsync().ConfigureAwait(false);
        }

        private static string Reason(int status) => status switch
        {
            200 => "OK",
            202 => "Accepted",
            204 => "No Content",
            400 => "Bad Request",
            401 => "Unauthorized",
            403 => "Forbidden",
            404 => "Not Found",
            409 => "Conflict",
            411 => "Length Required",
            413 => "Payload Too Large",
            422 => "Unprocessable Entity",
            429 => "Too Many Requests",
            431 => "Request Header Fields Too Large",
            500 => "Internal Server Error",
            502 => "Bad Gateway",
            503 => "Service Unavailable",
            504 => "Gateway Timeout",
            _ => "Status",
        };

        public void Dispose()
        {
            _stop.Cancel();
            _listener?.Stop();
            _stop.Dispose();
        }
    }
}

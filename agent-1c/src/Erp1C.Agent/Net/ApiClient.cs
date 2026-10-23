using System;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Agent.App;
using Erp1C.Core.Contracts;
using Erp1C.Core.Json;

namespace Erp1C.Agent.Net
{
    public sealed class ApiResponse<T>
    {
        public ApiResponse(int status, T? value)
        {
            Status = status;
            Value = value;
        }

        public int Status { get; }

        public T? Value { get; }
    }

    /// <summary>
    /// Agent API client (34 §7.1): one HttpClient for the process, Bearer token, <c>X-Agent-Version</c>,
    /// <c>X-Agent-Protocol: 2</c>, <c>User-Agent</c>, gzip for bodies &gt; 16 KB, 17 §7 error envelope →
    /// <see cref="ApiException"/>; a 401 gets exactly one fresh token and one retry (33 §9.9).
    /// </summary>
    public sealed class ApiClient
    {
        public const int GzipThreshold = 16 * 1024;
        public const int MaxBody = 10 * 1024 * 1024;

        private readonly HttpClient _http;
        private readonly Func<string> _serverBase;
        private readonly AuthClient _auth;
        private readonly ClockSync _clock;

        public ApiClient(HttpClient http, Func<string> serverBase, AuthClient auth, ClockSync clock)
        {
            _http = http;
            _serverBase = serverBase;
            _auth = auth;
            _clock = clock;
        }

        /// <summary>
        /// The process-wide HttpClient: system (IE/WinINET) proxy with default credentials, gzip/deflate, no
        /// redirects; TLS 1.2+ and 16 connections (net48 default 2 blocks the long-poll) — 34 §7.1. Certificate
        /// validation is never changed.
        /// </summary>
        public static HttpClient CreateHttpClient()
        {
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12 | (SecurityProtocolType)12288; // Tls13 where the OS has it
            ServicePointManager.DefaultConnectionLimit = 16;
            ServicePointManager.Expect100Continue = false;
#pragma warning disable CA2000 // owned by the HttpClient
            var handler = new HttpClientHandler
            {
                UseProxy = true,
                Proxy = WebRequest.DefaultWebProxy,
                DefaultProxyCredentials = CredentialCache.DefaultCredentials,
                AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate,
                AllowAutoRedirect = false,
            };
#pragma warning restore CA2000
            return new HttpClient(handler, true) { Timeout = System.Threading.Timeout.InfiniteTimeSpan };
        }

        public Task<ApiResponse<T>> PostAsync<T>(string path, object? body, TimeSpan timeout, CancellationToken ct) =>
            SendAsync<T>(HttpMethod.Post, path, body, timeout, ct);

        public Task<ApiResponse<T>> GetAsync<T>(string path, TimeSpan timeout, CancellationToken ct) =>
            SendAsync<T>(HttpMethod.Get, path, null, timeout, ct);

        public async Task<ApiResponse<T>> SendAsync<T>(HttpMethod method, string path, object? body, TimeSpan timeout, CancellationToken ct)
        {
            for (var attempt = 0; ; attempt++)
            {
                var token = await _auth.GetAccessTokenAsync(attempt > 0, ct).ConfigureAwait(false);
                using var req = Build(method, path, body, token);
                using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
                cts.CancelAfter(timeout);
                HttpResponseMessage resp;
                try
                {
                    resp = await _http.SendAsync(req, HttpCompletionOption.ResponseContentRead, cts.Token).ConfigureAwait(false);
                }
                catch (Exception e) when (e is HttpRequestException || (e is OperationCanceledException && !ct.IsCancellationRequested))
                {
                    throw NetworkException.From(e);
                }

                using (resp)
                {
                    _clock.FromDateHeader(resp.Headers.Date);
                    var status = (int)resp.StatusCode;
                    if (status == 401 && attempt == 0) continue; // one fresh assertion → token → retry
                    var bytes = resp.Content is null ? Array.Empty<byte>() : await resp.Content.ReadAsByteArrayAsync().ConfigureAwait(false);
                    if (status >= 200 && status < 300)
                    {
                        if (status == 204 || bytes.Length == 0) return new ApiResponse<T>(status, default);
                        return new ApiResponse<T>(status, AgentJson.Deserialize<T>(bytes));
                    }

                    throw ToException(status, bytes, resp.Headers.RetryAfter);
                }
            }
        }

        /// <summary>A-07 multipart upload (diagnostics zip ≤ 20 MB).</summary>
        public async Task<string?> UploadDiagnosticsAsync(string taskId, string zipPath, CancellationToken ct)
        {
            for (var attempt = 0; ; attempt++)
            {
                var token = await _auth.GetAccessTokenAsync(attempt > 0, ct).ConfigureAwait(false);
                using var content = new MultipartFormDataContent();
                using var file = new ByteArrayContent(File.ReadAllBytes(zipPath));
                file.Headers.ContentType = new MediaTypeHeaderValue("application/zip");
                content.Add(file, "file", Path.GetFileName(zipPath));
                using var tid = new StringContent(taskId);
                content.Add(tid, "task_id");
                using var req = new HttpRequestMessage(HttpMethod.Post, _serverBase() + "/api/v1/onec-agent/diagnostics") { Content = content };
                AddHeaders(req, token);
                HttpResponseMessage resp;
                try
                {
                    resp = await _http.SendAsync(req, ct).ConfigureAwait(false);
                }
                catch (HttpRequestException e)
                {
                    throw NetworkException.From(e);
                }

                using (resp)
                {
                    var status = (int)resp.StatusCode;
                    if (status == 401 && attempt == 0) continue;
                    var bytes = await resp.Content.ReadAsByteArrayAsync().ConfigureAwait(false);
                    if (status == 201 || status == 200)
                    {
                        using var doc = JsonDocument.Parse(bytes);
                        return doc.RootElement.TryGetProperty("attachment_id", out var a) ? a.GetString() : null;
                    }

                    throw ToException(status, bytes, resp.Headers.RetryAfter);
                }
            }
        }

        private HttpRequestMessage Build(HttpMethod method, string path, object? body, string token)
        {
            var req = new HttpRequestMessage(method, _serverBase() + path);
            AddHeaders(req, token);
            if (body != null)
            {
                var json = AgentJson.SerializeUtf8(body);
                if (json.Length > GzipThreshold)
                {
                    using var ms = new MemoryStream();
                    using (var gz = new GZipStream(ms, CompressionLevel.Optimal, true)) gz.Write(json, 0, json.Length);
                    var gzBytes = ms.ToArray();
                    if (gzBytes.Length > MaxBody) throw new ApiException(413, "FILE_TOO_LARGE");
                    var c = new ByteArrayContent(gzBytes);
                    c.Headers.ContentType = new MediaTypeHeaderValue("application/json") { CharSet = "utf-8" };
                    c.Headers.ContentEncoding.Add("gzip");
                    req.Content = c;
                }
                else
                {
                    var c = new ByteArrayContent(json);
                    c.Headers.ContentType = new MediaTypeHeaderValue("application/json") { CharSet = "utf-8" };
                    req.Content = c;
                }
            }

            return req;
        }

        private static void AddHeaders(HttpRequestMessage req, string token)
        {
            req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            req.Headers.TryAddWithoutValidation("X-Agent-Version", BuildInfo.Version);
            req.Headers.TryAddWithoutValidation("X-Agent-Protocol", BuildInfo.Protocol.ToString(System.Globalization.CultureInfo.InvariantCulture));
            req.Headers.TryAddWithoutValidation("User-Agent", BuildInfo.UserAgent(MachineInfo.OsShort(), MachineInfo.Arch()));
            req.Headers.TryAddWithoutValidation("Accept", "application/json");
            req.Headers.TryAddWithoutValidation("Accept-Encoding", "gzip");
        }

        internal static ApiException ToException(int status, byte[] bytes, RetryConditionHeaderValue? retryAfter)
        {
            ApiErrorBody? err = null;
            try
            {
                if (bytes.Length > 0) err = AgentJson.Deserialize<ApiErrorEnvelope>(bytes)?.Error;
            }
            catch (JsonException)
            {
            }

            var code = err?.Code ?? (status == 426 ? "ONEC_AGENT_UPDATE_REQUIRED" : "HTTP_" + status.ToString(System.Globalization.CultureInfo.InvariantCulture));
            return new ApiException(status, code, err?.RequestId, retryAfter?.Delta, err?.Params);
        }
    }
}

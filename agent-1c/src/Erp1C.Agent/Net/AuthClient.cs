using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Agent.App;
using Erp1C.Agent.State;
using Erp1C.Core.Contracts;
using Erp1C.Core.Crypto;
using Erp1C.Core.Json;

namespace Erp1C.Agent.Net
{
    /// <summary>Pairing (device grant) ended without a token.</summary>
    public sealed class PairingException : Exception
    {
        public PairingException()
        {
        }

        public PairingException(string message)
            : base(message)
        {
            Reason = message;
        }

        public PairingException(string message, Exception inner)
            : base(message, inner)
        {
            Reason = message;
        }

        /// <summary>expired | denied | rate_limited.</summary>
        public string Reason { get; } = "expired";
    }

    /// <summary>Claims of the agent access token the acceptor needs (33 §9.11 #2).</summary>
    public sealed class TokenClaims
    {
        public string? TenantId { get; set; }

        public string? AgentId { get; set; }

        public string? DeviceId { get; set; }

        /// <summary>Reads the JWT payload without verifying it — it came over TLS from our own AS (34 §5.4).</summary>
        public static TokenClaims Parse(string jwt)
        {
            var c = new TokenClaims();
            try
            {
                var parts = jwt.Split('.');
                if (parts.Length < 2) return c;
                using var doc = JsonDocument.Parse(Base64Url.Decode(parts[1]));
                var r = doc.RootElement;
                c.TenantId = Str(r, "tenant_id");
                c.AgentId = Str(r, "agent_id");
                c.DeviceId = Str(r, "device_id");
            }
            catch (Exception e) when (e is FormatException || e is JsonException)
            {
            }

            return c;
        }

        private static string? Str(JsonElement r, string n) => r.TryGetProperty(n, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;
    }

    /// <summary>
    /// OAuth client of the agent (33 §9.2, 34 §5.3/§5.4): RFC 8628 device grant for pairing, then
    /// <c>client_credentials</c> + <c>private_key_jwt</c> (RFC 7523). No refresh token; the access token lives only in
    /// memory and is renewed after 480 s or on 401 — one renewal at a time.
    /// </summary>
    public sealed class AuthClient : IDisposable
    {
        public const string ClientId = "onec-agent";
        public const string Scope = "onec.agent";
        public static readonly TimeSpan RefreshAfter = TimeSpan.FromSeconds(480);

        private readonly HttpClient _http;
        private readonly Func<string> _serverBase;
        private readonly AgentKeyStore _keys;
        private readonly SettingsStore _settings;
        private readonly ClockSync _clock;
        private readonly string _machineHash;
        private readonly Func<TimeSpan, CancellationToken, Task> _delay;
        private readonly SemaphoreSlim _gate = new SemaphoreSlim(1, 1);
        private readonly Stopwatch _age = new Stopwatch();
        private string? _token;

        public AuthClient(HttpClient http, Func<string> serverBase, AgentKeyStore keys, SettingsStore settings, ClockSync clock, string machineHash, Func<TimeSpan, CancellationToken, Task>? delay = null)
        {
            _http = http;
            _serverBase = serverBase;
            _keys = keys;
            _settings = settings;
            _clock = clock;
            _machineHash = machineHash;
            _delay = delay ?? ((d, ct) => Task.Delay(d, ct));
        }

        public TokenClaims Claims { get; private set; } = new TokenClaims();

        public int RefreshOk { get; private set; }

        public int RefreshFailed { get; private set; }

        private string TokenUrl => _serverBase() + "/oauth/token";

        // ---------------------------------------------------------------- device grant (pairing)

        public async Task<DeviceAuthorizationResponse> StartDeviceAuthorizationAsync(CancellationToken ct)
        {
            var key = _keys.EnsureKey(_clock.UtcNow);
            var form = new Dictionary<string, string>
            {
                ["client_id"] = ClientId,
                ["scope"] = Scope,
                ["public_jwk"] = JwkThumbprint.PublicJwkJson(Base64Url.Decode(key.X)),
                ["machine_hash"] = _machineHash,
                ["pc_name"] = MachineInfo.PcName(),
                ["os_version"] = MachineInfo.OsVersion(),
                ["agent_version"] = BuildInfo.Version,
            };
            var (status, body, resp) = await PostFormAsync(_serverBase() + "/oauth/device_authorization", form, ct).ConfigureAwait(false);
            if (status == 200) return AgentJson.Deserialize<DeviceAuthorizationResponse>(body) ?? throw new ApiException(502, "invalid_response");
            throw OAuthFailure(status, body, resp);
        }

        /// <summary>Polls the token endpoint every <c>interval</c> s (slow_down → +5 s) until a token or a final error.</summary>
        public async Task<TokenResponse> PollDeviceTokenAsync(DeviceAuthorizationResponse auth, CancellationToken ct)
        {
            var interval = TimeSpan.FromSeconds(Math.Max(5, auth.Interval));
            var deadline = _clock.LocalNow + TimeSpan.FromSeconds(Math.Max(1, auth.ExpiresIn));
            var backoff = new Backoff();
            while (_clock.LocalNow < deadline)
            {
                await _delay(interval, ct).ConfigureAwait(false);
                string body;
                int status;
                HttpResponseMessage? resp;
                try
                {
                    (status, body, resp) = await PostFormAsync(TokenUrl, new Dictionary<string, string>
                    {
                        ["grant_type"] = "urn:ietf:params:oauth:grant-type:device_code",
                        ["device_code"] = auth.DeviceCode,
                        ["client_id"] = ClientId,
                    }, ct).ConfigureAwait(false);
                }
                catch (NetworkException)
                {
                    await _delay(backoff.Next(), ct).ConfigureAwait(false);
                    continue;
                }

                backoff.Reset();
                if (status == 200)
                {
                    var tr = AgentJson.Deserialize<TokenResponse>(body) ?? throw new ApiException(502, "invalid_response");
                    SetToken(tr.AccessToken);
                    return tr;
                }

                var err = ParseOAuth(body);
                switch (err?.Error)
                {
                    case "authorization_pending":
                        continue;
                    case "slow_down":
                        if (status == 429) throw new PairingException("rate_limited");
                        interval += TimeSpan.FromSeconds(5);
                        continue;
                    case "access_denied":
                        throw new PairingException("denied");
                    case "expired_token":
                    case "invalid_grant":
                        throw new PairingException("expired");
                    default:
                        if (status == 429) throw new PairingException("rate_limited");
                        if (status >= 500) continue;
                        throw new PairingException("expired");
                }
            }

            throw new PairingException("expired");
        }

        // ---------------------------------------------------------------- private_key_jwt

        /// <summary>RFC 7523 client assertion (34 §5.4) — <c>iat</c>/<c>exp</c> from the corrected clock, exp = iat + 60.</summary>
        public string BuildClientAssertion(string agentClientId, string kid, DateTimeOffset now)
        {
            var header = new JsonObject { ["alg"] = "EdDSA", ["typ"] = "JWT", ["kid"] = kid };
            var iat = now.ToUnixTimeSeconds();
            var claims = new JsonObject
            {
                ["iss"] = agentClientId,
                ["sub"] = agentClientId,
                ["aud"] = TokenUrl,
                ["jti"] = Guid.NewGuid().ToString("D"),
                ["iat"] = iat,
                ["exp"] = iat + 60,
            };
            return CompactJws.Sign(header, claims, _keys.Sign);
        }

        /// <summary>The cached access token, renewed after 480 s (or when <paramref name="force"/> after a 401).</summary>
        public async Task<string> GetAccessTokenAsync(bool force, CancellationToken ct)
        {
            if (!force && _token != null && _age.Elapsed < RefreshAfter) return _token;
            await _gate.WaitAsync(ct).ConfigureAwait(false);
            try
            {
                if (!force && _token != null && _age.Elapsed < RefreshAfter) return _token;
                var s = _settings.Current;
                if (!s.IsPaired) throw new ApiException(401, "not_paired");
                var key = _keys.Read() ?? throw new AgentKeyUnavailableException("agent.key missing");
                for (var attempt = 0; ; attempt++)
                {
                    var form = new Dictionary<string, string>
                    {
                        ["grant_type"] = "client_credentials",
                        ["client_id"] = s.AgentClientId!,
                        ["client_assertion_type"] = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                        ["client_assertion"] = BuildClientAssertion(s.AgentClientId!, key.Kid, _clock.UtcNow),
                        ["scope"] = Scope,
                    };
                    var (status, body, resp) = await PostFormAsync(TokenUrl, form, ct).ConfigureAwait(false);
                    if (status == 200)
                    {
                        var tr = AgentJson.Deserialize<TokenResponse>(body) ?? throw new ApiException(502, "invalid_response");
                        SetToken(tr.AccessToken);
                        RefreshOk++;
                        return tr.AccessToken;
                    }

                    var err = ParseOAuth(body);
                    if (err?.Error == "invalid_client" && err.ErrorDescription == "agent_revoked")
                    {
                        RefreshFailed++;
                        throw new ApiException(401, "agent_revoked");
                    }

                    // A clock-skew rejection: take the offset from the Date header and try exactly once more (34 §5.4).
                    if ((status == 400 || status == 401) && attempt == 0)
                    {
                        _clock.FromDateHeader(resp?.Headers.Date, force: true);
                        continue;
                    }

                    RefreshFailed++;
                    throw OAuthFailure(status, body, resp);
                }
            }
            finally
            {
                _gate.Release();
            }
        }

        public void SetToken(string token)
        {
            _token = token;
            Claims = TokenClaims.Parse(token);
            _age.Restart();
        }

        public void Dispose() => _gate.Dispose();

        public void ForgetToken()
        {
            _token = null;
            Claims = new TokenClaims();
        }

        // ---------------------------------------------------------------- helpers

        private async Task<(int Status, string Body, HttpResponseMessage? Response)> PostFormAsync(string url, Dictionary<string, string> form, CancellationToken ct)
        {
            using var req = new HttpRequestMessage(HttpMethod.Post, url) { Content = new FormUrlEncodedContent(form) };
            req.Headers.TryAddWithoutValidation("User-Agent", BuildInfo.UserAgent(MachineInfo.OsShort(), MachineInfo.Arch()));
            req.Headers.TryAddWithoutValidation("Accept", "application/json");
            HttpResponseMessage resp;
            try
            {
                resp = await _http.SendAsync(req, ct).ConfigureAwait(false);
            }
            catch (Exception e) when (e is HttpRequestException || (e is TaskCanceledException && !ct.IsCancellationRequested))
            {
                throw NetworkException.From(e);
            }

            _clock.FromDateHeader(resp.Headers.Date);
            var body = resp.Content is null ? string.Empty : await resp.Content.ReadAsStringAsync().ConfigureAwait(false);
            return ((int)resp.StatusCode, body, resp);
        }

        private static OAuthError? ParseOAuth(string body)
        {
            try
            {
                return string.IsNullOrEmpty(body) ? null : AgentJson.Deserialize<OAuthError>(body);
            }
            catch (JsonException)
            {
                return null;
            }
        }

        private static ApiException OAuthFailure(int status, string body, HttpResponseMessage? resp)
        {
            var err = ParseOAuth(body);
            var retryAfter = resp?.Headers.RetryAfter?.Delta;
            return new ApiException(status, status == 429 ? "RATE_LIMITED" : err?.Error ?? "oauth_error", null, retryAfter);
        }
    }
}

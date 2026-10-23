using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Erp1C.Agent.State;
using Erp1C.Core.Crypto;
using Erp1C.Core.Errors;
using Erp1C.Core.Hosting;
using Erp1C.Core.Json;
using Erp1C.Core.Security;
using Erp1C.Core.Storage;

#pragma warning disable CA2227
#pragma warning disable CA1002

namespace Erp1C.Agent.LocalApi
{
    public sealed class PairedDevice
    {
        public string DeviceId { get; set; } = string.Empty;

        /// <summary>base64(DPAPI(local_token)), entropy <c>ErpOneCAgent/local-token/v1|&lt;device_id&gt;</c>.</summary>
        public string TokenProtected { get; set; } = string.Empty;

        public string PairedAt { get; set; } = string.Empty;

        public string? LastUsedAt { get; set; }
    }

    /// <summary>
    /// POS ↔ agent pairing (21 §16): the tray shows a one-time 6-digit code valid for 5 minutes; <c>POST /v1/pair
    /// {code, device_id}</c> returns a random 256-bit <c>local_token</c> stored only as a DPAPI blob paired with the
    /// POS <c>devices.id</c>. A token works only together with its own device id (<c>X-Device-Id</c>). Five wrong
    /// codes burn the current code. The server never sees the token.
    /// </summary>
    public sealed class LocalPairing
    {
        public static readonly TimeSpan CodeLifetime = TimeSpan.FromMinutes(5);
        public const int MaxAttempts = 5;

        private readonly string _path;
        private readonly ISecretProtector _protector;
        private readonly IClock _clock;
        private readonly object _lock = new object();
        private readonly Dictionary<string, byte[]> _tokenHashes = new Dictionary<string, byte[]>(StringComparer.OrdinalIgnoreCase);
        private List<PairedDevice> _devices = new List<PairedDevice>();
        private string? _code;
        private DateTimeOffset _codeExpires;
        private int _attempts;

        public LocalPairing(string path, ISecretProtector protector, IClock clock)
        {
            _path = path;
            _protector = protector;
            _clock = clock;
            Load();
        }

        public event EventHandler? Changed;

        private static string Purpose(string deviceId) => "ErpOneCAgent/local-token/v1|" + deviceId.ToLowerInvariant();

        private void Load()
        {
            if (!File.Exists(_path)) return;
            try
            {
                _devices = AgentJson.Deserialize<List<PairedDevice>>(File.ReadAllText(_path)) ?? new List<PairedDevice>();
            }
            catch (JsonException)
            {
                _devices = new List<PairedDevice>();
            }

            foreach (var d in _devices)
            {
                try
                {
                    var token = _protector.Unprotect(Convert.FromBase64String(d.TokenProtected), Purpose(d.DeviceId));
                    _tokenHashes[d.DeviceId] = Hashing.Sha256(token);
                    Array.Clear(token, 0, token.Length);
                }
                catch (Exception e) when (e is CryptographicException || e is FormatException)
                {
                    // A blob of another Windows user / PC: that POS must pair again.
                }
            }
        }

        private void Save() => AtomicFile.WriteAllText(_path, AgentJson.Serialize(_devices));

        /// <summary>New one-time code (replaces any previous one).</summary>
        public (string Code, DateTimeOffset ExpiresAt) NewCode()
        {
            var b = new byte[4];
            using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(b);
            var n = BitConverter.ToUInt32(b, 0) % 1000000;
            lock (_lock)
            {
                _code = n.ToString("D6", CultureInfo.InvariantCulture);
                _codeExpires = _clock.UtcNow + CodeLifetime;
                _attempts = 0;
                return (_code, _codeExpires);
            }
        }

        public (string? Code, DateTimeOffset ExpiresAt) CurrentCode()
        {
            lock (_lock) return _code != null && _clock.UtcNow < _codeExpires ? (_code, _codeExpires) : (null, default);
        }

        /// <summary>Validates the code (single use) and returns the new local token.</summary>
        public string Pair(string code, string deviceId)
        {
            if (!Guid.TryParse(deviceId, out var g)) throw LocalApiException.Validation("device_id", "uuid");
            deviceId = g.ToString("D");
            string token;
            lock (_lock)
            {
                if (_code is null || _clock.UtcNow >= _codeExpires) throw new LocalApiException(LocalCodes.OtpExpired);
                if (!Hashing.FixedTimeEquals(Encoding.ASCII.GetBytes(code ?? string.Empty), Encoding.ASCII.GetBytes(_code)))
                {
                    _attempts++;
                    if (_attempts >= MaxAttempts)
                    {
                        _code = null;
                        throw new LocalApiException(LocalCodes.OtpMaxAttempts);
                    }

                    throw new LocalApiException(LocalCodes.OtpInvalid);
                }

                _code = null; // single use
                var raw = new byte[32];
                using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(raw);
                token = Base64Url.Encode(raw);
                var tokenBytes = Encoding.ASCII.GetBytes(token);
                _devices.RemoveAll(d => string.Equals(d.DeviceId, deviceId, StringComparison.OrdinalIgnoreCase));
                _devices.Add(new PairedDevice
                {
                    DeviceId = deviceId,
                    TokenProtected = Convert.ToBase64String(_protector.Protect(tokenBytes, Purpose(deviceId))),
                    PairedAt = Iso.S(_clock.UtcNow),
                });
                _tokenHashes[deviceId] = Hashing.Sha256(tokenBytes);
                Save();
            }

            Changed?.Invoke(this, EventArgs.Empty);
            return token;
        }

        /// <summary>True only when the token belongs to exactly this device id.</summary>
        public bool Validate(string? token, string? deviceId)
        {
            if (string.IsNullOrEmpty(token) || string.IsNullOrEmpty(deviceId) || !Guid.TryParse(deviceId, out var g)) return false;
            byte[]? expected;
            lock (_lock) _tokenHashes.TryGetValue(g.ToString("D"), out expected);
            if (expected is null) return false;
            return Hashing.FixedTimeEquals(expected, Hashing.Sha256(Encoding.ASCII.GetBytes(token)));
        }

        public IReadOnlyList<PairedDevice> Devices()
        {
            lock (_lock) return _devices.ToList();
        }

        /// <summary>Tray «Ulangan kassalar» → remove.</summary>
        public void Revoke(string deviceId)
        {
            lock (_lock)
            {
                _devices.RemoveAll(d => string.Equals(d.DeviceId, deviceId, StringComparison.OrdinalIgnoreCase));
                _tokenHashes.Remove(deviceId);
                Save();
            }

            Changed?.Invoke(this, EventArgs.Empty);
        }

        public void Clear()
        {
            lock (_lock)
            {
                _devices.Clear();
                _tokenHashes.Clear();
                if (File.Exists(_path)) File.Delete(_path);
            }
        }
    }
}

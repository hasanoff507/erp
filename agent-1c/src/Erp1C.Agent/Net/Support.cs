using System;
using System.Collections.Generic;
using System.Globalization;
using System.Net.Http;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using Erp1C.Core.Security;
using Microsoft.Win32;

namespace Erp1C.Agent.Net
{
    /// <summary>Network backoff 1, 2, 5, 10, 30, 60 s ±20 % (33 §9.9, 34 §7.8); each loop owns one.</summary>
    public sealed class Backoff
    {
        private static readonly int[] Steps = { 1, 2, 5, 10, 30, 60 };
        private readonly Random _rng;

        public Backoff(Random? rng = null)
        {
            _rng = rng ?? new Random();
        }

        public int Failures { get; private set; }

        public TimeSpan Next() => Delay(Failures++);

        public TimeSpan Delay(int failures)
        {
            var s = Steps[Math.Min(Math.Max(failures, 0), Steps.Length - 1)];
            double jitter;
            lock (_rng) jitter = 1.0 + ((_rng.NextDouble() * 0.4) - 0.2);
            return TimeSpan.FromSeconds(s * jitter);
        }

        /// <summary>429 with Retry-After: the larger of the two.</summary>
        public TimeSpan NextWith(TimeSpan? retryAfter)
        {
            var d = Next();
            return retryAfter.HasValue && retryAfter.Value > d ? retryAfter.Value : d;
        }

        public void Reset() => Failures = 0;
    }

    /// <summary>
    /// Server clock offset (34 §7.9): from hello <c>server_time</c> with the round-trip midpoint, before the first hello
    /// from any HTTP <c>Date</c> header. Corrected time = local UTC + offset.
    /// </summary>
    public sealed class ClockSync : IClock
    {
        public static readonly TimeSpan Tolerance = TimeSpan.FromSeconds(120);
        private readonly Func<DateTimeOffset> _local;
        private long _offsetTicks;

        public ClockSync(Func<DateTimeOffset>? local = null)
        {
            _local = local ?? (() => DateTimeOffset.UtcNow);
        }

        public TimeSpan Offset => TimeSpan.FromTicks(System.Threading.Interlocked.Read(ref _offsetTicks));

        public bool HasHelloOffset { get; private set; }

        public DateTimeOffset LocalNow => _local();

        public DateTimeOffset UtcNow => _local() + Offset;

        public bool Skewed => Offset.Duration() > Tolerance;

        /// <summary>offset = server_time − (sent + received) / 2.</summary>
        public void FromHello(DateTimeOffset serverTime, DateTimeOffset sent, DateTimeOffset received)
        {
            var mid = sent + TimeSpan.FromTicks((received - sent).Ticks / 2);
            System.Threading.Interlocked.Exchange(ref _offsetTicks, (serverTime - mid).Ticks);
            HasHelloOffset = true;
        }

        /// <summary>HTTP Date (second precision) — only until the first hello offset exists, or when forced (401 retry).</summary>
        public void FromDateHeader(DateTimeOffset? date, bool force = false)
        {
            if (date is null || (HasHelloOffset && !force)) return;
            System.Threading.Interlocked.Exchange(ref _offsetTicks, (date.Value - _local()).Ticks);
        }
    }

    /// <summary>Machine identity facts (34 §5.2, §7.1).</summary>
    public static class MachineInfo
    {
        /// <summary>hex(SHA-256(UTF8(lower(MachineGuid) + "|" + UserSid))) — 64 lower-case hex.</summary>
        public static string MachineHash(string machineGuid, string userSid)
        {
            using var sha = SHA256.Create();
            var h = sha.ComputeHash(Encoding.UTF8.GetBytes(machineGuid.ToLowerInvariant() + "|" + userSid));
            var sb = new StringBuilder(64);
            foreach (var b in h) sb.Append(b.ToString("x2", CultureInfo.InvariantCulture));
            return sb.ToString();
        }

        public static string CurrentMachineHash()
        {
            string guid;
            using (var baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, Environment.Is64BitOperatingSystem ? RegistryView.Registry64 : RegistryView.Registry32))
            using (var key = baseKey.OpenSubKey(@"SOFTWARE\Microsoft\Cryptography"))
            {
                guid = key?.GetValue("MachineGuid") as string ?? Environment.MachineName;
            }

            using var id = WindowsIdentity.GetCurrent();
            return MachineHash(guid, id.User?.Value ?? id.Name);
        }

        public static string PcName()
        {
            var n = Environment.MachineName;
            return n.Length > 64 ? n.Substring(0, 64) : n;
        }

        /// <summary>"{ProductName} {DisplayVersion} ({CurrentBuild})"; build ≥ 22000 → Windows 11.</summary>
        public static string OsVersion()
        {
            try
            {
                using var baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, Environment.Is64BitOperatingSystem ? RegistryView.Registry64 : RegistryView.Registry32);
                using var key = baseKey.OpenSubKey(@"SOFTWARE\Microsoft\Windows NT\CurrentVersion");
                var product = key?.GetValue("ProductName") as string ?? "Windows";
                var display = key?.GetValue("DisplayVersion") as string ?? key?.GetValue("ReleaseId") as string ?? string.Empty;
                var build = key?.GetValue("CurrentBuild") as string ?? Environment.OSVersion.Version.Build.ToString(CultureInfo.InvariantCulture);
                if (int.TryParse(build, NumberStyles.None, CultureInfo.InvariantCulture, out var b) && b >= 22000) product = product.Replace("Windows 10", "Windows 11");
                return (product + " " + display).Trim() + " (" + build + ")";
            }
            catch (Exception e) when (e is System.Security.SecurityException || e is UnauthorizedAccessException || e is System.IO.IOException)
            {
                return Environment.OSVersion.VersionString;
            }
        }

        public static string OsShort() => "Windows " + Environment.OSVersion.Version.Major.ToString(CultureInfo.InvariantCulture) + "." + Environment.OSVersion.Version.Minor.ToString(CultureInfo.InvariantCulture) + "." + Environment.OSVersion.Version.Build.ToString(CultureInfo.InvariantCulture);

        public static string Arch() => Environment.Is64BitOperatingSystem ? "x64" : "x86";
    }

    /// <summary>Non-2xx answer of the agent API (17 §7 envelope) or an OAuth error.</summary>
    public sealed class ApiException : Exception
    {
        public ApiException()
        {
        }

        public ApiException(string message)
            : base(message)
        {
        }

        public ApiException(string message, Exception inner)
            : base(message, inner)
        {
        }

        public ApiException(int status, string code, string? requestId = null, TimeSpan? retryAfter = null, Dictionary<string, JsonElement>? parameters = null)
            : base(status.ToString(CultureInfo.InvariantCulture) + " " + code)
        {
            Status = status;
            Code = code;
            RequestId = requestId;
            RetryAfter = retryAfter;
            Params = parameters;
        }

        public int Status { get; }

        public string Code { get; } = string.Empty;

        public string? RequestId { get; }

        public TimeSpan? RetryAfter { get; }

        public Dictionary<string, JsonElement>? Params { get; }

        public bool IsRevoked => (Status == 403 && Code == "ONEC_AGENT_REVOKED") || (Status == 401 && Code == "agent_revoked");

        public bool IsSubscriptionRestricted => Status == 403 && Code == "SUBSCRIPTION_RESTRICTED";

        public bool IsUpdateRequired => Status == 426;

        public bool IsTransient => Status >= 500 || Status == 429 || Status == 408;
    }

    /// <summary>Transport failure (DNS, TLS, timeout) — always backoff.</summary>
    public sealed class NetworkException : Exception
    {
        public NetworkException()
        {
        }

        public NetworkException(string message)
            : base(message)
        {
        }

        public NetworkException(string message, Exception inner)
            : base(message, inner)
        {
        }

        public static NetworkException From(Exception e) =>
            new NetworkException(e is HttpRequestException h && h.InnerException != null ? h.InnerException.Message : e.Message, e);
    }
}

using System;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;

namespace Erp1C.Core.Security
{
    /// <summary>Secret protection (DPAPI in production, 34 §5.1); injectable for tests.</summary>
    public interface ISecretProtector
    {
        byte[] Protect(byte[] data, string purpose);

        /// <summary>Throws <see cref="CryptographicException"/> when the blob cannot be opened (→ ONEC_DPAPI_FAILED).</summary>
        byte[] Unprotect(byte[] blob, string purpose);
    }

    /// <summary>
    /// Windows DPAPI, <c>CurrentUser</c> scope only — never <c>LocalMachine</c> (33 §15.3). The purpose string is the
    /// entropy (e.g. <c>ErpOneCAgent/agent.key/v1|&lt;machine_hash&gt;</c>). .NET sets CRYPTPROTECT_UI_FORBIDDEN.
    /// </summary>
    public sealed class DpapiProtector : ISecretProtector
    {
        public byte[] Protect(byte[] data, string purpose) =>
            ProtectedData.Protect(data, Encoding.UTF8.GetBytes(purpose), DataProtectionScope.CurrentUser);

        public byte[] Unprotect(byte[] blob, string purpose) =>
            ProtectedData.Unprotect(blob, Encoding.UTF8.GetBytes(purpose), DataProtectionScope.CurrentUser);
    }

    /// <summary>Corrected time source (34 §7.9: local UTC + server clock offset).</summary>
    public interface IClock
    {
        DateTimeOffset UtcNow { get; }
    }

    public sealed class SystemClock : IClock
    {
        public static readonly SystemClock Instance = new SystemClock();

        public DateTimeOffset UtcNow => DateTimeOffset.UtcNow;
    }

    /// <summary>
    /// Device address rules (34 §14.3/§14.4): printers and card terminals only on private LAN IPv4 addresses
    /// (RFC 1918: 10/8, 172.16/12, 192.168/16). Host names, loopback, public and IPv6 addresses are refused — the agent
    /// never connects to an arbitrary host.
    /// </summary>
    public static class PrivateLan
    {
        public static bool IsPrivateIPv4(string? host)
        {
            if (string.IsNullOrWhiteSpace(host)) return false;
            var parts = host!.Split('.');
            if (parts.Length != 4) return false;
            var b = new byte[4];
            for (var i = 0; i < 4; i++)
            {
                var p = parts[i];
                if (p.Length == 0 || p.Length > 3) return false;
                foreach (var c in p)
                {
                    if (c < '0' || c > '9') return false;
                }

                if (p.Length > 1 && p[0] == '0') return false; // no octal-looking forms
                var v = int.Parse(p, System.Globalization.CultureInfo.InvariantCulture);
                if (v > 255) return false;
                b[i] = (byte)v;
            }

            if (b[0] == 10) return true;
            if (b[0] == 172 && b[1] >= 16 && b[1] <= 31) return true;
            if (b[0] == 192 && b[1] == 168) return true;
            return false;
        }

        public static bool IsValidPort(int port) => port > 0 && port < 65536;

        public static IPAddress ParsePrivate(string host)
        {
            if (!IsPrivateIPv4(host)) throw new ArgumentException("not a private LAN IPv4 address", nameof(host));
            var ip = IPAddress.Parse(host);
            if (ip.AddressFamily != AddressFamily.InterNetwork) throw new ArgumentException("IPv4 only", nameof(host));
            return ip;
        }
    }
}

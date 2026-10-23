using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;

namespace Erp1C.Agent.App
{
    /// <summary>
    /// Build-time constants (34 §2.6, §6.8): version, protocol, channel, the server base, the POS app Origins
    /// allowed on the local API (21 §16 — <c>https://app.&lt;domen&gt;</c>), the allowed local API ports (24 §4.4)
    /// and the expected Authenticode publisher (34 §4.4 #8). Nothing here is read from settings.json.
    /// </summary>
    public static class BuildInfo
    {
        public const int Protocol = 2;
        public const string Product = "erp-onec-agent";
        public const int DefaultLocalPort = 47110;

        private static readonly Assembly Asm = typeof(BuildInfo).Assembly;

        public static string Version { get; } =
            (Asm.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion ?? "0.0.0").Split('+')[0];

        public static string Channel { get; } = Meta("AgentChannel", "dev");

        public static bool IsDev =>
#if AGENT_DEV
            true;
#else
            false;
#endif

        /// <summary>The compiled server base; a DEV build may override it with <c>--server</c>.</summary>
        public static string ServerBase { get; private set; } = Meta("AgentServerBase", "http://localhost:8000").TrimEnd('/');

        public static IReadOnlyList<string> AppOrigins { get; } =
            Meta("AgentAppOrigins", string.Empty).Split(new[] { ';', ',' }, StringSplitOptions.RemoveEmptyEntries).Select(s => s.Trim().TrimEnd('/')).ToList();

        public static IReadOnlyList<int> LocalPorts { get; } =
            Meta("AgentLocalPorts", "47110").Split(new[] { ';', ',' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(s => int.Parse(s.Trim(), CultureInfo.InvariantCulture)).ToList();

        public static string ExpectedPublisher { get; } = Meta("AgentPublisher", "ERP");

        public static string UserAgent(string osShort, string arch) =>
            "ErpOneCAgent/" + Version + " (" + osShort + "; " + arch + ")";

        internal static void OverrideServerBase(string serverBase)
        {
            if (!IsDev) throw new InvalidOperationException("--server is allowed only in a DEV build (34 §6.8)");
            ServerBase = serverBase.TrimEnd('/');
        }

        private static string Meta(string key, string fallback) =>
            Asm.GetCustomAttributes<AssemblyMetadataAttribute>().FirstOrDefault(a => a.Key == key)?.Value is string v && v.Length > 0 ? v : fallback;

        /// <summary>SemVer triple comparison (34 §2.6 — no suffixes).</summary>
        public static int CompareVersions(string a, string b)
        {
            var pa = Parse(a);
            var pb = Parse(b);
            for (var i = 0; i < 3; i++)
            {
                var c = pa[i].CompareTo(pb[i]);
                if (c != 0) return c;
            }

            return 0;
        }

        public static bool TryParseVersion(string? v, out int[] parts)
        {
            parts = new int[3];
            if (string.IsNullOrEmpty(v)) return false;
            var s = v!.Split('.');
            if (s.Length != 3) return false;
            for (var i = 0; i < 3; i++)
            {
                if (!int.TryParse(s[i], NumberStyles.None, CultureInfo.InvariantCulture, out parts[i])) return false;
            }

            return true;
        }

        private static int[] Parse(string v)
        {
            if (!TryParseVersion(v, out var p)) throw new FormatException("not a MAJOR.MINOR.PATCH version: " + v);
            return p;
        }
    }
}

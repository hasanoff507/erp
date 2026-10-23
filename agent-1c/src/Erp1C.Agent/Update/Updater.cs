using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Agent.App;
using Erp1C.Core.Contracts;
using Erp1C.Core.Crypto;
using Erp1C.Core.Json;
using Erp1C.Core.Trust;

namespace Erp1C.Agent.Update
{
    public sealed class UpdateRejectedException : Exception
    {
        public UpdateRejectedException()
        {
        }

        public UpdateRejectedException(string message)
            : base(message)
        {
            Reason = message;
        }

        public UpdateRejectedException(string message, Exception inner)
            : base(message, inner)
        {
            Reason = message;
        }

        /// <summary>signature | product | channel | version | os | protocol | url | size | sha256 | authenticode.</summary>
        public string Reason { get; } = "signature";
    }

    /// <summary>
    /// A-09 manifest checks 1–6 (34 §4.4): Ed25519 over the EXACT base64-decoded bytes with a root <c>kid</c>, product,
    /// channel, strictly newer version (no downgrade, no equal), min_os, min_protocol, https URL without userinfo.
    /// </summary>
    public static class ManifestVerifier
    {
        public static UpdateManifest Verify(UpdateManifestEnvelope env, RootKeys roots, string channel, string installedVersion, Version osVersion, int maxProtocol)
        {
            byte[] bytes;
            byte[] sig;
            try
            {
                bytes = Convert.FromBase64String(env.Manifest);
                sig = Convert.FromBase64String(env.Signature);
            }
            catch (FormatException)
            {
                throw new UpdateRejectedException("signature");
            }

            if (!roots.TryGet(env.Kid, out var root) || !Ed25519.Verify(root.X, bytes, sig)) throw new UpdateRejectedException("signature");
            UpdateManifest m;
            try
            {
                m = AgentJson.Deserialize<UpdateManifest>(bytes) ?? throw new UpdateRejectedException("signature");
            }
            catch (JsonException)
            {
                throw new UpdateRejectedException("signature");
            }

            if (m.Product != BuildInfo.Product) throw new UpdateRejectedException("product");
            if (m.Channel != channel) throw new UpdateRejectedException("channel");
            if (!BuildInfo.TryParseVersion(m.Version, out _) || BuildInfo.CompareVersions(m.Version, installedVersion) <= 0) throw new UpdateRejectedException("version");
            if (!System.Version.TryParse(m.MinOs, out var minOs) || minOs > osVersion) throw new UpdateRejectedException("os");
            if (m.MinProtocol > maxProtocol) throw new UpdateRejectedException("protocol");
            if (!Uri.TryCreate(m.Url, UriKind.Absolute, out var u) || u.Scheme != Uri.UriSchemeHttps || !string.IsNullOrEmpty(u.UserInfo)) throw new UpdateRejectedException("url");
            if (m.Size <= 0 || !System.Text.RegularExpressions.Regex.IsMatch(m.Sha256 ?? string.Empty, "^[0-9a-f]{64}$")) throw new UpdateRejectedException("sha256");
            return m;
        }
    }

    /// <summary>Check 7: streamed to <c>.part</c>, stops above <c>size</c>, exact size and SHA-256 (lower-case hex), then renamed.</summary>
    public sealed class Downloader
    {
        private readonly HttpClient _http;

        public Downloader(HttpClient http)
        {
            _http = http;
        }

        public async Task<string> DownloadAsync(UpdateManifest m, string updatesDir, CancellationToken ct)
        {
            Directory.CreateDirectory(updatesDir);
            foreach (var old in Directory.GetFiles(updatesDir).Where(f => DateTime.UtcNow - File.GetLastWriteTimeUtc(f) > TimeSpan.FromDays(1)))
            {
                File.Delete(old);
            }

            var final = Path.Combine(updatesDir, "erp-onec-agent-" + m.Version + "-setup.exe");
            var part = final + ".part";
            using (var resp = await _http.GetAsync(m.Url, HttpCompletionOption.ResponseHeadersRead, ct).ConfigureAwait(false))
            {
                if (!resp.IsSuccessStatusCode) throw new UpdateRejectedException("url");
                using var src = await resp.Content.ReadAsStreamAsync().ConfigureAwait(false);
                await WriteVerifiedAsync(src, part, m.Size, m.Sha256, ct).ConfigureAwait(false);
            }

            if (File.Exists(final)) File.Delete(final);
            File.Move(part, final);
            return final;
        }

        public static async Task WriteVerifiedAsync(Stream src, string partPath, long size, string sha256, CancellationToken ct)
        {
            using var sha = SHA256.Create();
            long total = 0;
            using (var dst = new FileStream(partPath, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                var buf = new byte[81920];
                int n;
                while ((n = await src.ReadAsync(buf, 0, buf.Length, ct).ConfigureAwait(false)) > 0)
                {
                    total += n;
                    if (total > size)
                    {
                        dst.Dispose();
                        File.Delete(partPath);
                        throw new UpdateRejectedException("size");
                    }

                    sha.TransformBlock(buf, 0, n, null, 0);
                    await dst.WriteAsync(buf, 0, n, ct).ConfigureAwait(false);
                }

                sha.TransformFinalBlock(Array.Empty<byte>(), 0, 0);
                await dst.FlushAsync(ct).ConfigureAwait(false);
            }

            if (total != size)
            {
                File.Delete(partPath);
                throw new UpdateRejectedException("size");
            }

            if (Hashing.Hex(sha.Hash!) != sha256)
            {
                File.Delete(partPath);
                throw new UpdateRejectedException("sha256");
            }
        }
    }

    /// <summary>Check 8 (Authenticode) seam — the real check needs a signed setup (26 #105).</summary>
    public interface IAuthenticodeCheck
    {
        /// <summary>True when the file has a valid Authenticode signature whose signer CN equals <paramref name="expectedPublisher"/>.</summary>
        bool IsTrusted(string path, string expectedPublisher);
    }

    /// <summary><c>WinVerifyTrust(WINTRUST_ACTION_GENERIC_VERIFY_V2)</c> + signer certificate CN (34 §4.4 #8).</summary>
    public sealed class WinTrustAuthenticodeCheck : IAuthenticodeCheck
    {
        public bool IsTrusted(string path, string expectedPublisher)
        {
            if (!NativeMethods.Verify(path)) return false;
            try
            {
#pragma warning disable SYSLIB0057
                using var cert = new X509Certificate2(X509Certificate.CreateFromSignedFile(path));
#pragma warning restore SYSLIB0057
                var cn = cert.GetNameInfo(X509NameType.SimpleName, false);
                return string.Equals(cn, expectedPublisher, StringComparison.Ordinal);
            }
            catch (CryptographicException)
            {
                return false;
            }
        }

        private static class NativeMethods
        {
            private static readonly Guid GenericVerifyV2 = new Guid("00AAC56B-CD44-11d0-8CC2-00C04FC295EE");

            [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
            private struct WintrustFileInfo
            {
                public uint CbStruct;
                [MarshalAs(UnmanagedType.LPWStr)]
                public string FilePath;
                public IntPtr HFile;
                public IntPtr PgKnownSubject;
            }

            [StructLayout(LayoutKind.Sequential)]
            private struct WintrustData
            {
                public uint CbStruct;
                public IntPtr PolicyCallbackData;
                public IntPtr SipClientData;
                public uint UiChoice;
                public uint RevocationChecks;
                public uint UnionChoice;
                public IntPtr FileInfo;
                public uint StateAction;
                public IntPtr StateData;
                public IntPtr UrlReference;
                public uint ProvFlags;
                public uint UiContext;
                public IntPtr SignatureSettings;
            }

            [DllImport("wintrust.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
            [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
            private static extern int WinVerifyTrust(IntPtr hwnd, [MarshalAs(UnmanagedType.LPStruct)] Guid action, ref WintrustData data);

            public static bool Verify(string path)
            {
                var fi = new WintrustFileInfo { CbStruct = (uint)Marshal.SizeOf<WintrustFileInfo>(), FilePath = path };
                var fiPtr = Marshal.AllocHGlobal(Marshal.SizeOf<WintrustFileInfo>());
                try
                {
                    Marshal.StructureToPtr(fi, fiPtr, false);
                    var data = new WintrustData
                    {
                        CbStruct = (uint)Marshal.SizeOf<WintrustData>(),
                        UiChoice = 2, // WTD_UI_NONE
                        RevocationChecks = 0,
                        UnionChoice = 1, // WTD_CHOICE_FILE
                        FileInfo = fiPtr,
                        StateAction = 0,
                        ProvFlags = 0x00000080, // WTD_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT
                    };
                    return WinVerifyTrust(new IntPtr(-1), GenericVerifyV2, ref data) == 0;
                }
                finally
                {
                    Marshal.FreeHGlobal(fiPtr);
                }
            }
        }
    }

    /// <summary>Starts the verified setup silently and asks the agent to exit (34 §4.4 install sequence).</summary>
    public static class SetupLauncher
    {
        public static void Launch(string setupPath, bool hidden)
        {
            var args = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /restart" + (hidden ? " /hidden" : string.Empty);
            try
            {
                using var p = Process.Start(new ProcessStartInfo(setupPath, args) { UseShellExecute = false });
            }
            catch (Win32Exception e)
            {
                throw new UpdateRejectedException("authenticode", e);
            }
        }

        public static Version CurrentOsVersion()
        {
            var v = Environment.OSVersion.Version;
            return new Version(v.Major, v.Minor, v.Build);
        }

        public static string Describe(UpdateManifest m) =>
            m.Version + " (" + m.Channel + ", " + m.Size.ToString(CultureInfo.InvariantCulture) + " B)";
    }
}

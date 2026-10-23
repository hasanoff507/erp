using System;
using System.IO;
using System.Text.Json;
using Erp1C.Core.Security;

namespace Erp1C.Tests.Common
{
    /// <summary>Locates repo files (shared/agent vectors) from the test output folder.</summary>
    internal static class Repo
    {
        public static string Root
        {
            get
            {
                var dir = new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory);
                while (dir != null)
                {
                    if (Directory.Exists(Path.Combine(dir.FullName, "shared", "agent")) && Directory.Exists(Path.Combine(dir.FullName, "agent-1c"))) return dir.FullName;
                    dir = dir.Parent;
                }

                throw new DirectoryNotFoundException("repo root with shared/agent not found");
            }
        }

        public static string Vector(string name) => Path.Combine(Root, "shared", "agent", name);

        public static JsonElement LoadVector(string name)
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(Vector(name)));
            return doc.RootElement.Clone();
        }
    }

    internal sealed class TempDir : IDisposable
    {
        public TempDir()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "erp1c-test-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public string File(string name) => System.IO.Path.Combine(Path, name);

        public void Dispose()
        {
            try
            {
                Directory.Delete(Path, true);
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
    }

    internal sealed class FakeClock : IClock
    {
        public FakeClock(DateTimeOffset now)
        {
            UtcNow = now;
        }

        public DateTimeOffset UtcNow { get; set; }

        public void Advance(TimeSpan by) => UtcNow += by;
    }

    /// <summary>Reversible non-DPAPI protector for tests that do not test DPAPI itself.</summary>
    internal sealed class XorProtector : ISecretProtector
    {
        public byte[] Protect(byte[] data, string purpose)
        {
            var p = System.Text.Encoding.UTF8.GetBytes(purpose);
            var r = new byte[data.Length];
            for (var i = 0; i < data.Length; i++) r[i] = (byte)(data[i] ^ p[i % p.Length]);
            return r;
        }

        public byte[] Unprotect(byte[] blob, string purpose) => Protect(blob, purpose);
    }
}

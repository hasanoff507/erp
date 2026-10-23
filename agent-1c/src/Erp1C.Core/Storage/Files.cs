using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace Erp1C.Core.Storage
{
    /// <summary>Atomic file replace: write <c>.tmp</c>, flush to disk, then <c>File.Replace</c> (34 §3.2 SettingsStore).</summary>
    public static class AtomicFile
    {
        private static readonly UTF8Encoding Utf8NoBom = new UTF8Encoding(false);

        public static void WriteAllText(string path, string content) => WriteAllBytes(path, Utf8NoBom.GetBytes(content));

        public static void WriteAllBytes(string path, byte[] content)
        {
            var dir = Path.GetDirectoryName(Path.GetFullPath(path));
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            var tmp = path + ".tmp";
            using (var fs = new FileStream(tmp, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                fs.Write(content, 0, content.Length);
                fs.Flush(true);
            }

            if (File.Exists(path))
            {
                File.Replace(tmp, path, null, true);
            }
            else
            {
                File.Move(tmp, path);
            }
        }
    }

    /// <summary>
    /// Append-only JSON-lines file with fsync per line (journals, outboxes — 34 §7.7, §8.14). A torn last line (crash
    /// in the middle of a write) is skipped on read.
    /// </summary>
    public sealed class JsonlFile
    {
        private static readonly UTF8Encoding Utf8NoBom = new UTF8Encoding(false);
        private readonly object _lock = new object();

        public JsonlFile(string path)
        {
            Path = path;
        }

        public string Path { get; }

        public void Append(string jsonLine)
        {
            if (jsonLine is null) throw new ArgumentNullException(nameof(jsonLine));
            if (jsonLine.IndexOf('\n') >= 0) throw new ArgumentException("a JSON line must not contain newlines", nameof(jsonLine));
            lock (_lock)
            {
                var dir = System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(Path));
                if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
                var bytes = Utf8NoBom.GetBytes(jsonLine + "\n");
                using var fs = new FileStream(Path, FileMode.Append, FileAccess.Write, FileShare.Read);

                // A previous crash may have left a line without its newline — start on a fresh line.
                if (fs.Length > 0 && !EndsWithNewline())
                {
                    fs.WriteByte((byte)'\n');
                }

                fs.Write(bytes, 0, bytes.Length);
                fs.Flush(true);
            }
        }

        private bool EndsWithNewline()
        {
            using var r = new FileStream(Path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
            if (r.Length == 0) return true;
            r.Seek(-1, SeekOrigin.End);
            return r.ReadByte() == '\n';
        }

        /// <summary>Complete lines only (a trailing line without <c>\n</c> is a torn write and is ignored).</summary>
        public IReadOnlyList<string> ReadLines()
        {
            lock (_lock)
            {
                if (!File.Exists(Path)) return Array.Empty<string>();
                string text;
                using (var fs = new FileStream(Path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                using (var sr = new StreamReader(fs, Utf8NoBom))
                {
                    text = sr.ReadToEnd();
                }

                var lines = new List<string>();
                var start = 0;
                for (var i = 0; i < text.Length; i++)
                {
                    if (text[i] != '\n') continue;
                    var line = text.Substring(start, i - start).TrimEnd('\r');
                    if (line.Length > 0) lines.Add(line);
                    start = i + 1;
                }

                return lines;
            }
        }

        /// <summary>Atomically rewrites the file with the given lines (used to delete delivered outbox rows).</summary>
        public void Rewrite(IEnumerable<string> lines)
        {
            lock (_lock)
            {
                var sb = new StringBuilder();
                foreach (var l in lines) sb.Append(l).Append('\n');
                AtomicFile.WriteAllText(Path, sb.ToString());
            }
        }

        public long SizeBytes()
        {
            lock (_lock)
            {
                return File.Exists(Path) ? new FileInfo(Path).Length : 0;
            }
        }
    }
}

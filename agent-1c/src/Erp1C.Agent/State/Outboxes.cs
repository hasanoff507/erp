using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text.Json;
using Erp1C.Core.Contracts;
using Erp1C.Core.Json;
using Erp1C.Core.Security;
using Erp1C.Core.Storage;

#pragma warning disable CA2227

namespace Erp1C.Agent.State
{
    internal static class Iso
    {
        public static string Ms(DateTimeOffset t) => t.UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ss.fffZ", CultureInfo.InvariantCulture);

        public static string S(DateTimeOffset t) => t.UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture);
    }

    public sealed class OutboxEntry
    {
        public int V { get; set; } = 1;

        public string TaskId { get; set; } = string.Empty;

        public string LeaseId { get; set; } = string.Empty;

        public int Attempt { get; set; }

        public string QueuedAt { get; set; } = string.Empty;

        public int Tries { get; set; }

        public bool Truncated { get; set; }

        public ResultBody Body { get; set; } = new ResultBody();
    }

    /// <summary>
    /// <c>results.jsonl</c> (34 §7.7): every A-05 result is written to disk (fsync) BEFORE it goes to the network and
    /// is removed only after the server answered (200, or a terminal 404/409/422).
    /// </summary>
    public sealed class ResultOutbox
    {
        private readonly JsonlFile _file;
        private readonly object _lock = new object();

        public ResultOutbox(string path)
        {
            _file = new JsonlFile(path);
        }

        public event EventHandler? Enqueued;

        public void Enqueue(OutboxEntry e)
        {
            lock (_lock) _file.Append(AgentJson.Serialize(e));
            Enqueued?.Invoke(this, EventArgs.Empty);
        }

        public IReadOnlyList<OutboxEntry> Pending()
        {
            lock (_lock)
            {
                var list = new List<OutboxEntry>();
                foreach (var line in _file.ReadLines())
                {
                    try
                    {
                        var e = AgentJson.Deserialize<OutboxEntry>(line);
                        if (e != null) list.Add(e);
                    }
                    catch (JsonException)
                    {
                        // A torn line cannot be resent; the journal still has the result (34 §8.14).
                    }
                }

                return list;
            }
        }

        public int Count => Pending().Count;

        public void Remove(string taskId, string leaseId) => Rewrite(e => !(e.TaskId == taskId && e.LeaseId == leaseId), null);

        public void Replace(OutboxEntry updated) =>
            Rewrite(_ => true, e => e.TaskId == updated.TaskId && e.LeaseId == updated.LeaseId ? updated : e);

        private void Rewrite(Func<OutboxEntry, bool> keep, Func<OutboxEntry, OutboxEntry>? map)
        {
            lock (_lock)
            {
                var kept = Pending().Where(keep).Select(e => map is null ? e : map(e)).Select(e => AgentJson.Serialize(e)).ToList();
                _file.Rewrite(kept);
            }
        }
    }

    public sealed class ActionLine
    {
        public int V { get; set; } = 1;

        /// <summary>started | finished | delivered | cancelled.</summary>
        public string E { get; set; } = string.Empty;

        public string At { get; set; } = string.Empty;

        public string TaskId { get; set; } = string.Empty;

        public int Attempt { get; set; }

        public string? LeaseId { get; set; }

        public string? Kind { get; set; }

        public bool IsWrite { get; set; }

        public string? PayloadSha256 { get; set; }

        public string? Outcome { get; set; }

        public string? ErrorCode { get; set; }

        public bool ResultStored { get; set; }

        public ResultBody? Result { get; set; }

        public string? Reason { get; set; }
    }

    /// <summary>
    /// <c>actions.jsonl</c> (34 §8.14): append-only trace of every task attempt. A finished <c>(task_id, attempt)</c> is
    /// answered from here without touching the device again (33 §9.11 #6); a started-but-unfinished one is turned
    /// into an outbox result at start-up.
    /// </summary>
    public sealed class ActionJournal
    {
        public const int MaxStoredResultBytes = 64 * 1024;
        private readonly JsonlFile _file;
        private readonly IClock _clock;
        private readonly object _lock = new object();
        private readonly Dictionary<string, ActionLine> _started = new Dictionary<string, ActionLine>(StringComparer.Ordinal);
        private readonly Dictionary<string, ActionLine> _finished = new Dictionary<string, ActionLine>(StringComparer.Ordinal);

        public ActionJournal(string path, IClock clock)
        {
            _file = new JsonlFile(path);
            _clock = clock;
            foreach (var l in _file.ReadLines())
            {
                ActionLine? a;
                try
                {
                    a = AgentJson.Deserialize<ActionLine>(l);
                }
                catch (JsonException)
                {
                    continue;
                }

                if (a is null) continue;
                var k = Key(a.TaskId, a.Attempt);
                if (a.E == "started") _started[k] = a;
                if (a.E == "finished" || a.E == "cancelled") _finished[k] = a;
            }
        }

        public string Path => _file.Path;

        private static string Key(string taskId, int attempt) => taskId.ToLowerInvariant() + "#" + attempt.ToString(CultureInfo.InvariantCulture);

        private void Append(ActionLine a)
        {
            a.At = Iso.Ms(_clock.UtcNow);
            _file.Append(AgentJson.Serialize(a));
        }

        public void Started(string taskId, int attempt, string leaseId, string kind, string payloadSha256)
        {
            lock (_lock)
            {
                var a = new ActionLine { E = "started", TaskId = taskId, Attempt = attempt, LeaseId = leaseId, Kind = kind, IsWrite = false, PayloadSha256 = payloadSha256 };
                Append(a);
                _started[Key(taskId, attempt)] = a;
            }
        }

        public void Finished(string taskId, int attempt, ResultBody body)
        {
            lock (_lock)
            {
                var size = AgentJson.SerializeUtf8(body).Length;
                var stored = size <= MaxStoredResultBytes;
                var a = new ActionLine
                {
                    E = "finished",
                    TaskId = taskId,
                    Attempt = attempt,
                    Outcome = body.Outcome,
                    ErrorCode = body.Error?.Code,
                    ResultStored = stored,
                    Result = stored ? body : null,
                };
                Append(a);
                _finished[Key(taskId, attempt)] = a;
            }
        }

        public void Delivered(string taskId, int attempt)
        {
            lock (_lock) Append(new ActionLine { E = "delivered", TaskId = taskId, Attempt = attempt });
        }

        public void Cancelled(string taskId, int attempt, string reason)
        {
            lock (_lock)
            {
                var a = new ActionLine { E = "cancelled", TaskId = taskId, Attempt = attempt, Reason = reason };
                Append(a);
                _finished[Key(taskId, attempt)] = a;
            }
        }

        /// <summary>Rule 6: the stored result of a finished attempt (null when not finished or not stored).</summary>
        public ResultBody? FinishedResult(string taskId, int attempt)
        {
            lock (_lock) return _finished.TryGetValue(Key(taskId, attempt), out var a) && a.E == "finished" && a.ResultStored ? a.Result : null;
        }

        public bool IsFinished(string taskId, int attempt)
        {
            lock (_lock) return _finished.ContainsKey(Key(taskId, attempt));
        }

        /// <summary>Started attempts without a finished/cancelled line (start-up recovery, 34 §7.3 #5).</summary>
        public IReadOnlyList<ActionLine> Unfinished()
        {
            lock (_lock) return _started.Where(kv => !_finished.ContainsKey(kv.Key)).Select(kv => kv.Value).ToList();
        }
    }

    /// <summary>
    /// <c>logs-outbox.jsonl</c> (34 §9.3): masked log entries for A-06; at most 10 000 entries — when full, the oldest
    /// info goes first, then warn; error last.
    /// </summary>
    public sealed class LogOutbox
    {
        public const int MaxEntries = 10000;
        private readonly JsonlFile _file;
        private readonly object _lock = new object();
        private int _count = -1;

        public LogOutbox(string path)
        {
            _file = new JsonlFile(path);
        }

        public void Add(LogEntry e)
        {
            lock (_lock)
            {
                if (_count < 0) _count = _file.ReadLines().Count;
                _file.Append(AgentJson.Serialize(e));
                _count++;
                if (_count > MaxEntries) Trim();
            }
        }

        private void Trim()
        {
            var all = Read();
            foreach (var level in new[] { "debug", "info", "warn", "error" })
            {
                while (all.Count > MaxEntries)
                {
                    var idx = all.FindIndex(x => x.Level == level);
                    if (idx < 0) break;
                    all.RemoveAt(idx);
                }
            }

            _file.Rewrite(all.Select(x => AgentJson.Serialize(x)));
            _count = all.Count;
        }

        private List<LogEntry> Read()
        {
            var list = new List<LogEntry>();
            foreach (var l in _file.ReadLines())
            {
                try
                {
                    var e = AgentJson.Deserialize<LogEntry>(l);
                    if (e != null) list.Add(e);
                }
                catch (JsonException)
                {
                }
            }

            return list;
        }

        public IReadOnlyList<LogEntry> Take(int max)
        {
            lock (_lock) return Read().Take(max).ToList();
        }

        public int Count
        {
            get
            {
                lock (_lock) return Read().Count;
            }
        }

        public void Remove(IEnumerable<string> clientLogIds)
        {
            var ids = new HashSet<string>(clientLogIds, StringComparer.Ordinal);
            lock (_lock)
            {
                var kept = Read().Where(x => !ids.Contains(x.ClientLogId)).ToList();
                _file.Rewrite(kept.Select(x => AgentJson.Serialize(x)));
                _count = kept.Count;
            }
        }
    }
}

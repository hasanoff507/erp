using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Erp1C.Agent.State;
using Erp1C.Core.Contracts;
using Erp1C.Core.Hosting;
using Erp1C.Core.Json;
using Erp1C.Core.Masking;
using Erp1C.Core.Security;
using Serilog;
using Serilog.Core;
using Serilog.Events;
using Serilog.Formatting.Compact;

namespace Erp1C.Agent.App
{
    /// <summary>
    /// The agent log (34 §9.1–§9.3): every message and string property is masked (34 §9.2) BEFORE it reaches the
    /// rolling CLEF file (<c>logs\agent-YYYYMMDD.clef</c>, 10 MB × 20) or the A-06 outbox (info and above).
    /// </summary>
    public sealed class AgentLogger : IAgentLogger, IDisposable
    {
        private readonly Logger? _file;
        private readonly LogOutbox? _outbox;
        private readonly IClock _clock;
        private readonly LoggingLevelSwitch _level = new LoggingLevelSwitch(LogEventLevel.Information);

        public AgentLogger(string? logsDir, LogOutbox? outbox, IClock clock)
        {
            _outbox = outbox;
            _clock = clock;
            if (logsDir != null)
            {
                Directory.CreateDirectory(logsDir);
                PruneOld(logsDir, TimeSpan.FromDays(30));
                _file = new LoggerConfiguration()
                    .MinimumLevel.ControlledBy(_level)
                    .Enrich.WithProperty("agent_version", BuildInfo.Version)
                    .WriteTo.File(
                        new CompactJsonFormatter(),
                        Path.Combine(logsDir, "agent-.clef"),
                        rollingInterval: RollingInterval.Day,
                        fileSizeLimitBytes: 10_000_000,
                        rollOnFileSizeLimit: true,
                        retainedFileCountLimit: 20)
                    .CreateLogger();
            }
        }

        /// <summary><c>hello.log_level</c>: debug | info | warn | error.</summary>
        public void SetLevel(string? level)
        {
            _level.MinimumLevel = level switch
            {
                "debug" => LogEventLevel.Debug,
                "warn" => LogEventLevel.Warning,
                "error" => LogEventLevel.Error,
                _ => LogEventLevel.Information,
            };
        }

        public void Log(string level, string? code, string message, IReadOnlyDictionary<string, object?>? context = null)
        {
            var masked = SecretMasker.Mask(message);
            var ctx = context?.ToDictionary(kv => kv.Key, kv => kv.Value is string s ? SecretMasker.Mask(s) : kv.Value);
            if (_file != null)
            {
                var lvl = level switch { "debug" => LogEventLevel.Debug, "warn" => LogEventLevel.Warning, "error" => LogEventLevel.Error, _ => LogEventLevel.Information };
                var log = _file.ForContext("code", code);
                if (ctx != null) foreach (var kv in ctx) log = log.ForContext(kv.Key, kv.Value);
                log.Write(lvl, "{Message:l}", masked);
            }

            if (_outbox != null && Rank(level) >= Math.Max(1, (int)_level.MinimumLevel - 1))
            {
                _outbox.Add(new LogEntry
                {
                    ClientLogId = Guid.NewGuid().ToString("D"),
                    At = Iso.Ms(_clock.UtcNow),
                    Level = level,
                    Code = code,
                    Message = masked.Length > 4000 ? masked.Substring(0, 4000) : masked,
                    TaskId = ctx != null && ctx.TryGetValue("task_id", out var t) ? t as string : null,
                    Context = ctx?.Where(kv => kv.Key != "task_id").ToDictionary(kv => kv.Key, kv => AgentJson.ToElement(kv.Value)),
                });
            }
        }

        /// <summary>debug 0, info 1, warn 2, error 3 (Serilog levels Debug=1 … Error=4 minus one).</summary>
        private static int Rank(string level) => level switch { "debug" => 0, "warn" => 2, "error" => 3, _ => 1 };

        private static void PruneOld(string dir, TimeSpan age)
        {
            foreach (var f in Directory.GetFiles(dir, "*.clef"))
            {
                try
                {
                    if (DateTime.UtcNow - File.GetLastWriteTimeUtc(f) > age) File.Delete(f);
                }
                catch (IOException)
                {
                }
                catch (UnauthorizedAccessException)
                {
                }
            }
        }

        public void Dispose() => _file?.Dispose();
    }
}

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Agent.App;
using Erp1C.Agent.Net;
using Erp1C.Agent.State;
using Erp1C.Core.Contracts;
using Erp1C.Core.Errors;
using Erp1C.Core.Hosting;
using Erp1C.Core.Json;
using Erp1C.Core.Masking;
using Erp1C.Core.Security;

namespace Erp1C.Agent.Tasks
{
    /// <summary>
    /// Diagnostics package (34 §9.4) — <c>collect_diagnostics</c> task (upload A-07, result <c>{attachment_id}</c>) and
    /// the tray «Diagnostika paketini saqlash». Never contains agent.key, DPAPI blobs, tokens or local pairs; every
    /// text file is masked again.
    /// </summary>
    public sealed class DiagnosticsOp : IAgentTaskHandler
    {
        public const long MaxZipBytes = 20 * 1024 * 1024;
        private static readonly string[] KindList = { "collect_diagnostics" };
        private static readonly StrictObject Schema = new StrictObject()
            .Optional("include_logs_days", e => e.ValueKind == JsonValueKind.Number && e.TryGetInt32(out var d) && d >= 1 && d <= 7)
            .Optional("include_settings", e => e.ValueKind == JsonValueKind.True || e.ValueKind == JsonValueKind.False);

        private readonly AgentPaths _paths;
        private readonly SettingsStore _settings;
        private readonly ResultOutbox _outbox;
        private readonly LogOutbox _logs;
        private readonly IClock _clock;
        private readonly Func<string, string, CancellationToken, Task<string?>>? _upload;

        public DiagnosticsOp(AgentPaths paths, SettingsStore settings, ResultOutbox outbox, LogOutbox logs, IClock clock, Func<string, string, CancellationToken, Task<string?>>? upload)
        {
            _paths = paths;
            _settings = settings;
            _outbox = outbox;
            _logs = logs;
            _clock = clock;
            _upload = upload;
        }

        public IReadOnlyCollection<string> Kinds => KindList;

        public string? ValidatePayload(string kind, JsonElement payload) => Schema.Validate(payload);

        public async Task<TaskExecution> ExecuteAsync(TaskContext context, JsonElement payload, CancellationToken ct)
        {
            var days = payload.TryGetProperty("include_logs_days", out var d) ? d.GetInt32() : 3;
            var settings = !payload.TryGetProperty("include_settings", out var s) || s.ValueKind == JsonValueKind.True;
            context.Progress("uploading", 10);
            var zip = Build(_paths.Diag, days, settings);
            try
            {
                if (_upload is null) return TaskExecution.Failed(AgentCodes.WorkerCrashed, "upload not available", true);
                var id = await _upload(context.TaskId, zip, ct).ConfigureAwait(false);
                return TaskExecution.Done(new { attachment_id = id });
            }
            catch (ApiException e)
            {
                return TaskExecution.Failed(e.Code, "diagnostics upload failed", e.IsTransient);
            }
            catch (NetworkException)
            {
                return TaskExecution.Failed(AgentCodes.WorkerCrashed, "diagnostics upload failed (network)", true);
            }
            finally
            {
                try
                {
                    File.Delete(zip);
                }
                catch (IOException)
                {
                }
            }
        }

        public string Build(string dir, int logDays, bool includeSettings)
        {
            Directory.CreateDirectory(dir);
            var name = "erp-onec-agent-diag-" + MachineInfo.PcName() + "-" + _clock.UtcNow.UtcDateTime.ToString("yyyyMMddHHmm", CultureInfo.InvariantCulture) + ".zip";
            var path = Path.Combine(dir, name);
            if (File.Exists(path)) File.Delete(path);
            using (var zip = ZipFile.Open(path, ZipArchiveMode.Create))
            {
                if (Directory.Exists(_paths.Logs))
                {
                    var cutoff = DateTime.UtcNow.AddDays(-logDays);
                    foreach (var f in Directory.GetFiles(_paths.Logs, "*.clef").Where(f => File.GetLastWriteTimeUtc(f) >= cutoff))
                    {
                        AddText(zip, "logs/" + Path.GetFileName(f), ReadShared(f));
                    }
                }

                if (includeSettings) AddText(zip, "settings.redacted.json", _settings.Redacted());
                if (File.Exists(_paths.Actions)) AddText(zip, "actions.jsonl", ReadShared(_paths.Actions));
                AddText(zip, "outbox.json", AgentJson.Serialize(new { results_pending = _outbox.Count, logs_pending = _logs.Count }));
                AddText(zip, "env.json", AgentJson.Serialize(new
                {
                    os_version = MachineInfo.OsVersion(),
                    bitness = Environment.Is64BitProcess ? 64 : 32,
                    clr = Environment.Version.ToString(),
                    culture = CultureInfo.CurrentCulture.Name,
                    ui_culture = CultureInfo.CurrentUICulture.Name,
                    time_zone = TimeZoneInfo.Local.Id,
                    clock_offset_ms = (long)(_clock.UtcNow - DateTimeOffset.UtcNow).TotalMilliseconds,
                    agent_version = BuildInfo.Version,
                    channel = BuildInfo.Channel,
                }));
            }

            if (new FileInfo(path).Length > MaxZipBytes)
            {
                File.Delete(path);
                return Build(dir, Math.Max(1, logDays - 1), includeSettings);
            }

            return path;
        }

        private static string ReadShared(string f)
        {
            using var fs = new FileStream(f, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
            using var sr = new StreamReader(fs, Encoding.UTF8);
            return sr.ReadToEnd();
        }

        private static void AddText(ZipArchive zip, string entry, string text)
        {
            var e = zip.CreateEntry(entry, CompressionLevel.Optimal);
            using var w = new StreamWriter(e.Open(), new UTF8Encoding(false));
            w.Write(SecretMasker.Mask(text));
        }
    }
}

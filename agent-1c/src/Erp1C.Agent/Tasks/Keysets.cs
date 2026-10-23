using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Agent.App;
using Erp1C.Agent.State;
using Erp1C.Core.Hosting;
using Erp1C.Core.Security;
using Erp1C.Core.Trust;

namespace Erp1C.Agent.Tasks
{
    /// <summary>
    /// Holds the verified task keyset (34 §5.5): sources — device grant, <c>hello.task_keyset</c>, A-08. Stored as
    /// <c>settings.keyset = {version, jws}</c> and re-verified at every start; the version never goes down.
    /// </summary>
    public sealed class KeysetManager : ITaskKeyProvider
    {
        private readonly RootKeys _roots;
        private readonly SettingsStore _settings;
        private readonly IClock _clock;
        private readonly IAgentLogger _log;
        private TaskKeyset? _current;

        public KeysetManager(RootKeys roots, SettingsStore settings, IClock clock, IAgentLogger log)
        {
            _roots = roots;
            _settings = settings;
            _clock = clock;
            _log = log;
            var stored = settings.Current.Keyset;
            if (stored != null && !string.IsNullOrEmpty(stored.Jws))
            {
                try
                {
                    _current = TaskKeyset.Verify(stored.Jws, roots, clock.UtcNow, 0);
                }
                catch (KeysetException e)
                {
                    _log.Error("agent.keyset.rejected", "stored task keyset rejected: " + e.Reason);
                }
            }
        }

        /// <summary>A-08 fetch (set by the runtime once the API client exists).</summary>
        public Func<CancellationToken, Task<string?>>? Fetch { get; set; }

        public TaskKeyset? Current => _current;

        public int Version => _current?.Version ?? 0;

        /// <summary>Verifies and stores a keyset; false (and logged) when rejected or older than the stored one.</summary>
        public bool Accept(string? jws)
        {
            if (string.IsNullOrEmpty(jws)) return false;
            try
            {
                var ks = TaskKeyset.Verify(jws!, _roots, _clock.UtcNow, Version);
                _current = ks;
                _settings.Update(s => s.Keyset = new KeysetRef { Version = ks.Version, Jws = ks.Jws });
                return true;
            }
            catch (KeysetException e)
            {
                _log.Error("agent.keyset.rejected", "task keyset rejected: " + e.Reason);
                return false;
            }
        }

        public async Task<TaskKeyset?> RefreshAsync(CancellationToken ct)
        {
            if (Fetch is null) return _current;
            try
            {
                var jws = await Fetch(ct).ConfigureAwait(false);
                Accept(jws);
            }
            catch (Exception e) when (!(e is OperationCanceledException))
            {
                _log.Warn("agent.keyset.refresh_failed", "A-08 task-keys failed: " + e.GetType().Name);
            }

            return _current;
        }

        public void Clear() => _current = null;

        /// <summary>Embedded roots + (DEV build only) <c>dev-root-keys.json</c> <c>[{"kid","x"}]</c>.</summary>
        public static RootKeys LoadRoots(string devRootKeysPath)
        {
            var keys = new List<TrustKey>(RootKeys.Embedded);
            if (BuildInfo.IsDev && File.Exists(devRootKeysPath))
            {
                using var doc = JsonDocument.Parse(File.ReadAllText(devRootKeysPath));
                foreach (var k in doc.RootElement.EnumerateArray())
                {
                    keys.Add(TrustKey.FromBase64Url(k.GetProperty("kid").GetString()!, k.GetProperty("x").GetString()!));
                }
            }

            return new RootKeys(keys);
        }
    }
}

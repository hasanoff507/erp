using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;
using Erp1C.CardTerminal;
using Erp1C.Core.Json;
using Erp1C.Core.Storage;
using Erp1C.Devices;
using Erp1C.Fiscal;

#pragma warning disable CA2227
#pragma warning disable CA1002

namespace Erp1C.Agent.State
{
    /// <summary>Data folder <c>%LOCALAPPDATA%\ErpOneCAgent\</c> (not roaming — 34 §4.1) and its files.</summary>
    public sealed class AgentPaths
    {
        public AgentPaths(string? root = null)
        {
            Root = root ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ErpOneCAgent");
        }

        public string Root { get; }

        public string Settings => Path.Combine(Root, "settings.json");

        public string AgentKey => Path.Combine(Root, "agent.key");

        public string Results => Path.Combine(Root, "results.jsonl");

        public string Actions => Path.Combine(Root, "actions.jsonl");

        public string LogsOutbox => Path.Combine(Root, "logs-outbox.jsonl");

        public string LocalPairs => Path.Combine(Root, "local-pairs.json");

        public string CardJournal => Path.Combine(Root, "card_journal.jsonl");

        public string FiscalJournal => Path.Combine(Root, "fiscal_journal.jsonl");

        public string FakeFm => Path.Combine(Root, "fake-fm.json");

        public string Logs => Path.Combine(Root, "logs");

        public string Updates => Path.Combine(Root, "updates");

        public string Diag => Path.Combine(Root, "diag");

        public string DevRootKeys => Path.Combine(Root, "dev-root-keys.json");

        public void Ensure()
        {
            Directory.CreateDirectory(Root);
            Directory.CreateDirectory(Logs);
        }
    }

    public sealed class KeysetRef
    {
        public int Version { get; set; }

        public string Jws { get; set; } = string.Empty;
    }

    public sealed class LocalApiSettings
    {
        /// <summary>Only a value from the compiled port list (BuildInfo.LocalPorts) is used (24 §4.4).</summary>
        public int Port { get; set; } = 47110;

        /// <summary>DEV build only: extra Origins such as <c>http://localhost:5173</c> (21 §16).</summary>
        public List<string> DevOrigins { get; set; } = new List<string>();
    }

    public sealed class DeviceSettings
    {
        public List<PrinterConfig> Printers { get; set; } = new List<PrinterConfig>();

        public List<TerminalConfig> CardTerminals { get; set; } = new List<TerminalConfig>();

        public List<FiscalDeviceConfig> Fiscal { get; set; } = new List<FiscalDeviceConfig>();
    }

    /// <summary>settings.json (34 §6.8, store-agent part). Secrets live only as DPAPI blobs elsewhere.</summary>
    public sealed class AgentSettings
    {
        public int V { get; set; } = 1;

        public string? AgentId { get; set; }

        public string? AgentClientId { get; set; }

        public string? TenantName { get; set; }

        public string? PairedAt { get; set; }

        public string UpdateChannel { get; set; } = "stable";

        public string UiLanguage { get; set; } = "uz";

        public KeysetRef? Keyset { get; set; }

        public LocalApiSettings LocalApi { get; set; } = new LocalApiSettings();

        /// <summary>Demo-tenant agent: the fake fiscal bridge / fake card driver may be announced (34 §14.4).</summary>
        public bool DemoMode { get; set; }

        public bool StartWithWindows { get; set; } = true;

        public DeviceSettings Devices { get; set; } = new DeviceSettings();

        public List<JsonElement> Bases { get; set; } = new List<JsonElement>();

        public bool IsPaired => !string.IsNullOrEmpty(AgentId) && !string.IsNullOrEmpty(AgentClientId);
    }

    /// <summary>Atomic read/write of settings.json (<c>.tmp</c> + <c>File.Replace</c>); a corrupt file is moved aside (34 §7.3 #4).</summary>
    public sealed class SettingsStore
    {
        private readonly string _path;
        private readonly object _lock = new object();
        private AgentSettings _current;

        public SettingsStore(string path, Action<string>? onCorrupt = null)
        {
            _path = path;
            _current = Load(onCorrupt);
        }

        public AgentSettings Current
        {
            get
            {
                lock (_lock) return _current;
            }
        }

        public event EventHandler? Changed;

        private AgentSettings Load(Action<string>? onCorrupt)
        {
            if (!File.Exists(_path)) return new AgentSettings();
            try
            {
                var s = AgentJson.Deserialize<AgentSettings>(File.ReadAllText(_path));
                if (s is null || s.V != 1) throw new JsonException("unsupported settings version");
                return s;
            }
            catch (JsonException)
            {
                var bad = _path + ".bad-" + DateTime.UtcNow.ToString("yyyyMMddHHmmss", CultureInfo.InvariantCulture);
                File.Move(_path, bad);
                onCorrupt?.Invoke(bad);
                return new AgentSettings();
            }
        }

        public void Update(Action<AgentSettings> change)
        {
            lock (_lock)
            {
                // Copy-on-write through JSON so readers never see a half-changed object.
                var copy = AgentJson.Deserialize<AgentSettings>(AgentJson.Serialize(_current))!;
                change(copy);
                AtomicFile.WriteAllText(_path, JsonSerializer.Serialize(copy, AgentJson.Indented));
                _current = copy;
            }

            Changed?.Invoke(this, EventArgs.Empty);
        }

        /// <summary>Settings without secrets for the diagnostics package (34 §9.4).</summary>
        public string Redacted()
        {
            var copy = AgentJson.Deserialize<AgentSettings>(AgentJson.Serialize(Current))!;
            if (copy.Keyset != null) copy.Keyset.Jws = "***";
            return JsonSerializer.Serialize(copy, AgentJson.Indented);
        }

        public static IEnumerable<string> ValidateDevices(DeviceSettings d)
        {
            foreach (var p in d.Printers.Where(p => !PrinterService.IsAllowedPrinter(p))) yield return "printer " + p.LocalId + ": private LAN IPv4 and port 9100 only";
            foreach (var t in d.CardTerminals.Where(t => !Core.Security.PrivateLan.IsPrivateIPv4(t.Host) || !Core.Security.PrivateLan.IsValidPort(t.Port))) yield return "card terminal " + t.LocalId + ": private LAN IPv4 only";
        }
    }
}

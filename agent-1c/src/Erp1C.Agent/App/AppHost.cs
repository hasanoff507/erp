using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Agent.LocalApi;
using Erp1C.Agent.Loops;
using Erp1C.Agent.Net;
using Erp1C.Agent.State;
using Erp1C.Agent.Tasks;
using Erp1C.Agent.Update;
using Erp1C.CardTerminal;
using Erp1C.CardTerminal.Drivers.Fake;
using Erp1C.Core.Contracts;
using Erp1C.Core.Hosting;
using Erp1C.Core.Security;
using Erp1C.Core.Trust;
using Erp1C.Devices;
using Erp1C.Fiscal;

namespace Erp1C.Agent.App
{
    /// <summary>Settings → module configuration adapters (read live, so tray edits apply at once).</summary>
    internal sealed class SettingsDeviceConfig : ICardTerminalConfig, IFiscalConfig, IPrinterConfig
    {
        private readonly SettingsStore _s;

        public SettingsDeviceConfig(SettingsStore s)
        {
            _s = s;
        }

        public IReadOnlyList<TerminalConfig> Terminals => _s.Current.Devices.CardTerminals;

        public IReadOnlyList<FiscalDeviceConfig> Devices => _s.Current.Devices.Fiscal;

        public IReadOnlyList<PrinterConfig> Printers => _s.Current.Devices.Printers;

        /// <summary>Fakes only in a DEV build or on a demo-tenant agent (34 §14.4, qaror #34 «fake never in prod»).</summary>
        public bool AllowFakeDriver => BuildInfo.IsDev || _s.Current.DemoMode;

        public bool AllowFakeBridge => BuildInfo.IsDev || _s.Current.DemoMode;
    }

    /// <summary>
    /// Composition root and start/stop order (34 §7.3): data folder, settings, journal recovery, local API, then —
    /// when paired — key, token, hello and the loops. UI talks to the agent only through this class.
    /// </summary>
    public sealed class AppHost : IDisposable
    {
        private readonly CancellationTokenSource _stopping = new CancellationTokenSource();
        private AgentRuntime? _runtime;
        private DeviceAuthorizationResponse? _pendingPair;

        public AppHost(AgentPaths paths)
        {
            Paths = paths;
            paths.Ensure();
            Clock = new ClockSync();
            Logs = new LogOutbox(paths.LogsOutbox);
            Log = new AgentLogger(paths.Logs, Logs, Clock);
            Settings = new SettingsStore(paths.Settings, bad => Log.Error("agent.settings.corrupt", "settings.json was corrupt, moved to " + bad));
            Protector = new DpapiProtector();
            MachineHash = MachineInfo.CurrentMachineHash();
            Keys = new AgentKeyStore(paths.AgentKey, Protector, MachineHash);
            Http = ApiClient.CreateHttpClient();
            Auth = new AuthClient(Http, () => BuildInfo.ServerBase, Keys, Settings, Clock, MachineHash);
            Api = new ApiClient(Http, () => BuildInfo.ServerBase, Auth, Clock);
            Roots = KeysetManager.LoadRoots(paths.DevRootKeys);
            Keysets = new KeysetManager(Roots, Settings, Clock, Log);
            Outbox = new ResultOutbox(paths.Results);
            Journal = new ActionJournal(paths.Actions, Clock);
            Runner = new TaskRunner(Journal, Outbox, Clock, Log);

            var cfg = new SettingsDeviceConfig(Settings);
            var lanes = new DeviceLanes();
            FakeFm = new FakeFiscalBridge(Clock, paths.FakeFm);
            Fiscal = new FiscalModule(new FiscalService(cfg, new IFiscalBridge[] { FakeFm, new UnavailableFiscalBridge("multikassa_local"), new UnavailableFiscalBridge("fiscaldrive_local") }, paths.FiscalJournal, lanes, Clock, Log));
            Printers = new PrinterService(cfg, new TcpRawPrinterTransport(), lanes, Log);
            PrinterModule = new PrinterModule(Printers);
            Cards = new CardTerminalService(cfg, new DriverRegistry(new ICardTerminalDriver[] { new FakeCardTerminalDriver(TimeSpan.FromSeconds(3)) }), new CardJournal(paths.CardJournal, Clock), lanes, Clock, Log);
            CardTasks = new CardTaskHandler(Cards);
            Diagnostics = new DiagnosticsOp(paths, Settings, Outbox, Logs, Clock, (taskId, zip, ct) => Api.UploadDiagnosticsAsync(taskId, zip, ct));
            Acceptor = new TaskAcceptor(Keysets, new IAgentTaskHandler[] { Fiscal, PrinterModule, CardTasks, Diagnostics }, Journal, Clock, () => Settings.Current.AgentId, () => Auth.Claims.TenantId);
            Pairing = new LocalPairing(paths.LocalPairs, Protector, Clock);
        }

        public AgentPaths Paths { get; }

        public ClockSync Clock { get; }

        public LogOutbox Logs { get; }

        public AgentLogger Log { get; }

        public SettingsStore Settings { get; }

        public ISecretProtector Protector { get; }

        public string MachineHash { get; }

        public AgentKeyStore Keys { get; }

        public HttpClient Http { get; }

        public AuthClient Auth { get; }

        public ApiClient Api { get; }

        public RootKeys Roots { get; }

        public KeysetManager Keysets { get; }

        public ResultOutbox Outbox { get; }

        public ActionJournal Journal { get; }

        public TaskRunner Runner { get; }

        public FakeFiscalBridge FakeFm { get; }

        public FiscalModule Fiscal { get; }

        public PrinterService Printers { get; }

        public PrinterModule PrinterModule { get; }

        public CardTerminalService Cards { get; }

        public CardTaskHandler CardTasks { get; }

        public DiagnosticsOp Diagnostics { get; }

        public TaskAcceptor Acceptor { get; }

        public LocalPairing Pairing { get; }

        public LocalApiServer? LocalApi { get; private set; }

        public AgentState State => !Settings.Current.IsPaired ? AgentState.NotPaired : _runtime?.State ?? AgentState.Connecting;

        public DateTimeOffset? OfflineSince => _runtime?.OfflineSince;

        public event EventHandler? StateChanged;

        public event EventHandler? ExitRequested;

        public bool HiddenStart { get; set; }

        /// <summary>34 §7.3 steps 4–8.</summary>
        public void Start()
        {
            Log.Info("agent.started", "agent started " + BuildInfo.Version + " (" + BuildInfo.Channel + ")");
            var recovered = Runner.RecoverUnfinished();
            if (recovered > 0) Log.Warn("task.recovered", recovered.ToString(CultureInfo.InvariantCulture) + " unfinished task(s) reported as failed");
            StartLocalApi();
            if (Settings.Current.IsPaired) StartRuntime();
        }

        private void StartLocalApi()
        {
            var port = Settings.Current.LocalApi.Port;
            if (!BuildInfo.LocalPorts.Contains(port)) port = BuildInfo.LocalPorts.Count > 0 ? BuildInfo.LocalPorts[0] : BuildInfo.DefaultLocalPort;
            var origins = new List<string>(BuildInfo.AppOrigins);
            if (BuildInfo.IsDev) origins.AddRange(Settings.Current.LocalApi.DevOrigins);
            LocalApi = new LocalApiServer(port, new OriginPolicy(origins), Pairing, new ILocalApiModule[]
            {
                new AgentLocalModule(Pairing, Fiscal, Printers, Cards),
                Fiscal,
                PrinterModule,
                new CardLocalApi(Cards),
            }, Log);
            try
            {
                LocalApi.Start();
                Log.Info("local_api.started", "local API on 127.0.0.1:" + LocalApi.Port.ToString(CultureInfo.InvariantCulture));
            }
            catch (System.Net.Sockets.SocketException e)
            {
                Log.Error("local_api.port_busy", "local API port " + port.ToString(CultureInfo.InvariantCulture) + " is busy: " + e.SocketErrorCode);
            }
        }

        private void StartRuntime()
        {
            _runtime?.Dispose();
            _runtime = new AgentRuntime(new RuntimeDeps
            {
                Api = Api,
                Auth = Auth,
                Settings = Settings,
                Keysets = Keysets,
                Acceptor = Acceptor,
                Runner = Runner,
                Outbox = Outbox,
                Journal = Journal,
                Logs = Logs,
                Clock = Clock,
                Log = Log,
                Capabilities = new ICapabilityProvider[] { Fiscal, PrinterModule, CardTasks },
                MachineHash = MachineHash,
                OnRevoked = () => ForgetPairing("revoked"),
                CheckUpdate = CheckUpdateAsync,
                OnLogLevel = Log.SetLevel,
            });
            Keysets.Fetch = ct => _runtime!.FetchTaskKeysAsync(ct);
            _runtime.StateChanged += (_, __) => StateChanged?.Invoke(this, EventArgs.Empty);
            _runtime.Start();
            StateChanged?.Invoke(this, EventArgs.Empty);
        }

        // ---------------------------------------------------------------- pairing (34 §5.3)

        public async Task<DeviceAuthorizationResponse> BeginPairingAsync(CancellationToken ct)
        {
            _pendingPair = await Auth.StartDeviceAuthorizationAsync(ct).ConfigureAwait(false);
            return _pendingPair;
        }

        /// <summary>Waits for the owner to approve the code in BO-22, then stores agent_id/keyset and starts the loops.</summary>
        public async Task<string> CompletePairingAsync(CancellationToken ct)
        {
            var auth = _pendingPair ?? throw new InvalidOperationException("pairing not started");
            var tr = await Auth.PollDeviceTokenAsync(auth, ct).ConfigureAwait(false);
            Settings.Update(s =>
            {
                s.AgentId = tr.AgentId;
                s.AgentClientId = tr.AgentClientId;
                s.TenantName = tr.TenantName;
                s.PairedAt = Iso.S(Clock.UtcNow);
            });
            Keysets.Accept(tr.TaskKeyset);
            Log.Info("agent.paired", "agent paired");
            _pendingPair = null;
            StartRuntime();
            return tr.TenantName ?? string.Empty;
        }

        /// <summary>UI «Kompyuterni uzish» (34 §5.6): wait for the lane, A-10, local clean-up.</summary>
        public async Task UnpairAsync(string reason)
        {
            if (_runtime != null)
            {
                using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
                try
                {
                    await Runner.WaitIdleAsync(cts.Token).ConfigureAwait(false);
                    await _runtime.UnpairAsync(reason, cts.Token).ConfigureAwait(false);
                }
                catch (Exception e) when (e is OperationCanceledException || e is ApiException || e is NetworkException || e is AgentKeyUnavailableException)
                {
                    Log.Warn("agent.unpaired", "A-10 unpair not delivered: " + e.GetType().Name);
                }
            }

            ForgetPairing(reason);
        }

        /// <summary>34 §5.6 clean-up: key, token, keyset, agent id; the tray turns red.</summary>
        private void ForgetPairing(string reason)
        {
            var rt = _runtime;
            _runtime = null;
            if (rt != null) _ = rt.StopAsync();
            Keys.Delete();
            Auth.ForgetToken();
            Keysets.Clear();
            Settings.Update(s =>
            {
                s.AgentId = null;
                s.AgentClientId = null;
                s.TenantName = null;
                s.Keyset = null;
            });
            Log.Warn("agent.unpaired", "agent unpaired: " + reason);
            StateChanged?.Invoke(this, EventArgs.Empty);
        }

        // ---------------------------------------------------------------- update (34 §4.4)

        public IAuthenticodeCheck Authenticode { get; set; } = new WinTrustAuthenticodeCheck();

        public string? LastUpdateError { get; private set; }

        private int _updating;

        private async Task CheckUpdateAsync(bool mandatory, CancellationToken ct)
        {
            if (Interlocked.Exchange(ref _updating, 1) == 1) return;
            try
            {
                var channel = Settings.Current.UpdateChannel;
                var env = await Api.GetAsync<UpdateManifestEnvelope>("/api/v1/onec-agent/update-manifest?channel=" + Uri.EscapeDataString(channel), TimeSpan.FromSeconds(30), ct).ConfigureAwait(false);
                if (env.Value is null) return;
                var m = ManifestVerifier.Verify(env.Value, Roots, channel, BuildInfo.Version, SetupLauncher.CurrentOsVersion(), BuildInfo.Protocol);
                Log.Info("agent.update.available", "update available " + SetupLauncher.Describe(m));
                var setup = await new Downloader(Http).DownloadAsync(m, Paths.Updates, ct).ConfigureAwait(false);
                if (!Authenticode.IsTrusted(setup, BuildInfo.ExpectedPublisher)) throw new UpdateRejectedException("authenticode");
                await Runner.WaitIdleAsync(ct).ConfigureAwait(false);
                Log.Info("agent.update.installed", "starting setup " + m.Version);
                SetupLauncher.Launch(setup, HiddenStart);
                ExitRequested?.Invoke(this, EventArgs.Empty);
            }
            catch (UpdateRejectedException e)
            {
                LastUpdateError = e.Reason;
                Log.Error("agent.update.rejected", "update rejected: " + e.Reason);
            }
            catch (ApiException e) when (e.Status == 404)
            {
                // no manifest for the channel
            }
            finally
            {
                Interlocked.Exchange(ref _updating, 0);
            }
        }

        public async Task StopAsync()
        {
            _stopping.Cancel();
            if (_runtime != null) await _runtime.StopAsync().ConfigureAwait(false);
        }

        public void Dispose()
        {
            LocalApi?.Dispose();
            _runtime?.Dispose();
            Http.Dispose();
            Log.Dispose();
            _stopping.Dispose();
        }
    }
}

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Agent.App;
using Erp1C.Agent.Net;
using Erp1C.Agent.State;
using Erp1C.Agent.Tasks;
using Erp1C.Core.Contracts;
using Erp1C.Core.Hosting;
using Erp1C.Core.Json;

namespace Erp1C.Agent.Loops
{
    /// <summary>Connection state shown by the tray (34 §10).</summary>
    public enum AgentState
    {
        NotPaired,
        Connecting,
        Online,
        Offline,
        SubscriptionRestricted,
        UpdateRequired,
        Revoked,
        KeyUnavailable,
    }

    /// <summary>Everything the pull cycle needs (built by AppHost, faked in tests).</summary>
    public sealed class RuntimeDeps
    {
        public ApiClient Api { get; set; } = null!;

        public AuthClient Auth { get; set; } = null!;

        public SettingsStore Settings { get; set; } = null!;

        public KeysetManager Keysets { get; set; } = null!;

        public TaskAcceptor Acceptor { get; set; } = null!;

        public TaskRunner Runner { get; set; } = null!;

        public ResultOutbox Outbox { get; set; } = null!;

        public ActionJournal Journal { get; set; } = null!;

        public LogOutbox Logs { get; set; } = null!;

        public ClockSync Clock { get; set; } = null!;

        public IAgentLogger Log { get; set; } = NullAgentLogger.Instance;

        public IReadOnlyList<ICapabilityProvider> Capabilities { get; set; } = Array.Empty<ICapabilityProvider>();

        public string MachineHash { get; set; } = string.Empty;

        public Func<TimeSpan, CancellationToken, Task> Delay { get; set; } = (d, ct) => Task.Delay(d, ct);

        /// <summary>Called on 403 ONEC_AGENT_REVOKED / agent_revoked (34 §5.6).</summary>
        public Action? OnRevoked { get; set; }

        /// <summary>Called when an update must be checked (hello.update, 426, every 6 h).</summary>
        public Func<bool, CancellationToken, Task>? CheckUpdate { get; set; }

        public Action<string?>? OnLogLevel { get; set; }
    }

    /// <summary>
    /// The pull cycle (34 §7.2): hello (600 s and on events), long-poll, heartbeat (15 s), results (on enqueue + 30 s),
    /// logs (60 s / 200 entries), update (6 h). Only outgoing HTTPS. Each loop has its own backoff.
    /// </summary>
    public sealed class AgentRuntime : IDisposable
    {
        public static readonly TimeSpan HeartbeatEvery = TimeSpan.FromSeconds(15);
        public static readonly TimeSpan ResultsEvery = TimeSpan.FromSeconds(30);
        public static readonly TimeSpan LogsEvery = TimeSpan.FromSeconds(60);
        public static readonly TimeSpan UpdateEvery = TimeSpan.FromHours(6);
        public static readonly TimeSpan PollClientTimeout = TimeSpan.FromSeconds(35);

        private readonly RuntimeDeps _d;
        private readonly CancellationTokenSource _stop = new CancellationTokenSource();
        private readonly SemaphoreSlim _helloNow = new SemaphoreSlim(0);
        private readonly SemaphoreSlim _resultsNow = new SemaphoreSlim(0);
        private readonly List<Task> _loops = new List<Task>();
        private int _helloIntervalS = 600;
        private volatile AgentState _state = AgentState.Connecting;
        private volatile bool _restricted;
        private volatile bool _updateRequired;
        private int _shortPollSuccesses;
        private int _pollFailures;

        public AgentRuntime(RuntimeDeps deps)
        {
            _d = deps;
            _d.Outbox.Enqueued += (_, __) => SignalResults();
        }

        public AgentState State => _state;

        public DateTimeOffset? OfflineSince { get; private set; }

        public event EventHandler? StateChanged;

        public int PollOk { get; private set; }

        public int PollErrors { get; private set; }

        private CancellationToken Stopping => _stop.Token;

        public void Start()
        {
            _loops.Add(Task.Run(HelloLoop));
            _loops.Add(Task.Run(PollLoop));
            _loops.Add(Task.Run(HeartbeatLoop));
            _loops.Add(Task.Run(ResultLoop));
            _loops.Add(Task.Run(LogLoop));
            _loops.Add(Task.Run(UpdateLoop));
        }

        public async Task StopAsync()
        {
            _stop.Cancel();
            try
            {
                await Task.WhenAll(_loops).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
            }
        }

        public void HelloNow() => _helloNow.Release();

        public void SignalResults() => _resultsNow.Release();

        private void SetState(AgentState s)
        {
            if (s == AgentState.Offline && _state != AgentState.Offline) OfflineSince = _d.Clock.UtcNow;
            if (s == AgentState.Online) OfflineSince = null;
            if (_state == s) return;
            _state = s;
            StateChanged?.Invoke(this, EventArgs.Empty);
        }

        /// <summary>Common handling of a failed call; returns true when the loop must stop for good.</summary>
        private bool HandleFailure(Exception e)
        {
            switch (e)
            {
                case ApiException a when a.IsRevoked:
                    SetState(AgentState.Revoked);
                    _d.Log.Error("agent.unpaired", "agent revoked by the server");
                    _d.OnRevoked?.Invoke();
                    _stop.Cancel();
                    return true;
                case ApiException a when a.IsUpdateRequired:
                    _updateRequired = true;
                    SetState(AgentState.UpdateRequired);
                    _ = _d.CheckUpdate?.Invoke(true, Stopping);
                    return false;
                case ApiException a when a.IsSubscriptionRestricted:
                    _restricted = true;
                    SetState(AgentState.SubscriptionRestricted);
                    return false;
                case AgentKeyUnavailableException _:
                    SetState(AgentState.KeyUnavailable);
                    _d.Log.Error("ONEC_DPAPI_FAILED", "agent key cannot be opened — re-pair the computer");
                    _stop.Cancel();
                    return true;
                case NetworkException _:
                case ApiException x when x.IsTransient:
                    SetState(AgentState.Offline);
                    return false;
                default:
                    return false;
            }
        }

        // ---------------------------------------------------------------- A-01 hello

        public HelloRequest BuildHello()
        {
            var caps = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
            {
                ["onec"] = AgentJson.ToElement(new { enabled = false, version = 0 }),
            };
            foreach (var p in _d.Capabilities) caps[p.Family] = AgentJson.ToElement(p.Describe());
            if (!caps.ContainsKey("scale")) caps["scale"] = AgentJson.ToElement(new { enabled = false, version = 0, devices = Array.Empty<object>() });
            return new HelloRequest
            {
                AgentVersion = BuildInfo.Version,
                Protocol = BuildInfo.Protocol,
                OsVersion = MachineInfo.OsVersion(),
                MachineHash = _d.MachineHash,
                PcName = MachineInfo.PcName(),
                TaskKeysetVersion = _d.Keysets.Current is null ? (int?)null : _d.Keysets.Version,
                ResultsOutboxPending = _d.Outbox.Count,
                Capabilities = caps,
                Clock = Iso.S(_d.Clock.LocalNow), // uncorrected local UTC (34 §7.9)
            };
        }

        public async Task<bool> HelloOnceAsync(CancellationToken ct)
        {
            var sent = _d.Clock.LocalNow;
            var resp = await _d.Api.PostAsync<HelloResponse>("/api/v1/onec-agent/hello", BuildHello(), TimeSpan.FromSeconds(30), ct).ConfigureAwait(false);
            var received = _d.Clock.LocalNow;
            var h = resp.Value ?? new HelloResponse();
            if (h.ServerTime != null && DateTimeOffset.TryParse(h.ServerTime, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out var st))
            {
                _d.Clock.FromHello(st, sent, received);
                if (_d.Clock.Skewed) _d.Log.Warn("agent.clock_skew", "computer clock is off by " + ((int)_d.Clock.Offset.TotalSeconds).ToString(CultureInfo.InvariantCulture) + " s");
            }

            if (h.TaskKeyset != null) _d.Keysets.Accept(h.TaskKeyset);
            _helloIntervalS = h.HelloIntervalS > 0 ? h.HelloIntervalS : 600;
            _d.OnLogLevel?.Invoke(h.LogLevel);
            _restricted = false;
            if (h.Update != null && !string.IsNullOrEmpty(h.Update.Version)) _ = _d.CheckUpdate?.Invoke(h.Update.Mandatory, Stopping);
            SetState(AgentState.Online);
            return true;
        }

        private async Task HelloLoop()
        {
            var backoff = new Backoff();
            while (!Stopping.IsCancellationRequested)
            {
                TimeSpan wait;
                try
                {
                    await HelloOnceAsync(Stopping).ConfigureAwait(false);
                    backoff.Reset();
                    wait = TimeSpan.FromSeconds(_helloIntervalS);
                }
                catch (OperationCanceledException) when (Stopping.IsCancellationRequested)
                {
                    return;
                }
                catch (Exception e)
                {
                    if (HandleFailure(e)) return;
                    wait = _restricted ? TimeSpan.FromSeconds(600) : backoff.NextWith((e as ApiException)?.RetryAfter);
                }

                try
                {
                    await _helloNow.WaitAsync(wait, Stopping).ConfigureAwait(false);
                }
                catch (OperationCanceledException)
                {
                    return;
                }
            }
        }

        // ---------------------------------------------------------------- A-03 poll

        private async Task PollLoop()
        {
            var backoff = new Backoff();
            while (!Stopping.IsCancellationRequested)
            {
                try
                {
                    if (_restricted || _updateRequired || _state == AgentState.Connecting)
                    {
                        await _d.Delay(TimeSpan.FromSeconds(2), Stopping).ConfigureAwait(false);
                        continue;
                    }

                    // Poll only when the agent lane is free (max_tasks 0 → no request, 34 §7.4).
                    await _d.Runner.WaitIdleAsync(Stopping).ConfigureAwait(false);
                    var shortPoll = _pollFailures >= 2;
                    var req = new PollRequest { MaxTasks = 1, WaitS = shortPoll ? 0 : 25 };
                    var resp = await _d.Api.PostAsync<PollResponse>("/api/v1/onec-agent/poll", req, PollClientTimeout, Stopping).ConfigureAwait(false);
                    PollOk++;
                    backoff.Reset();
                    SetState(AgentState.Online);
                    if (shortPoll && ++_shortPollSuccesses >= 10)
                    {
                        _pollFailures = 0;
                        _shortPollSuccesses = 0;
                    }

                    if (resp.Status == 200 && resp.Value != null)
                    {
                        foreach (var raw in resp.Value.Tasks) await HandleEnvelopeAsync(raw).ConfigureAwait(false);
                    }
                    else if (shortPoll)
                    {
                        // 26 #137: an antivirus that breaks long-polls → short polls every 30 s.
                        await _d.Delay(TimeSpan.FromSeconds(30), Stopping).ConfigureAwait(false);
                    }
                }
                catch (OperationCanceledException) when (Stopping.IsCancellationRequested)
                {
                    return;
                }
                catch (Exception e)
                {
                    PollErrors++;
                    if (e is NetworkException) _pollFailures++;
                    if (HandleFailure(e)) return;
                    try
                    {
                        await _d.Delay(backoff.NextWith((e as ApiException)?.RetryAfter), Stopping).ConfigureAwait(false);
                    }
                    catch (OperationCanceledException)
                    {
                        return;
                    }
                }
            }
        }

        /// <summary>33 §9.11 checks, then lane / outbox (rejections and journal replays free the lease at once).</summary>
        public async Task HandleEnvelopeAsync(JsonElement raw)
        {
            var r = await _d.Acceptor.AcceptAsync(raw, Stopping).ConfigureAwait(false);
            switch (r.Decision)
            {
                case AcceptDecision.Accepted:
                    await _d.Runner.StartAsync(r.Envelope!, r.Handler!, Stopping).ConfigureAwait(false);
                    break;
                case AcceptDecision.Replay:
                    _d.Runner.EnqueueResult(r.Envelope!, r.Result!);
                    break;
                case AcceptDecision.Rejected:
                    RejectedCount++;
                    _d.Log.Error("task.rejected", "task rejected (security): " + r.Reason, new Dictionary<string, object?> { ["task_id"] = r.Envelope?.TaskId, ["kind"] = r.Envelope?.Kind, ["reason"] = r.Reason, ["field"] = r.Field });
                    _d.Runner.EnqueueResult(r.Envelope!, r.Result!);
                    break;
                default:
                    RejectedCount++;
                    _d.Log.Error("task.rejected", "task envelope without task_id/lease_id dropped");
                    break;
            }
        }

        public int RejectedCount { get; private set; }

        // ---------------------------------------------------------------- A-04 heartbeat

        private async Task HeartbeatLoop()
        {
            while (!Stopping.IsCancellationRequested)
            {
                try
                {
                    await _d.Delay(HeartbeatEvery, Stopping).ConfigureAwait(false);
                }
                catch (OperationCanceledException)
                {
                    return;
                }

                foreach (var rt in _d.Runner.Running.ToList()) await HeartbeatOnceAsync(rt).ConfigureAwait(false);
            }
        }

        public async Task HeartbeatOnceAsync(RunningTask rt)
        {
            try
            {
                var body = new HeartbeatRequest { LeaseId = rt.Envelope.LeaseId, Progress = new HeartbeatProgress { Stage = rt.Stage, Pct = rt.Pct, Message = null } };
                var resp = await _d.Api.PostAsync<HeartbeatResponse>("/api/v1/onec-agent/tasks/" + rt.Envelope.TaskId + "/heartbeat", body, TimeSpan.FromSeconds(20), Stopping).ConfigureAwait(false);
                if (resp.Value?.CancelRequested == true) _d.Runner.Cancel(rt.Envelope.TaskId);
            }
            catch (ApiException e) when (e.Status == 409)
            {
                // ONEC_TASK_LEASE_LOST: a read stops; a device action finishes and its result is still sent.
                _d.Runner.Cancel(rt.Envelope.TaskId);
            }
            catch (Exception e) when (!(e is OperationCanceledException))
            {
                HandleFailure(e); // network / 5xx: next tick, the work is not stopped
            }
        }

        // ---------------------------------------------------------------- A-05 results

        private async Task ResultLoop()
        {
            while (!Stopping.IsCancellationRequested)
            {
                // Network / 5xx: the outbox is retried every 30 s (34 §7.7); a new result wakes the sender at once.
                var wait = ResultsEvery;
                try
                {
                    await SendResultsOnceAsync(Stopping).ConfigureAwait(false);
                }
                catch (OperationCanceledException) when (Stopping.IsCancellationRequested)
                {
                    return;
                }

                try
                {
                    await _resultsNow.WaitAsync(wait, Stopping).ConfigureAwait(false);
                }
                catch (OperationCanceledException)
                {
                    return;
                }
            }
        }

        /// <summary>Sends the outbox oldest-first (34 §7.7); false when a transient error stopped it.</summary>
        public async Task<bool> SendResultsOnceAsync(CancellationToken ct)
        {
            foreach (var e in _d.Outbox.Pending())
            {
                try
                {
                    await _d.Api.PostAsync<ResultResponse>("/api/v1/onec-agent/tasks/" + e.TaskId + "/result", e.Body, TimeSpan.FromSeconds(60), ct).ConfigureAwait(false);
                    _d.Outbox.Remove(e.TaskId, e.LeaseId);
                    _d.Journal.Delivered(e.TaskId, e.Attempt);
                }
                catch (ApiException a) when (a.Status == 404 || a.Status == 409)
                {
                    _d.Outbox.Remove(e.TaskId, e.LeaseId);
                    _d.Log.Warn("task.result.dropped", "result not accepted (" + a.Code + ")", new Dictionary<string, object?> { ["task_id"] = e.TaskId });
                }
                catch (ApiException a) when (a.Status == 413 || a.Status == 422)
                {
                    // Store-agent results are small; a 413/422 is an agent fault — drop and keep the journal copy.
                    _d.Outbox.Remove(e.TaskId, e.LeaseId);
                    _d.Log.Error("task.result.dropped", "result rejected (" + a.Code + ")", new Dictionary<string, object?> { ["task_id"] = e.TaskId });
                }
                catch (Exception x) when (!(x is OperationCanceledException))
                {
                    if (x is ApiException ae && !ae.IsTransient && !ae.IsRevoked && ae.Status >= 400 && ae.Status < 500 && !ae.IsSubscriptionRestricted && !ae.IsUpdateRequired)
                    {
                        _d.Outbox.Remove(e.TaskId, e.LeaseId);
                        _d.Log.Error("task.result.dropped", "result rejected (" + ae.Code + ")");
                        continue;
                    }

                    HandleFailure(x);
                    return false;
                }
            }

            return true;
        }

        // ---------------------------------------------------------------- A-06 logs

        private async Task LogLoop()
        {
            while (!Stopping.IsCancellationRequested)
            {
                try
                {
                    await _d.Delay(LogsEvery, Stopping).ConfigureAwait(false);
                    await ShipLogsOnceAsync(Stopping).ConfigureAwait(false);
                }
                catch (OperationCanceledException)
                {
                    return;
                }
                catch (Exception e)
                {
                    HandleFailure(e); // entries stay queued
                }
            }
        }

        public async Task ShipLogsOnceAsync(CancellationToken ct)
        {
            while (true)
            {
                var batch = _d.Logs.Take(500);
                if (batch.Count == 0) return;
                await _d.Api.PostAsync<LogsResponse>("/api/v1/onec-agent/logs", new LogsRequest { Entries = batch.ToList() }, TimeSpan.FromSeconds(30), ct).ConfigureAwait(false);
                _d.Logs.Remove(batch.Select(b => b.ClientLogId));
                if (batch.Count < 500) return;
            }
        }

        // ---------------------------------------------------------------- A-09 update

        private async Task UpdateLoop()
        {
            while (!Stopping.IsCancellationRequested)
            {
                try
                {
                    await _d.Delay(UpdateEvery, Stopping).ConfigureAwait(false);
                    if (_d.CheckUpdate != null) await _d.CheckUpdate(false, Stopping).ConfigureAwait(false);
                }
                catch (OperationCanceledException)
                {
                    return;
                }
                catch (Exception e)
                {
                    HandleFailure(e);
                }
            }
        }

        // ---------------------------------------------------------------- A-08 / A-10

        public async Task<string?> FetchTaskKeysAsync(CancellationToken ct)
        {
            var r = await _d.Api.GetAsync<TaskKeysResponse>("/api/v1/onec-agent/task-keys", TimeSpan.FromSeconds(30), ct).ConfigureAwait(false);
            return r.Value?.TaskKeyset;
        }

        public Task UnpairAsync(string reason, CancellationToken ct) =>
            _d.Api.PostAsync<object>("/api/v1/onec-agent/unpair", new UnpairRequest { Reason = reason }, TimeSpan.FromSeconds(10), ct);

        public void Dispose()
        {
            _stop.Dispose();
            _helloNow.Dispose();
            _resultsNow.Dispose();
        }
    }
}

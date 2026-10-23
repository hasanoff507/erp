using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Agent.State;
using Erp1C.Core.Contracts;
using Erp1C.Core.Errors;
using Erp1C.Core.Hosting;
using Erp1C.Core.Masking;
using Erp1C.Core.Security;

namespace Erp1C.Agent.Tasks
{
    /// <summary>A task in flight — what the heartbeat pump reports (33 A-04).</summary>
    public sealed class RunningTask
    {
        public RunningTask(TaskEnvelope envelope, CancellationTokenSource cts, bool cancellable)
        {
            Envelope = envelope;
            Cts = cts;
            Cancellable = cancellable;
        }

        public TaskEnvelope Envelope { get; }

        public CancellationTokenSource Cts { get; }

        /// <summary>Pure reads may be stopped on cancel_requested / lease lost; device actions always finish (34 §7.6).</summary>
        public bool Cancellable { get; }

        public string Stage { get; set; } = "connecting";

        public int Pct { get; set; }

        public bool Cancelled { get; set; }
    }

    /// <summary>
    /// The agent-level lane (34 §1.3 AgentLane; 33 §5.15 one leased agent-level task): one store-agent task at a time,
    /// journal <c>started</c> → handler (watchdog = <c>timeout_s</c> clamped to [10, 1800]) → journal <c>finished</c> →
    /// results outbox. Device lanes inside the modules keep devices independent.
    /// </summary>
    public sealed class TaskRunner : IDisposable
    {
        /// <summary>Kinds that only read state — they may be stopped when the server cancels / the lease is lost.</summary>
        private static readonly HashSet<string> ReadOnlyKinds = new HashSet<string>(StringComparer.Ordinal) { "fiscal.status", "card.status", "collect_diagnostics" };

        private readonly ActionJournal _journal;
        private readonly ResultOutbox _outbox;
        private readonly IClock _clock;
        private readonly IAgentLogger _log;
        private readonly SemaphoreSlim _lane = new SemaphoreSlim(1, 1);
        private readonly ConcurrentDictionary<string, RunningTask> _running = new ConcurrentDictionary<string, RunningTask>(StringComparer.OrdinalIgnoreCase);

        public TaskRunner(ActionJournal journal, ResultOutbox outbox, IClock clock, IAgentLogger log)
        {
            _journal = journal;
            _outbox = outbox;
            _clock = clock;
            _log = log;
        }

        public bool Busy => _lane.CurrentCount == 0;

        public IReadOnlyCollection<RunningTask> Running => _running.Values.ToList();

        public Task WaitIdleAsync(CancellationToken ct) => WaitIdleCoreAsync(ct);

        private async Task WaitIdleCoreAsync(CancellationToken ct)
        {
            await _lane.WaitAsync(ct).ConfigureAwait(false);
            _lane.Release();
        }

        /// <summary>Puts a rejection / replayed result straight into the outbox (frees the server lease).</summary>
        public void EnqueueResult(TaskEnvelope env, ResultBody body)
        {
            _outbox.Enqueue(new OutboxEntry { TaskId = env.TaskId, LeaseId = env.LeaseId, Attempt = env.Attempt, QueuedAt = Iso.Ms(_clock.UtcNow), Body = body });
        }

        /// <summary>Starts an accepted task on the lane (returns once it is running).</summary>
        public async Task StartAsync(TaskEnvelope env, IAgentTaskHandler handler, CancellationToken appStopping)
        {
            await _lane.WaitAsync(appStopping).ConfigureAwait(false);
            var cts = CancellationTokenSource.CreateLinkedTokenSource(appStopping);
            var timeout = TimeSpan.FromSeconds(Math.Min(1800, Math.Max(10, env.TimeoutS)));
            cts.CancelAfter(timeout);
            var rt = new RunningTask(env, cts, ReadOnlyKinds.Contains(env.Kind));
            _running[env.TaskId] = rt;
            _journal.Started(env.TaskId, env.Attempt, env.LeaseId, env.Kind, env.PayloadSha256);
            _log.Info("task.accepted", "task accepted", new Dictionary<string, object?> { ["task_id"] = env.TaskId, ["kind"] = env.Kind, ["attempt"] = env.Attempt });
            _ = Task.Run(() => RunAsync(rt, handler), CancellationToken.None);
        }

        private async Task RunAsync(RunningTask rt, IAgentTaskHandler handler)
        {
            var env = rt.Envelope;
            var started = _clock.UtcNow;
            var sw = Stopwatch.StartNew();
            ResultBody body;
            try
            {
                var ctx = new TaskContext(env.TaskId, env.Kind, env.Attempt, env.LeaseId, (stage, pct) =>
                {
                    rt.Stage = stage;
                    rt.Pct = pct;
                });
                var exec = await handler.ExecuteAsync(ctx, env.Payload, rt.Cts.Token).ConfigureAwait(false);
                body = Body(env, exec.Outcome, exec.Data, exec.Error, started, sw);
            }
            catch (OperationCanceledException) when (rt.Cancelled)
            {
                _journal.Cancelled(env.TaskId, env.Attempt, "cancel_requested");
                _log.Info("task.cancelled", "task stopped by the server", new Dictionary<string, object?> { ["task_id"] = env.TaskId });
                Finish(rt);
                return;
            }
            catch (OperationCanceledException)
            {
                body = Body(env, "failed", TaskExecution.EmptyObject(), ErrorObj.Of(AgentCodes.Timeout, "task watchdog timeout", true), started, sw);
            }
            catch (Exception e)
            {
                // Never leak an exception text unmasked; device actions report a transient failure.
                body = Body(env, "failed", TaskExecution.EmptyObject(), ErrorObj.Of(AgentCodes.WorkerCrashed, SecretMasker.Mask(e.GetType().Name + ": " + e.Message), true), started, sw);
            }

            if (rt.Cancelled && rt.Cancellable)
            {
                _journal.Cancelled(env.TaskId, env.Attempt, "cancel_requested");
                Finish(rt);
                return;
            }

            _journal.Finished(env.TaskId, env.Attempt, body);
            EnqueueResult(env, body);
            _log.Info("task.finished", "task finished: " + body.Outcome, new Dictionary<string, object?> { ["task_id"] = env.TaskId, ["kind"] = env.Kind, ["code"] = body.Error?.Code, ["duration_ms"] = body.DurationMs });
            Finish(rt);
        }

        private void Finish(RunningTask rt)
        {
            _running.TryRemove(rt.Envelope.TaskId, out _);
            rt.Cts.Dispose();
            _lane.Release();
        }

        private ResultBody Body(TaskEnvelope env, string outcome, JsonElement data, ErrorObj? error, DateTimeOffset started, Stopwatch sw) => new ResultBody
        {
            LeaseId = env.LeaseId,
            Attempt = env.Attempt,
            Outcome = outcome,
            Data = data,
            Error = error,
            StartedAt = Iso.S(started),
            FinishedAt = Iso.S(_clock.UtcNow),
            DurationMs = sw.ElapsedMilliseconds,
            WorkerBits = null,
        };

        /// <summary>cancel_requested / 409 lease lost: stop a pure read; device actions run to the end.</summary>
        public void Cancel(string taskId)
        {
            if (_running.TryGetValue(taskId, out var rt) && rt.Cancellable)
            {
                rt.Cancelled = true;
                rt.Cts.Cancel();
            }
        }

        public void Dispose() => _lane.Dispose();

        /// <summary>Start-up recovery (34 §7.3 #5): an attempt started but never finished becomes a failed result.</summary>
        public int RecoverUnfinished()
        {
            var n = 0;
            foreach (var a in _journal.Unfinished())
            {
                var body = new ResultBody
                {
                    LeaseId = a.LeaseId ?? string.Empty,
                    Attempt = a.Attempt,
                    Outcome = "failed",
                    Data = TaskExecution.EmptyObject(),
                    Error = ErrorObj.Of(AgentCodes.WorkerCrashed, "agent stopped while the task was running", true),
                    StartedAt = a.At,
                    FinishedAt = Iso.S(_clock.UtcNow),
                    DurationMs = 0,
                };
                _journal.Finished(a.TaskId, a.Attempt, body);
                if (!string.IsNullOrEmpty(a.LeaseId)) EnqueueResult(new TaskEnvelope { TaskId = a.TaskId, LeaseId = a.LeaseId!, Attempt = a.Attempt }, body);
                n++;
            }

            return n;
        }
    }
}

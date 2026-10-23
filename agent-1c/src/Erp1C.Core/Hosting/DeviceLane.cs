using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace Erp1C.Core.Hosting
{
    /// <summary>
    /// Per-device FIFO lane (34 §14.1, §14.4): one operation on a device at a time, strictly in arrival order.
    /// <see cref="TryEnterExclusiveAsync"/> is for operations that must not queue behind another transaction
    /// (card <c>purchase</c> → <c>CARD_TERMINAL_BUSY</c>): it fails immediately while a transaction is running or
    /// queued, otherwise it waits only for short operations ahead of it. Lanes of different devices never block
    /// each other.
    /// </summary>
    public sealed class DeviceLane
    {
        private readonly object _gate = new object();
        private readonly LinkedList<TaskCompletionSource<bool>> _waiters = new LinkedList<TaskCompletionSource<bool>>();
        private bool _held;
        private int _transactions;

        public DeviceLane(string deviceId)
        {
            DeviceId = deviceId;
        }

        public string DeviceId { get; }

        /// <summary>A transaction (purchase/refund/void/settlement/fiscal receipt…) is running or waiting.</summary>
        public bool HasTransaction
        {
            get
            {
                lock (_gate) return _transactions > 0;
            }
        }

        public bool IsBusy
        {
            get
            {
                lock (_gate) return _held;
            }
        }

        /// <summary>Waits for the lane (FIFO). <paramref name="transaction"/> marks the slot as a transaction.</summary>
        public Task<IDisposable> EnterAsync(bool transaction, CancellationToken ct) => EnterCoreAsync(transaction, false, ct)!;

        /// <summary>Null when another transaction is running or queued (caller answers "busy").</summary>
        public Task<IDisposable?> TryEnterExclusiveAsync(CancellationToken ct) => EnterCoreAsync(true, true, ct);

        private async Task<IDisposable?> EnterCoreAsync(bool transaction, bool failIfTransaction, CancellationToken ct)
        {
            TaskCompletionSource<bool> tcs;
            LinkedListNode<TaskCompletionSource<bool>> node;
            lock (_gate)
            {
                if (failIfTransaction && _transactions > 0) return null;
                if (transaction) _transactions++;
                if (!_held)
                {
                    _held = true;
                    return new Releaser(this, transaction);
                }

                tcs = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
                node = _waiters.AddLast(tcs);
            }

            using (ct.Register(() =>
            {
                lock (_gate)
                {
                    if (node.List != null)
                    {
                        _waiters.Remove(node);
                        if (transaction) _transactions--;
                        tcs.TrySetCanceled();
                    }
                }
            }))
            {
                await tcs.Task.ConfigureAwait(false);
            }

            return new Releaser(this, transaction);
        }

        private void Release(bool transaction)
        {
            lock (_gate)
            {
                if (transaction) _transactions--;
                if (_waiters.Count == 0)
                {
                    _held = false;
                    return;
                }

                var next = _waiters.First!;
                _waiters.RemoveFirst();
                next.Value.TrySetResult(true); // lane handed over, _held stays true
            }
        }

        private sealed class Releaser : IDisposable
        {
            private readonly DeviceLane _lane;
            private readonly bool _transaction;
            private int _disposed;

            public Releaser(DeviceLane lane, bool transaction)
            {
                _lane = lane;
                _transaction = transaction;
            }

            public void Dispose()
            {
                if (Interlocked.Exchange(ref _disposed, 1) == 0) _lane.Release(_transaction);
            }
        }
    }

    /// <summary>Lanes by device id.</summary>
    public sealed class DeviceLanes
    {
        private readonly ConcurrentDictionary<string, DeviceLane> _lanes = new ConcurrentDictionary<string, DeviceLane>(StringComparer.Ordinal);

        public DeviceLane For(string deviceId) => _lanes.GetOrAdd(deviceId, id => new DeviceLane(id));
    }
}

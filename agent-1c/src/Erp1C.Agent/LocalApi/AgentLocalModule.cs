using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Agent.App;
using Erp1C.CardTerminal;
using Erp1C.Core.Hosting;
using Erp1C.Devices;
using Erp1C.Fiscal;

namespace Erp1C.Agent.LocalApi
{
    /// <summary><c>GET /v1/status</c> and <c>POST /v1/pair</c> (21 §16.1).</summary>
    public sealed class AgentLocalModule : ILocalApiModule
    {
        private readonly LocalPairing _pairing;
        private readonly FiscalModule? _fiscal;
        private readonly PrinterService? _print;
        private readonly CardTerminalService? _card;

        public AgentLocalModule(LocalPairing pairing, FiscalModule? fiscal, PrinterService? print, CardTerminalService? card)
        {
            _pairing = pairing;
            _fiscal = fiscal;
            _print = print;
            _card = card;
        }

        public IEnumerable<LocalRoute> Routes => new[]
        {
            new LocalRoute("GET", "/v1/status", Status),
            new LocalRoute("POST", "/v1/pair", Pair, anonymous: true),
        };

        private Task<LocalResponse> Pair(LocalRequest r, CancellationToken ct)
        {
            var b = new BodyReader(r.JsonBody());
            var token = _pairing.Pair(b.RequireString("code", 6), b.RequireString("device_id", 64));
            return Task.FromResult(LocalResponse.Json(new { local_token = token, expires_at = (string?)null }));
        }

        private async Task<LocalResponse> Status(LocalRequest r, CancellationToken ct)
        {
            var fiscalDevices = new List<object>();
            string? provider = null;
            if (_fiscal != null)
            {
                var active = _fiscal.Service.Active();
                provider = active.Count > 0 ? active[0].Bridge.Provider : null;
                foreach (var (d, _) in active)
                {
                    using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
                    cts.CancelAfter(TimeSpan.FromSeconds(1.5));
                    try
                    {
                        var s = await _fiscal.Service.DeviceStatusAsync(d.LocalId, cts.Token).ConfigureAwait(false);
                        fiscalDevices.Add(new { local_id = d.LocalId, fm_state = s.FmState, pending_count = s.PendingCount, oldest_unacked_at = s.OldestUnackedAt });
                    }
                    catch (Exception e) when (e is LocalApiException || e is OperationCanceledException)
                    {
                        // fm_state unknown → the POS does not close a receipt (21 §16 «Fiskal modul ulanmagan»)
                        fiscalDevices.Add(new { local_id = d.LocalId, fm_state = "unknown", pending_count = 0, oldest_unacked_at = (string?)null });
                    }
                }
            }

            object[] terminals = _card?.Terminals().Select(t => (object)new { local_id = t.LocalId, driver = t.Driver, tid = t.Tid, status = t.Status }).ToArray() ?? Array.Empty<object>();
            return LocalResponse.Json(new
            {
                agent_version = BuildInfo.Version,
                capabilities = new
                {
                    fiscal = new { enabled = fiscalDevices.Count > 0, provider },
                    print = new { enabled = _print != null && _print.Enabled },
                    card_terminal = new { enabled = _card != null && _card.Enabled },
                },
                fiscal_devices = fiscalDevices,
                card_terminals = terminals,
            });
        }
    }
}

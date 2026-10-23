using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Core.Contracts;
using Erp1C.Core.Errors;
using Erp1C.Core.Hosting;

namespace Erp1C.CardTerminal
{
    /// <summary>Local API <c>/v1/card/*</c> (21 §16.1, 34 §14.4).</summary>
    public sealed class CardLocalApi : ILocalApiModule
    {
        private readonly CardTerminalService _svc;

        public CardLocalApi(CardTerminalService svc)
        {
            _svc = svc;
        }

        public IEnumerable<LocalRoute> Routes => new[]
        {
            new LocalRoute("GET", "/v1/card/terminals", Terminals),
            new LocalRoute("GET", "/v1/card/health", Health),
            new LocalRoute("POST", "/v1/card/purchase", Purchase),
            new LocalRoute("POST", "/v1/card/refund", Refund),
            new LocalRoute("POST", "/v1/card/void", Void),
            new LocalRoute("GET", "/v1/card/tx/{attempt_id}", Tx),
            new LocalRoute("POST", "/v1/card/cancel-pending", CancelPending),
            new LocalRoute("POST", "/v1/card/settlement", Settlement),
        };

        private Task<LocalResponse> Terminals(LocalRequest r, CancellationToken ct)
        {
            // Cached health (≤ 30 s); stale entries refresh in the background.
            foreach (var t in _svc.ActiveTerminals().Where(t => _svc.HealthStale(t.Config.LocalId)))
            {
                var id = t.Config.LocalId;
                _ = Task.Run(() => _svc.HealthAsync(id, false, CancellationToken.None));
            }

            return Task.FromResult(LocalResponse.Json(new { items = _svc.Terminals() }));
        }

        private async Task<LocalResponse> Health(LocalRequest r, CancellationToken ct)
        {
            var localId = r.QueryValue("local_id");
            if (string.IsNullOrEmpty(localId)) throw LocalApiException.Validation("local_id", "required");
            return LocalResponse.Json(await _svc.HealthAsync(localId!, false, ct).ConfigureAwait(false));
        }

        private async Task<LocalResponse> Purchase(LocalRequest r, CancellationToken ct)
        {
            var b = new BodyReader(r.JsonBody());
            var currency = b.OptionalString("currency", 3) ?? "UZS";
            if (currency != "UZS") throw LocalApiException.Validation("currency", "invalid_choice");
            var req = new CardPurchase
            {
                AttemptId = b.RequireGuid("attempt_id"),
                AmountTiyin = b.RequireLong("amount_tiyin", 1),
                Currency = currency,
                CashRegisterId = b.OptionalGuid("cash_register_id")?.ToString("D"),
                ClientEventId = b.OptionalGuid("client_event_id")?.ToString("D"),
                ReceiptSeq = b.OptionalLong("receipt_seq", 0),
            };
            var localId = b.RequireString("local_id", 64);
            return ToResponse(await _svc.PurchaseAsync(localId, req, ct).ConfigureAwait(false));
        }

        private async Task<LocalResponse> Refund(LocalRequest r, CancellationToken ct)
        {
            var b = new BodyReader(r.JsonBody());
            var req = new CardRefund
            {
                AttemptId = b.RequireGuid("attempt_id"),
                AmountTiyin = b.RequireLong("amount_tiyin", 1),
                OriginalRrn = b.OptionalString("original_rrn", 32),
                OriginalAttemptId = b.OptionalGuid("original_attempt_id"),
            };
            return ToResponse(await _svc.RefundAsync(b.RequireString("local_id", 64), req, ct).ConfigureAwait(false));
        }

        private async Task<LocalResponse> Void(LocalRequest r, CancellationToken ct)
        {
            var b = new BodyReader(r.JsonBody());
            var req = new CardVoid
            {
                AttemptId = b.RequireGuid("attempt_id"),
                AmountTiyin = b.RequireLong("amount_tiyin", 1),
                OriginalRrn = b.OptionalString("original_rrn", 32),
                OriginalAttemptId = b.OptionalGuid("original_attempt_id"),
            };
            return ToResponse(await _svc.VoidAsync(b.RequireString("local_id", 64), req, ct).ConfigureAwait(false));
        }

        private async Task<LocalResponse> Tx(LocalRequest r, CancellationToken ct)
        {
            if (!Guid.TryParse(r.RouteValues["attempt_id"], out var id)) throw LocalApiException.Validation("attempt_id", "uuid");
            return ToResponse(await _svc.GetTxAsync(id.ToString("D"), ct).ConfigureAwait(false));
        }

        private async Task<LocalResponse> CancelPending(LocalRequest r, CancellationToken ct)
        {
            var b = new BodyReader(r.JsonBody());
            var status = await _svc.CancelPendingAsync(b.RequireGuid("attempt_id").ToString("D"), ct).ConfigureAwait(false);
            return LocalResponse.Json(new { status });
        }

        private async Task<LocalResponse> Settlement(LocalRequest r, CancellationToken ct)
        {
            var b = new BodyReader(r.JsonBody());
            return LocalResponse.Json(await _svc.SettlementAsync(b.RequireString("local_id", 64), ct).ConfigureAwait(false));
        }

        internal static LocalResponse ToResponse(CardCallResult c)
        {
            if (c.Status == 200) return LocalResponse.Json(c.Tx);
            if (c.Status == 202) return LocalResponse.Json(new { attempt_id = c.AttemptId }, 202);
            return LocalResponse.Error(c.Status, c.ErrorCode!, c.Params);
        }
    }

    /// <summary>Server tasks <c>card.status</c> / <c>card.settlement</c> (21 §16) and the <c>card_terminal</c> capability (34 §14.2).</summary>
    public sealed class CardTaskHandler : IAgentTaskHandler, ICapabilityProvider
    {
        private static readonly string[] KindList = { "card.status", "card.settlement" };
        private static readonly StrictObject TerminalRef = new StrictObject()
            .Required("card_terminal_id", StrictObject.IsUuidOrNull)
            .Required("local_id", StrictObject.IsNonEmptyString);

        private static readonly StrictObject StatusSchema = new StrictObject()
            .Optional("terminals", e => e.ValueKind == JsonValueKind.Null || (e.ValueKind == JsonValueKind.Array && e.EnumerateArray().All(t => TerminalRef.Validate(t) is null)))
            .Optional("card_terminal_ids", StrictObject.IsUuidArrayOrNull);

        private static readonly StrictObject SettlementSchema = new StrictObject()
            .Required("card_terminal_id", StrictObject.IsUuid)
            .Required("local_id", StrictObject.IsNonEmptyString)
            .Optional("shift_id", StrictObject.IsUuidOrNull);

        private readonly CardTerminalService _svc;

        public CardTaskHandler(CardTerminalService svc)
        {
            _svc = svc;
        }

        public IReadOnlyCollection<string> Kinds => KindList;

        public string Family => "card_terminal";

        public object Describe()
        {
            var active = _svc.ActiveTerminals();
            if (active.Count == 0) return new { enabled = false, version = 0, devices = Array.Empty<object>() };
            var statuses = _svc.Terminals().ToDictionary(t => t.LocalId, t => t.Status, StringComparer.Ordinal);
            return new
            {
                enabled = true,
                version = 1,
                devices = active.Select(t => new
                {
                    local_id = t.Config.LocalId,
                    driver = t.Driver.Name,
                    host = t.Config.Host,
                    tid = t.Config.Tid,
                    status = statuses.TryGetValue(t.Config.LocalId, out var s) ? s : "offline",
                }).ToArray(),
            };
        }

        public string? ValidatePayload(string kind, JsonElement payload) =>
            kind == "card.status" ? StatusSchema.Validate(payload) : SettlementSchema.Validate(payload);

        public async Task<TaskExecution> ExecuteAsync(TaskContext context, JsonElement payload, CancellationToken ct)
        {
            if (context.Kind == "card.status")
            {
                var requested = new List<(string?, string)>();
                if (payload.TryGetProperty("terminals", out var ts) && ts.ValueKind == JsonValueKind.Array)
                {
                    foreach (var t in ts.EnumerateArray())
                    {
                        var cid = t.GetProperty("card_terminal_id");
                        requested.Add((cid.ValueKind == JsonValueKind.String ? cid.GetString() : null, t.GetProperty("local_id").GetString()!));
                    }
                }

                context.Progress("querying", 10);
                var (terminals, unresolved) = await _svc.StatusForServerAsync(requested, ct).ConfigureAwait(false);
                var exec = TaskExecution.Done(new { terminals, unresolved });
                _svc.MarkReported(unresolved.Select(u => u.AttemptId));
                return exec;
            }

            var cardTerminalId = payload.GetProperty("card_terminal_id").GetString();
            var localId = payload.GetProperty("local_id").GetString()!;
            context.Progress("querying", 10);
            try
            {
                var r = await _svc.SettlementAsync(localId, ct).ConfigureAwait(false);
                return TaskExecution.Done(new
                {
                    card_terminal_id = cardTerminalId,
                    local_id = localId,
                    tid = r.Tid,
                    batch_no = r.BatchNo,
                    count = r.Count,
                    total_tiyin = r.TotalTiyin,
                    refund_count = r.RefundCount,
                    refund_total_tiyin = r.RefundTotalTiyin,
                    by_scheme = r.ByScheme,
                    settled_at = r.SettledAt,
                });
            }
            catch (LocalApiException e)
            {
                return TaskExecution.Failed(ErrorObj.Of(
                    e.Code,
                    e.Code == LocalCodes.NotFound ? "card terminal is not configured on this agent" : "card terminal settlement failed",
                    e.Code == LocalCodes.CardTerminalUnreachable || e.Code == LocalCodes.CardTerminalBusy,
                    e.Code == LocalCodes.NotFound ? "payload.local_id" : null));
            }
        }
    }
}

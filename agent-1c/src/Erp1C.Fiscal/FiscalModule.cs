using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Core.Contracts;
using Erp1C.Core.Errors;
using Erp1C.Core.Hosting;

namespace Erp1C.Fiscal
{
    /// <summary>Local API <c>/v1/fiscal/*</c> (21 §16.1), server tasks <c>fiscal.*</c> (21 §16) and the <c>fiscal</c> capability (34 §14.2).</summary>
    public sealed class FiscalModule : ILocalApiModule, IAgentTaskHandler, ICapabilityProvider
    {
        private static readonly string[] KindList = { "fiscal.status", "fiscal.resend_unsent", "fiscal.zreport" };
        private static readonly string[] SaleKinds = { "sale", "debt_settlement", "credit_sale" };
        private static readonly string[] PaymentForms = { "cash", "card", "qr", "mixed" };
        private static readonly string[] CardTypes = { "personal", "corporate", "social", "unknown" };
        private static readonly Regex MaskRe = new Regex("^[0-9]{4}\\*+[0-9]{4}$", RegexOptions.CultureInvariant);

        private static readonly StrictObject RegisterTaskSchema = new StrictObject()
            .Required("cash_register_id", StrictObject.IsUuid)
            .Optional("local_id", e => e.ValueKind == JsonValueKind.Null || StrictObject.IsNonEmptyString(e));

        private static readonly StrictObject ZTaskSchema = new StrictObject()
            .Required("cash_register_id", StrictObject.IsUuid)
            .Optional("local_id", e => e.ValueKind == JsonValueKind.Null || StrictObject.IsNonEmptyString(e))
            .Required("shift_id", StrictObject.IsUuidOrNull);

        private readonly FiscalService _svc;

        public FiscalModule(FiscalService svc)
        {
            _svc = svc;
        }

        public FiscalService Service => _svc;

        // ---------------------------------------------------------------- capability

        public string Family => "fiscal";

        public object Describe()
        {
            var active = _svc.Active();
            if (active.Count == 0) return new { enabled = false, version = 0, provider = (string?)null, devices = Array.Empty<object>() };
            return new
            {
                enabled = true,
                version = 1,
                provider = active[0].Bridge.Provider,
                devices = active.Select(a => new { local_id = a.Device.LocalId, provider = a.Bridge.Provider, status = "ok" }).ToArray(),
            };
        }

        // ---------------------------------------------------------------- local API

        public IEnumerable<LocalRoute> Routes => new[]
        {
            new LocalRoute("POST", "/v1/fiscal/open-shift", OpenShift),
            new LocalRoute("POST", "/v1/fiscal/close-shift", CloseShift),
            new LocalRoute("POST", "/v1/fiscal/sale", Sale),
            new LocalRoute("POST", "/v1/fiscal/refund", Refund),
            new LocalRoute("GET", "/v1/fiscal/device-status", DeviceStatus),
            new LocalRoute("GET", "/v1/fiscal/unsent", Unsent),
            new LocalRoute("POST", "/v1/fiscal/resend", Resend),
        };

        private static CashRegisterRef ReadRegister(BodyReader b)
        {
            var r = b.Child("cash_register");
            return new CashRegisterRef { CashRegisterId = r.RequireGuid("cash_register_id").ToString("D"), LocalId = r.RequireString("local_id", 64) };
        }

        private async Task<LocalResponse> OpenShift(LocalRequest r, CancellationToken ct)
        {
            var b = new BodyReader(r.JsonBody());
            var reg = ReadRegister(b);
            var res = await _svc.OpenShiftAsync(reg, b.RequireLong("shift_no", 1), b.OptionalString("cashier_name", 128) ?? string.Empty, ct).ConfigureAwait(false);
            return LocalResponse.Json(res);
        }

        private async Task<LocalResponse> CloseShift(LocalRequest r, CancellationToken ct)
        {
            var b = new BodyReader(r.JsonBody());
            var reg = ReadRegister(b);
            return LocalResponse.Json(await _svc.CloseShiftAsync(reg, b.RequireLong("shift_no", 1), ct).ConfigureAwait(false));
        }

        private Task<LocalResponse> Sale(LocalRequest r, CancellationToken ct) => Receipt(r, false, ct);

        private Task<LocalResponse> Refund(LocalRequest r, CancellationToken ct) => Receipt(r, true, ct);

        private async Task<LocalResponse> Receipt(LocalRequest r, bool refund, CancellationToken ct)
        {
            var body = r.JsonBody();
            var payload = ParseReceipt(new BodyReader(body), refund);
            return LocalResponse.Json(await _svc.RegisterAsync(payload, body, refund, ct).ConfigureAwait(false));
        }

        /// <summary>Validates a 21 §16.1 FiscalReceiptPayload; integers only for money (tiyin) and quantity (milli).</summary>
        internal static FiscalReceiptPayload ParseReceipt(BodyReader b, bool refund)
        {
            var p = new FiscalReceiptPayload
            {
                CashRegister = ReadRegister(b),
                ReceiptSeq = b.RequireLong("receipt_seq", 0),
                Kind = b.RequireString("kind", 32),
            };
            if (refund ? p.Kind != "return" : !SaleKinds.Contains(p.Kind)) throw LocalApiException.Validation("kind", "invalid_choice");

            var items = b.OptionalArray("items") ?? throw LocalApiException.Validation("items", "required");
            var i = 0;
            foreach (var it in items.EnumerateArray())
            {
                if (it.ValueKind != JsonValueKind.Object) throw LocalApiException.Validation("items[" + i + "]", "object");
                var ib = new BodyReader(it);
                var item = new FiscalItem
                {
                    Name = ib.RequireString("name", 256),
                    Mxik = ib.OptionalString("mxik", 17),
                    PackageCode = ib.OptionalString("package_code", 32),
                    UnitCode = ib.OptionalString("unit_code", 32),
                    QtyMilli = ib.RequireLong("qty_milli", 1),
                    PriceTiyin = ib.RequireLong("price_tiyin", 0),
                    AmountTiyin = ib.RequireLong("amount_tiyin", 0),
                    VatTiyin = ib.OptionalLong("vat_tiyin", 0) ?? 0,
                    VatRate = VatRate(it),
                };
                if (item.Mxik != null && !Regex.IsMatch(item.Mxik, "^[0-9]{17}$")) throw LocalApiException.Validation("items[" + i + "].mxik", "mxik");
                if (ib.OptionalArray("marking_codes") is JsonElement codes)
                {
                    foreach (var c in codes.EnumerateArray())
                    {
                        if (c.ValueKind != JsonValueKind.String) throw LocalApiException.Validation("items[" + i + "].marking_codes", "string");
                        item.MarkingCodes.Add(c.GetString()!);
                    }
                }

                p.Items.Add(item);
                i++;
            }

            if (p.Items.Count == 0) throw LocalApiException.Validation("items", "required");

            var pay = b.Child("payments");
            p.Payments = new FiscalPayments
            {
                PaymentForm = pay.RequireString("payment_form", 16),
                CashTiyin = pay.OptionalLong("cash_tiyin", 0) ?? 0,
                CardTiyin = pay.OptionalLong("card_tiyin", 0) ?? 0,
                QrTiyin = pay.OptionalLong("qr_tiyin", 0) ?? 0,
                CardType = pay.OptionalString("card_type", 16),
                CardMask = pay.OptionalString("card_mask", 32),
                Rrn = pay.OptionalString("rrn", 32),
            };
            if (!PaymentForms.Contains(p.Payments.PaymentForm)) throw LocalApiException.Validation("payments.payment_form", "invalid_choice");
            if (p.Payments.CardType != null && !CardTypes.Contains(p.Payments.CardType)) throw LocalApiException.Validation("payments.card_type", "invalid_choice");

            // PCI (21 §9.4): only a 4+4 mask is accepted — never a card number.
            if (p.Payments.CardMask != null && !MaskRe.IsMatch(p.Payments.CardMask)) throw LocalApiException.Validation("payments.card_mask", "mask");
            if (p.Payments.CashTiyin + p.Payments.CardTiyin + p.Payments.QrTiyin != p.TotalTiyin()) throw LocalApiException.Validation("payments", "sum_mismatch");

            if (refund)
            {
                var ri = b.Child("refund_info");
                p.RefundInfo = new RefundInfo
                {
                    FmTerminalId = ri.RequireString("fm_terminal_id", 32),
                    FmReceiptSeq = ri.RequireLong("fm_receipt_seq", 0),
                    FiscalSign = ri.RequireString("fiscal_sign", 32),
                };
            }

            return p;
        }

        private static string? VatRate(JsonElement item)
        {
            if (!item.TryGetProperty("vat_rate", out var v) || v.ValueKind == JsonValueKind.Null) return null;
            if (v.ValueKind == JsonValueKind.String) return v.GetString();
            if (v.ValueKind == JsonValueKind.Number && v.TryGetInt64(out var n)) return n.ToString(System.Globalization.CultureInfo.InvariantCulture);
            throw LocalApiException.Validation("vat_rate", "string");
        }

        private static string LocalIdQuery(LocalRequest r)
        {
            var id = r.QueryValue("local_id");
            if (string.IsNullOrEmpty(id)) throw LocalApiException.Validation("local_id", "required");
            return id!;
        }

        private async Task<LocalResponse> DeviceStatus(LocalRequest r, CancellationToken ct)
        {
            var s = await _svc.DeviceStatusAsync(LocalIdQuery(r), ct).ConfigureAwait(false);
            return LocalResponse.Json(new { fm_state = s.FmState, pending_count = s.PendingCount, oldest_unacked_at = s.OldestUnackedAt });
        }

        private async Task<LocalResponse> Unsent(LocalRequest r, CancellationToken ct) =>
            LocalResponse.Json(new { items = await _svc.UnsentAsync(LocalIdQuery(r), ct).ConfigureAwait(false) });

        private async Task<LocalResponse> Resend(LocalRequest r, CancellationToken ct)
        {
            var b = new BodyReader(r.JsonBody());
            return LocalResponse.Json(await _svc.ResendAsync(b.RequireString("local_id", 64), ct).ConfigureAwait(false));
        }

        // ---------------------------------------------------------------- server tasks

        public IReadOnlyCollection<string> Kinds => KindList;

        public string? ValidatePayload(string kind, JsonElement payload) =>
            kind == "fiscal.zreport" ? ZTaskSchema.Validate(payload) : RegisterTaskSchema.Validate(payload);

        public async Task<TaskExecution> ExecuteAsync(TaskContext context, JsonElement payload, CancellationToken ct)
        {
            var cashRegisterId = payload.GetProperty("cash_register_id").GetString()!;
            var localId = payload.TryGetProperty("local_id", out var l) && l.ValueKind == JsonValueKind.String ? l.GetString() : _svc.LocalIdFor(cashRegisterId);
            if (string.IsNullOrEmpty(localId))
            {
                return TaskExecution.Failed(ErrorObj.Of(LocalCodes.FiscalProviderError, "fiscal device of the cash register is unknown on this agent", false, "payload.local_id"));
            }

            context.Progress("querying", 10);
            try
            {
                switch (context.Kind)
                {
                    case "fiscal.status":
                    {
                        var s = await _svc.DeviceStatusAsync(localId!, ct).ConfigureAwait(false);
                        var acked = _svc.NewAcks(s.Acked);
                        var exec = TaskExecution.Done(new
                        {
                            cash_register_id = cashRegisterId,
                            fm_state = s.FmState,
                            pending_count = s.PendingCount,
                            oldest_unacked_at = s.OldestUnackedAt,
                            acked,
                        });
                        _svc.MarkAcksReported(acked);
                        return exec;
                    }

                    case "fiscal.resend_unsent":
                    {
                        var r = await _svc.ResendAsync(localId!, ct).ConfigureAwait(false);
                        _svc.MarkAcksReported(r.Acked);
                        return TaskExecution.Done(new { cash_register_id = cashRegisterId, sent = r.Sent, failed = r.Failed, acked = r.Acked });
                    }

                    default:
                    {
                        var shiftId = payload.GetProperty("shift_id");
                        var z = await _svc.ZReportAsync(localId!, ct).ConfigureAwait(false);
                        return TaskExecution.Done(new
                        {
                            cash_register_id = cashRegisterId,
                            shift_id = shiftId.ValueKind == JsonValueKind.String ? shiftId.GetString() : null,
                            fm_terminal_id = z.FmTerminalId,
                            z_number = z.ZNumber,
                            totals = z.Totals,
                            closed_at = z.ClosedAt,
                        });
                    }
                }
            }
            catch (LocalApiException e)
            {
                return TaskExecution.Failed(ErrorObj.Of(e.Code, "fiscal task failed: " + e.Code, e.Code == LocalCodes.FiscalProviderError, e.Code == LocalCodes.NotFound ? "payload.local_id" : null));
            }
        }
    }
}

using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Erp1C.Core.Hosting;
using Erp1C.Core.Masking;
using Erp1C.Core.Security;
using Erp1C.Core.Storage;
using Erp1C.Tests.Common;
using Shouldly;
using Xunit;

namespace Erp1C.Core.Tests
{
    public class SecretMaskerTests
    {
        [Theory]
        [InlineData("File=\"D:\\1C\\Shop\";Usr=\"ERP\";Pwd=\"secret\";", "secret")]
        [InlineData("password = hunter22", "hunter22")]
        [InlineData("Authorization: Bearer abc.def-ghi_jkl", "abc.def-ghi_jkl")]
        [InlineData("{\"client_assertion\":\"eyJhbGciOiJFZERTQSJ9.eyJpc3MiOiJ4In0.c2lnbmF0dXJlMTIz\"}", "c2lnbmF0dXJlMTIz")]
        [InlineData("access_token=AbCdEfGhIjKl", "AbCdEfGhIjKl")]
        [InlineData("\"local_token\":\"q1w2e3r4t5y6u7i8o9p0\"", "q1w2e3r4t5y6u7i8o9p0")]
        [InlineData("\"code\":\"123456\"", "123456")]
        [InlineData("card 8600123412345678 paid", "8600123412345678")]
        [InlineData("card 8600 1234 1234 5678 paid", "8600 1234 1234 5678")]
        public void Secrets_are_masked(string input, string secret)
        {
            var m = SecretMasker.Mask(input);
            m.ShouldNotContain(secret);
        }

        [Fact]
        public void Pan_keeps_first_and_last_four()
        {
            SecretMasker.Mask("pan 8600123412345678").ShouldBe("pan 8600********5678");
        }

        [Theory]
        [InlineData("rrn 123456789012 approved")]
        [InlineData("fiscal_sign 123456789012")]
        [InlineData("task 0192f0c4-7a00-7000-8000-0000000000cc started")]
        [InlineData("amount_tiyin 1500000")]
        public void Non_secrets_stay(string input)
        {
            SecretMasker.Mask(input).ShouldBe(input);
        }

        [Fact]
        public void Connect_string_keeps_location_only()
        {
            SecretMasker.Mask("File=\"D:\\1C\\Shop\";Usr=\"admin\";Pwd=\"x\";").ShouldBe("File=\"D:\\1C\\Shop\";***");
        }
    }

    public class PrivateLanTests
    {
        [Theory]
        [InlineData("10.0.0.5", true)]
        [InlineData("172.16.1.1", true)]
        [InlineData("172.31.255.255", true)]
        [InlineData("192.168.1.60", true)]
        [InlineData("172.32.0.1", false)]
        [InlineData("8.8.8.8", false)]
        [InlineData("127.0.0.1", false)]
        [InlineData("printer.local", false)]
        [InlineData("192.168.01.5", false)]
        [InlineData("192.168.1", false)]
        [InlineData("::1", false)]
        [InlineData("", false)]
        public void Only_rfc1918_ipv4(string host, bool ok) => PrivateLan.IsPrivateIPv4(host).ShouldBe(ok);
    }

    public class DeviceLaneTests
    {
        [Fact]
        public async Task Operations_run_one_at_a_time_in_arrival_order()
        {
            var lane = new DeviceLane("t1");
            var order = new List<int>();
            var first = await lane.EnterAsync(false, CancellationToken.None);
            var waiters = new List<Task>();
            for (var i = 1; i <= 3; i++)
            {
                var n = i;
                waiters.Add(Task.Run(async () =>
                {
                    await Task.Delay(n * 30);
                    using (await lane.EnterAsync(false, CancellationToken.None))
                    {
                        lock (order) order.Add(n);
                    }
                }));
            }

            await Task.Delay(200);
            order.ShouldBeEmpty();
            first.Dispose();
            await Task.WhenAll(waiters);
            order.ShouldBe(new[] { 1, 2, 3 });
        }

        [Fact]
        public async Task Exclusive_entry_fails_while_a_transaction_runs_or_waits()
        {
            var lane = new DeviceLane("t1");
            var tx = await lane.EnterAsync(true, CancellationToken.None);
            (await lane.TryEnterExclusiveAsync(CancellationToken.None)).ShouldBeNull();
            lane.HasTransaction.ShouldBeTrue();
            tx.Dispose();
            using var ok = await lane.TryEnterExclusiveAsync(CancellationToken.None);
            ok.ShouldNotBeNull();
        }

        [Fact]
        public async Task Different_devices_never_block_each_other()
        {
            var lanes = new DeviceLanes();
            using var a = await lanes.For("a").EnterAsync(true, CancellationToken.None);
            using var b = await lanes.For("b").TryEnterExclusiveAsync(CancellationToken.None);
            b.ShouldNotBeNull();
        }

        [Fact]
        public async Task Cancelled_waiter_leaves_the_queue()
        {
            var lane = new DeviceLane("t1");
            var held = await lane.EnterAsync(true, CancellationToken.None);
            using var cts = new CancellationTokenSource(50);
            await Should.ThrowAsync<OperationCanceledException>(() => lane.EnterAsync(true, cts.Token));
            held.Dispose();
            lane.HasTransaction.ShouldBeFalse();
            lane.IsBusy.ShouldBeFalse();
        }
    }

    public class JsonlFileTests
    {
        [Fact]
        public void Torn_last_line_is_ignored_and_next_append_starts_fresh()
        {
            using var dir = new TempDir();
            var f = new JsonlFile(dir.File("x.jsonl"));
            f.Append("{\"a\":1}");
            File.AppendAllText(f.Path, "{\"a\":2", new UTF8Encoding(false));
            f.ReadLines().ShouldBe(new[] { "{\"a\":1}" });
            f.Append("{\"a\":3}");
            // the torn fragment stays on its own (unparsable) line; the new record is intact
            f.ReadLines().ShouldBe(new[] { "{\"a\":1}", "{\"a\":2", "{\"a\":3}" });
        }

        [Fact]
        public void Rewrite_replaces_atomically()
        {
            using var dir = new TempDir();
            var f = new JsonlFile(dir.File("x.jsonl"));
            f.Append("1");
            f.Append("2");
            f.Rewrite(new[] { "2" });
            f.ReadLines().ShouldBe(new[] { "2" });
            File.Exists(f.Path + ".tmp").ShouldBeFalse();
        }
    }

    public class StrictObjectTests
    {
        private static JsonElement J(string s)
        {
            using var d = JsonDocument.Parse(s);
            return d.RootElement.Clone();
        }

        private static readonly StrictObject Schema = new StrictObject()
            .Required("cash_register_id", StrictObject.IsUuid)
            .Optional("local_id", StrictObject.IsNonEmptyString);

        [Fact]
        public void Valid_payload_passes() => Schema.Validate(J("{\"cash_register_id\":\"0192f0c4-7a00-7000-8000-000000000123\"}")).ShouldBeNull();

        [Fact]
        public void Unknown_member_fails() => Schema.Validate(J("{\"cash_register_id\":\"0192f0c4-7a00-7000-8000-000000000123\",\"x\":1}")).ShouldBe("payload.x");

        [Fact]
        public void Missing_required_fails() => Schema.Validate(J("{}")).ShouldBe("payload.cash_register_id");

        [Fact]
        public void Wrong_type_fails() => Schema.Validate(J("{\"cash_register_id\":5}")).ShouldBe("payload.cash_register_id");

        [Fact]
        public void Non_integer_numbers_are_detected()
        {
            StrictObject.HasNonIntegerNumber(J("{\"a\":[1,{\"b\":2.5}]}")).ShouldBeTrue();
            StrictObject.HasNonIntegerNumber(J("{\"a\":[1,{\"b\":2}]}")).ShouldBeFalse();
        }
    }
}

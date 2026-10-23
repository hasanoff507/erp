using System.Linq;
using System.Text.RegularExpressions;
using Erp1C.Core.Masking;

namespace Erp1C.CardTerminal
{
    /// <summary>
    /// Common card layer rules (34 §14.4, 21 §9.4): mask normalisation to <c>^[0-9]{4}\*+[0-9]{4}$</c> (a full PAN
    /// from a driver is dropped and turned into a mask), scheme from BIN when the driver did not give one, RRN
    /// format check, slip text masked. Track data / CVV / PIN never exist in <see cref="CardTxResult"/>.
    /// </summary>
    public static class CardNormalizer
    {
        private static readonly Regex MaskRe = new Regex("^[0-9]{4}\\*+[0-9]{4}$", RegexOptions.CultureInvariant);
        private static readonly Regex RrnRe = new Regex("^[0-9A-Za-z]{6,32}$", RegexOptions.CultureInvariant);
        private static readonly string[] Schemes = { "uzcard", "humo", "visa", "mastercard", "unionpay", "mir", "other" };
        private static readonly string[] CardTypes = { "personal", "corporate", "social", "unknown" };
        private static readonly string[] EntryModes = { "chip", "contactless", "magstripe", "fallback" };

        public static CardTxResult Normalize(CardTxResult raw, string attemptId, string kind)
        {
            var r = raw.Clone();
            r.AttemptId = attemptId;
            r.Kind = kind;
            var bin = BinOf(raw.CardMask);
            r.CardMask = NormalizeMask(raw.CardMask);
            r.CardScheme = Schemes.Contains(raw.CardScheme) ? raw.CardScheme : (bin != null ? SchemeFromBin(bin) : (r.CardMask != null ? "other" : null));
            r.CardType = CardTypes.Contains(raw.CardType) ? raw.CardType : null;
            r.EntryMode = EntryModes.Contains(raw.EntryMode) ? raw.EntryMode : null;
            r.Rrn = raw.Rrn != null && RrnRe.IsMatch(raw.Rrn) ? raw.Rrn : null;
            r.SlipText = raw.SlipText == null ? null : SecretMasker.Mask(raw.SlipText);
            r.DeclineMessage = raw.DeclineMessage == null ? null : SecretMasker.Mask(raw.DeclineMessage);
            return r;
        }

        /// <summary>First 4 + stars + last 4; a full PAN (13–19 digits) or a vendor mask like <c>860031******1234</c> both normalise.</summary>
        public static string? NormalizeMask(string? raw)
        {
            if (string.IsNullOrWhiteSpace(raw)) return null;
            var s = Regex.Replace(raw!, "[ -]", string.Empty);
            if (MaskRe.IsMatch(s) && s.Length >= 12) return s.Substring(0, 4) + new string('*', s.Length - 8) + s.Substring(s.Length - 4);
            if (Regex.IsMatch(s, "^[0-9]{13,19}$")) return s.Substring(0, 4) + new string('*', s.Length - 8) + s.Substring(s.Length - 4);
            var m = Regex.Match(s, "^([0-9]{4})[0-9]{0,4}[*Xx]+([0-9]{4})$");
            if (m.Success)
            {
                var len = s.Length;
                return m.Groups[1].Value + new string('*', len - 8) + m.Groups[2].Value;
            }

            return null;
        }

        /// <summary>BIN digits available before masking (memory only, never stored).</summary>
        public static string? BinOf(string? raw)
        {
            if (string.IsNullOrWhiteSpace(raw)) return null;
            var m = Regex.Match(raw!, "^([0-9]{4,8})");
            return m.Success ? m.Groups[1].Value : null;
        }

        public static string SchemeFromBin(string bin)
        {
            if (bin.StartsWith("8600", System.StringComparison.Ordinal) || bin.StartsWith("5614", System.StringComparison.Ordinal)) return "uzcard";
            if (bin.StartsWith("9860", System.StringComparison.Ordinal)) return "humo";
            if (bin.StartsWith("4", System.StringComparison.Ordinal)) return "visa";
            if (bin.Length >= 4)
            {
                var two = int.Parse(bin.Substring(0, 2), System.Globalization.CultureInfo.InvariantCulture);
                var four = int.Parse(bin.Substring(0, 4), System.Globalization.CultureInfo.InvariantCulture);
                if (four >= 2200 && four <= 2204) return "mir";
                if ((two >= 51 && two <= 55) || (four >= 2221 && four <= 2720)) return "mastercard";
                if (two == 62) return "unionpay";
            }

            return "other";
        }
    }
}

using System;
using System.Text.RegularExpressions;

namespace Erp1C.Core.Masking
{
    /// <summary>
    /// 34 §9.2 secret masking — applied to every log line before it reaches a file or the server, to diagnostics and
    /// to error texts. Store-agent additions (34 §14.4, 21 §9.4 PCI): the local API token and full card numbers
    /// (13–19 digits) are masked too; a PAN keeps only the first 4 and last 4 digits.
    /// </summary>
    public static class SecretMasker
    {
        private const RegexOptions Opts = RegexOptions.IgnoreCase | RegexOptions.CultureInvariant;
        private static readonly TimeSpan Timeout = TimeSpan.FromMilliseconds(250);

        private static readonly Regex ConnectString = new Regex(
            "\\b((?:File|Srvr)\\s*=\\s*\"[^\"]*\"\\s*;\\s*(?:Ref\\s*=\\s*\"[^\"]*\"\\s*;\\s*)?)Usr=.*", Opts, Timeout);

        private static readonly Regex Password = new Regex(
            "\\b(pwd|password|пароль)\\s*=\\s*(\"(?:[^\"]|\"\")*\"|[^;\\s]*)", Opts, Timeout);

        private static readonly Regex Bearer = new Regex("\\bbearer\\s+[A-Za-z0-9._~+/=-]+", Opts, Timeout);

        private static readonly Regex NamedSecret = new Regex(
            "\"?(client_assertion|access_token|device_code|assertion|password_protected|protected|local_token|token)\"?\\s*[:=]\\s*\"?[A-Za-z0-9._~+/=-]{8,}\"?",
            Opts,
            Timeout);

        private static readonly Regex Jws = new Regex("eyJ[A-Za-z0-9_-]{4,}\\.[A-Za-z0-9_-]{4,}\\.[A-Za-z0-9_-]{8,}", Opts, Timeout);

        private static readonly Regex PairingCode = new Regex("\"?(pairing_code|code)\"?\\s*[:=]\\s*\"?[0-9]{6}\"?", Opts, Timeout);

        // 13–19 digits, or a printed PAN in groups of 4 separated by a space/dash; never part of a longer token (UUIDs,
        // hex ids, other numbers).
        private static readonly Regex Pan = new Regex(
            "(?<![0-9A-Za-z_-])(?:[0-9]{13,19}|[0-9]{4}(?:[ -][0-9]{4}){2}[ -][0-9]{1,7})(?![0-9A-Za-z_-])", Opts, Timeout);

        public static string Mask(string? text)
        {
            if (string.IsNullOrEmpty(text)) return text ?? string.Empty;
            try
            {
                var s = ConnectString.Replace(text!, m => m.Groups[1].Value + "***");
                s = Password.Replace(s, "$1=***");
                s = Bearer.Replace(s, "Bearer ***");
                s = Jws.Replace(s, "***jws***");
                s = NamedSecret.Replace(s, "$1=***");
                s = PairingCode.Replace(s, "$1=***");
                s = Pan.Replace(s, m => MaskPan(m.Value));
                return s;
            }
            catch (RegexMatchTimeoutException)
            {
                return "***masking-timeout***";
            }
        }

        /// <summary>Keeps the first 4 and the last 4 digits of a card number: <c>8600********1234</c>.</summary>
        public static string MaskPan(string pan)
        {
            var digits = Regex.Replace(pan ?? string.Empty, "[^0-9]", string.Empty, RegexOptions.None, Timeout);
            if (digits.Length < 8) return new string('*', digits.Length);
            return digits.Substring(0, 4) + new string('*', digits.Length - 8) + digits.Substring(digits.Length - 4);
        }
    }
}

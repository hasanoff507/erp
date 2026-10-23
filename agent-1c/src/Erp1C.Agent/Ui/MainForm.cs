using System;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using Erp1C.Agent.App;
using Erp1C.Agent.Loops;
using Erp1C.Agent.Net;
using Erp1C.CardTerminal;
using Erp1C.Core.Security;
using Erp1C.Devices;
using Erp1C.Fiscal;
using QRCoder;

namespace Erp1C.Agent.Ui
{
    /// <summary>
    /// Minimal main window (34 §10): Holat (pairing with code + QR, status, unpair), Ulangan kassalar (POS local pairing
    /// code and paired devices), Uskunalar (printers / card terminals / fiscal devices, private LAN only). The UI never
    /// calls the network directly — only <see cref="AppHost"/>.
    /// </summary>
    public sealed class MainForm : Form
    {
        private readonly AppHost _host;
        private readonly Label _state = new Label { AutoSize = false, Dock = DockStyle.Top, Height = 48, Font = new Font(SystemFonts.MessageBoxFont.FontFamily, 11f) };
        private readonly Button _pair = new Button { Text = Texts.T("pair.button"), AutoSize = true };
        private readonly Button _unpair = new Button { Text = Texts.T("pair.unpair"), AutoSize = true };
        private readonly PairingPanel _pairing = new PairingPanel { Dock = DockStyle.Fill, Visible = false };
        private readonly Label _posCode = new Label { AutoSize = false, Dock = DockStyle.Top, Height = 40, Font = new Font(FontFamily.GenericMonospace, 14f, FontStyle.Bold) };
        private readonly ListBox _posList = new ListBox { Dock = DockStyle.Fill };
        private readonly ListBox _devList = new ListBox { Dock = DockStyle.Fill };
        private readonly System.Windows.Forms.Timer _timer = new System.Windows.Forms.Timer { Interval = 1000 };
        private CancellationTokenSource? _pairCts;

        public MainForm(AppHost host)
        {
            _host = host;
            Text = Texts.T("app.title") + " " + BuildInfo.Version;
            Width = 640;
            Height = 520;
            StartPosition = FormStartPosition.CenterScreen;
            AutoScaleMode = AutoScaleMode.Dpi;

            var tabs = new TabControl { Dock = DockStyle.Fill };
            tabs.TabPages.Add(StatusPage());
            tabs.TabPages.Add(PosPage());
            tabs.TabPages.Add(DevicesPage());
            Controls.Add(tabs);

            _host.StateChanged += (_, __) => BeginInvokeSafe(RefreshState);
            _host.Pairing.Changed += (_, __) => BeginInvokeSafe(RefreshPos);
            _timer.Tick += (_, __) =>
            {
                RefreshState();
                RefreshPosCode();
            };
            _timer.Start();
            RefreshState();
            RefreshPos();
            RefreshDevices();
        }

        private void BeginInvokeSafe(Action a)
        {
            if (IsHandleCreated && !IsDisposed) BeginInvoke(a);
        }

        private TabPage StatusPage()
        {
            var page = new TabPage(Texts.T("tab.status"));
            var buttons = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 40 };
            buttons.Controls.Add(_pair);
            buttons.Controls.Add(_unpair);
            _pair.Click += async (_, __) => await StartPairingAsync().ConfigureAwait(true);
            _unpair.Click += async (_, __) =>
            {
                if (MessageBox.Show(this, Texts.T("pair.confirm_unpair"), Text, MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;
                await _host.UnpairAsync("user").ConfigureAwait(true);
                RefreshState();
            };
            _pairing.NewCode += async (_, __) => await StartPairingAsync().ConfigureAwait(true);
            page.Controls.Add(_pairing);
            page.Controls.Add(buttons);
            page.Controls.Add(_state);
            return page;
        }

        private TabPage PosPage()
        {
            var page = new TabPage(Texts.T("tab.pos"));
            var buttons = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 40 };
            var code = new Button { Text = Texts.T("pos.new_code"), AutoSize = true };
            var remove = new Button { Text = Texts.T("pos.remove"), AutoSize = true };
            code.Click += (_, __) =>
            {
                _host.Pairing.NewCode();
                RefreshPosCode();
            };
            remove.Click += (_, __) =>
            {
                if (_posList.SelectedItem is string s && Guid.TryParse(s.Split(' ')[0], out var id)) _host.Pairing.Revoke(id.ToString("D"));
            };
            buttons.Controls.Add(code);
            buttons.Controls.Add(remove);
            page.Controls.Add(_posList);
            page.Controls.Add(buttons);
            page.Controls.Add(_posCode);
            return page;
        }

        private TabPage DevicesPage()
        {
            var page = new TabPage(Texts.T("tab.devices"));
            var buttons = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 40 };
            var addPrinter = new Button { Text = Texts.T("dev.add") + ": " + Texts.T("dev.printers"), AutoSize = true };
            var addTerminal = new Button { Text = Texts.T("dev.add") + ": " + Texts.T("dev.terminals"), AutoSize = true };
            var addFiscal = new Button { Text = Texts.T("dev.add") + ": " + Texts.T("dev.fiscal"), AutoSize = true };
            var remove = new Button { Text = Texts.T("dev.remove"), AutoSize = true };
            addPrinter.Click += (_, __) => AddDevice("printer");
            addTerminal.Click += (_, __) => AddDevice("terminal");
            addFiscal.Click += (_, __) => AddDevice("fiscal");
            remove.Click += (_, __) => RemoveDevice();
            buttons.Controls.AddRange(new Control[] { addPrinter, addTerminal, addFiscal, remove });
            page.Controls.Add(_devList);
            page.Controls.Add(buttons);
            return page;
        }

        private void RefreshState()
        {
            var s = _host.Settings.Current;
            _state.Text = _host.State switch
            {
                AgentState.NotPaired => Texts.T("state.not_paired"),
                AgentState.Online => Texts.F("state.online", s.TenantName ?? string.Empty),
                AgentState.Offline => Texts.F("state.offline", _host.OfflineSince?.ToLocalTime().ToString("HH:mm", CultureInfo.CurrentCulture) ?? "-"),
                AgentState.SubscriptionRestricted => Texts.T("state.restricted"),
                AgentState.UpdateRequired => Texts.T("state.update"),
                AgentState.Revoked => Texts.T("state.revoked"),
                AgentState.KeyUnavailable => Texts.T("state.key"),
                _ => Texts.T("state.connecting"),
            };
            if (_host.Clock.Skewed) _state.Text += Environment.NewLine + Texts.F("clock.skew", ((int)Math.Abs(_host.Clock.Offset.TotalMinutes)).ToString(CultureInfo.CurrentCulture));
            _pair.Visible = !s.IsPaired;
            _unpair.Visible = s.IsPaired;
        }

        private void RefreshPosCode()
        {
            var (code, exp) = _host.Pairing.CurrentCode();
            _posCode.Text = code is null ? string.Empty : Texts.F("pos.code", code) + "  " + exp.ToLocalTime().ToString("HH:mm:ss", CultureInfo.CurrentCulture);
        }

        private void RefreshPos()
        {
            _posList.Items.Clear();
            foreach (var d in _host.Pairing.Devices()) _posList.Items.Add(d.DeviceId + "  " + d.PairedAt);
            if (_posList.Items.Count == 0) _posList.Items.Add(Texts.T("pos.none"));
        }

        private void RefreshDevices()
        {
            _devList.Items.Clear();
            var d = _host.Settings.Current.Devices;
            foreach (var p in d.Printers) _devList.Items.Add("printer|" + p.LocalId + "|" + p.Name + " " + p.Address);
            foreach (var t in d.CardTerminals) _devList.Items.Add("terminal|" + t.LocalId + "|" + t.Name + " " + t.Driver + " " + t.Host + ":" + t.Port.ToString(CultureInfo.InvariantCulture));
            foreach (var f in d.Fiscal) _devList.Items.Add("fiscal|" + f.LocalId + "|" + f.Name + " " + f.Provider);
        }

        private void AddDevice(string kind)
        {
            using var dlg = new DeviceDialog(kind);
            if (dlg.ShowDialog(this) != DialogResult.OK) return;
            _host.Settings.Update(s =>
            {
                switch (kind)
                {
                    case "printer":
                        s.Devices.Printers.Add(new PrinterConfig { LocalId = dlg.Host + ":9100", Name = dlg.DeviceName, Host = dlg.Host, Port = 9100 });
                        break;
                    case "terminal":
                        s.Devices.CardTerminals.Add(new TerminalConfig { LocalId = Guid.NewGuid().ToString("D"), Name = dlg.DeviceName, Host = dlg.Host, Port = dlg.Port, Driver = dlg.Driver });
                        break;
                    default:
                        s.Devices.Fiscal.Add(new FiscalDeviceConfig { LocalId = Guid.NewGuid().ToString("D"), Name = dlg.DeviceName, Provider = dlg.Driver });
                        break;
                }
            });
            RefreshDevices();
        }

        private void RemoveDevice()
        {
            if (!(_devList.SelectedItem is string s)) return;
            var parts = s.Split('|');
            _host.Settings.Update(x =>
            {
                x.Devices.Printers.RemoveAll(p => parts[0] == "printer" && p.LocalId == parts[1]);
                x.Devices.CardTerminals.RemoveAll(t => parts[0] == "terminal" && t.LocalId == parts[1]);
                x.Devices.Fiscal.RemoveAll(f => parts[0] == "fiscal" && f.LocalId == parts[1]);
            });
            RefreshDevices();
        }

        private async Task StartPairingAsync()
        {
            _pairCts?.Cancel();
            _pairCts = new CancellationTokenSource();
            var ct = _pairCts.Token;
            try
            {
                var auth = await _host.BeginPairingAsync(ct).ConfigureAwait(true);
                _pairing.Show(auth);
                var tenant = await _host.CompletePairingAsync(ct).ConfigureAwait(true);
                _pairing.ShowMessage(Texts.F("pair.done", tenant));
            }
            catch (PairingException e)
            {
                _pairing.ShowMessage(Texts.T(e.Reason == "denied" ? "pair.denied" : e.Reason == "rate_limited" ? "pair.rate_limited" : "pair.expired"));
            }
            catch (ApiException e) when (e.Status == 429)
            {
                _pairing.ShowMessage(Texts.T("pair.rate_limited"));
            }
            catch (NetworkException e)
            {
                _pairing.ShowMessage(e.Message.IndexOf("SSL", StringComparison.OrdinalIgnoreCase) >= 0 ? Texts.T("tls.win7") : e.Message);
            }
            catch (OperationCanceledException)
            {
            }

            RefreshState();
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            // Closing the window keeps the agent in the tray.
            if (e.CloseReason == CloseReason.UserClosing)
            {
                e.Cancel = true;
                Hide();
                return;
            }

            base.OnFormClosing(e);
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                _timer.Dispose();
                _pairCts?.Dispose();
            }

            base.Dispose(disposing);
        }
    }

    /// <summary>Pairing code + QR of <c>verification_uri_complete</c> + [Brauzerda ochish] + timer (34 §5.3).</summary>
    public sealed class PairingPanel : Panel
    {
        private readonly Label _code = new Label { Dock = DockStyle.Top, Height = 56, Font = new Font(FontFamily.GenericMonospace, 26f, FontStyle.Bold), TextAlign = ContentAlignment.MiddleCenter };
        private readonly Label _hint = new Label { Dock = DockStyle.Top, Height = 56, Text = Texts.T("pair.code_hint") };
        private readonly PictureBox _qr = new PictureBox { Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom };
        private readonly Label _timer = new Label { Dock = DockStyle.Bottom, Height = 24 };
        private readonly Button _open = new Button { Text = Texts.T("pair.open_browser"), Dock = DockStyle.Bottom };
        private readonly Button _new = new Button { Text = Texts.T("pair.new_code"), Dock = DockStyle.Bottom, Visible = false };
        private readonly System.Windows.Forms.Timer _tick = new System.Windows.Forms.Timer { Interval = 1000 };
        private DateTime _expires;
        private string? _url;

        public PairingPanel()
        {
            Controls.Add(_qr);
            Controls.Add(_open);
            Controls.Add(_new);
            Controls.Add(_timer);
            Controls.Add(_hint);
            Controls.Add(_code);
            _open.Click += (_, __) =>
            {
                // Only our own server origin is opened (34 §5.3).
                if (_url != null && _url.StartsWith(BuildInfo.ServerBase + "/", StringComparison.OrdinalIgnoreCase))
                {
                    using var p = Process.Start(new ProcessStartInfo(_url) { UseShellExecute = true });
                }
            };
            _new.Click += (_, __) => NewCode?.Invoke(this, EventArgs.Empty);
            _tick.Tick += (_, __) =>
            {
                var left = _expires - DateTime.UtcNow;
                _timer.Text = left > TimeSpan.Zero ? Texts.F("pair.timer", left.ToString(@"mm\:ss", CultureInfo.InvariantCulture)) : Texts.T("pair.expired");
            };
        }

        public event EventHandler? NewCode;

        public void Show(Core.Contracts.DeviceAuthorizationResponse auth)
        {
            Visible = true;
            _new.Visible = false;
            _code.Text = auth.UserCode;
            _url = auth.VerificationUriComplete ?? auth.VerificationUri;
            _expires = DateTime.UtcNow.AddSeconds(auth.ExpiresIn);
            _qr.Image?.Dispose();
            using (var gen = new QRCodeGenerator())
            using (var data = gen.CreateQrCode(_url, QRCodeGenerator.ECCLevel.M))
            {
                var png = new PngByteQRCode(data).GetGraphic(8);
                using var ms = new MemoryStream(png);
                _qr.Image = Image.FromStream(ms);
            }

            _tick.Start();
        }

        public void ShowMessage(string text)
        {
            _tick.Stop();
            _timer.Text = text;
            _new.Visible = true;
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                _tick.Dispose();
                _qr.Image?.Dispose();
            }

            base.Dispose(disposing);
        }
    }

    /// <summary>Add-device dialog — only private LAN IPv4 hosts are accepted (34 §14.3/§14.4).</summary>
    public sealed class DeviceDialog : Form
    {
        private readonly TextBox _name = new TextBox { Width = 260 };
        private readonly TextBox _host = new TextBox { Width = 260 };
        private readonly NumericUpDown _port = new NumericUpDown { Minimum = 1, Maximum = 65535, Value = 9100, Width = 100 };
        private readonly ComboBox _driver = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 260 };
        private readonly string _kind;

        public DeviceDialog(string kind)
        {
            _kind = kind;
            Text = Texts.T(kind == "printer" ? "dev.printers" : kind == "terminal" ? "dev.terminals" : "dev.fiscal");
            FormBorderStyle = FormBorderStyle.FixedDialog;
            StartPosition = FormStartPosition.CenterParent;
            AutoSize = true;
            AutoSizeMode = AutoSizeMode.GrowAndShrink;
            var grid = new TableLayoutPanel { ColumnCount = 2, AutoSize = true, Dock = DockStyle.Fill, Padding = new Padding(8) };
            void Row(string label, Control c)
            {
                grid.Controls.Add(new Label { Text = Texts.T(label), AutoSize = true, Anchor = AnchorStyles.Left });
                grid.Controls.Add(c);
            }

            Row("dev.name", _name);
            if (kind != "fiscal") Row("dev.host", _host);
            if (kind == "terminal") Row("dev.port", _port);
            if (kind == "terminal") _driver.Items.Add("fake");
            if (kind == "fiscal") _driver.Items.AddRange(new object[] { "fake", "multikassa_local", "fiscaldrive_local" });
            if (kind != "printer")
            {
                _driver.SelectedIndex = 0;
                Row(kind == "fiscal" ? "dev.provider" : "dev.driver", _driver);
            }

            var ok = new Button { Text = Texts.T("common.ok"), DialogResult = DialogResult.None, AutoSize = true };
            var cancel = new Button { Text = Texts.T("common.cancel"), DialogResult = DialogResult.Cancel, AutoSize = true };
            ok.Click += (_, __) => Validate(ok);
            grid.Controls.Add(ok);
            grid.Controls.Add(cancel);
            Controls.Add(grid);
            AcceptButton = ok;
            CancelButton = cancel;
        }

        public string DeviceName => _name.Text.Trim();

        public string Host => _host.Text.Trim();

        public int Port => (int)_port.Value;

        public string Driver => _driver.SelectedItem as string ?? string.Empty;

        private void Validate(Button ok)
        {
            if (_kind != "fiscal" && !PrivateLan.IsPrivateIPv4(Host))
            {
                MessageBox.Show(this, Texts.T("dev.invalid_host"), Text, MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            DialogResult = DialogResult.OK;
            _ = ok;
            Close();
        }
    }
}

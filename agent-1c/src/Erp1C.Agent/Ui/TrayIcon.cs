using System;
using System.Drawing;
using System.Windows.Forms;
using Erp1C.Agent.App;
using Erp1C.Agent.Loops;

namespace Erp1C.Agent.Ui
{
    /// <summary>Tray icon and menu (34 §10.2): green online, yellow offline/restricted/skew, red not paired/revoked.</summary>
    public sealed class TrayIcon : IDisposable
    {
        private readonly NotifyIcon _icon;
        private readonly AppHost _host;
        private readonly MainForm _form;

        public TrayIcon(AppHost host, MainForm form)
        {
            _host = host;
            _form = form;
            var menu = new ContextMenuStrip();
            menu.Items.Add(Texts.T("tray.open"), null, (_, __) => ShowForm());
            menu.Items.Add(Texts.T("tray.pos_code"), null, (_, __) =>
            {
                var (code, _) = _host.Pairing.NewCode();
                Show(Texts.F("pos.code", code));
            });
            menu.Items.Add(Texts.T("tray.diag"), null, (_, __) => SaveDiagnostics());
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add(Texts.T("tray.exit"), null, (_, __) => Application.Exit());
            _icon = new NotifyIcon { ContextMenuStrip = menu, Visible = true, Text = Texts.T("app.title") };
            _icon.DoubleClick += (_, __) => ShowForm();
            _host.StateChanged += (_, __) => Refresh();
            Refresh();
        }

        private void ShowForm()
        {
            _form.Show();
            _form.WindowState = FormWindowState.Normal;
            _form.Activate();
        }

        public void Show(string text) => _icon.ShowBalloonTip(5000, Texts.T("app.title"), text, ToolTipIcon.Info);

        private void SaveDiagnostics()
        {
            using var dlg = new FolderBrowserDialog();
            if (dlg.ShowDialog() != DialogResult.OK) return;
            var zip = _host.Diagnostics.Build(dlg.SelectedPath, 3, true);
            Show(Texts.F("diag.saved", zip));
        }

        private void Refresh()
        {
            var state = _host.State;
            var color = state switch
            {
                AgentState.Online => _host.Clock.Skewed ? Color.Goldenrod : Color.SeaGreen,
                AgentState.Offline => Color.Goldenrod,
                AgentState.SubscriptionRestricted => Color.Goldenrod,
                AgentState.Connecting => Color.Goldenrod,
                _ => Color.Firebrick,
            };
            var old = _icon.Icon;
            _icon.Icon = MakeIcon(color);
            old?.Dispose();
        }

        private static Icon MakeIcon(Color c)
        {
            using var bmp = new Bitmap(16, 16);
            using (var g = Graphics.FromImage(bmp))
            using (var b = new SolidBrush(c))
            {
                g.Clear(Color.Transparent);
                g.FillEllipse(b, 1, 1, 14, 14);
            }

            var h = bmp.GetHicon();
            using var tmp = Icon.FromHandle(h);
            var icon = (Icon)tmp.Clone();
            NativeMethods.DestroyIcon(h);
            return icon;
        }

        public void Dispose()
        {
            _icon.Visible = false;
            _icon.Icon?.Dispose();
            _icon.Dispose();
        }

        private static class NativeMethods
        {
            [System.Runtime.InteropServices.DllImport("user32.dll", SetLastError = true)]
            [System.Runtime.InteropServices.DefaultDllImportSearchPaths(System.Runtime.InteropServices.DllImportSearchPath.System32)]
            [return: System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.Bool)]
            internal static extern bool DestroyIcon(IntPtr handle);
        }
    }
}

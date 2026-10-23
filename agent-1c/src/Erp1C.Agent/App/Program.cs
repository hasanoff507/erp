using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Security.Principal;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using Erp1C.Agent.State;
using Erp1C.Agent.Ui;

namespace Erp1C.Agent.App
{
    /// <summary>Command line (34 §7.3 #1).</summary>
    public sealed class CommandLine
    {
        public bool Hidden { get; private set; }

        public bool AfterUpdate { get; private set; }

        public bool Shutdown { get; private set; }

        public bool UninstallHook { get; private set; }

        public bool KeepSettings { get; private set; }

        public string? SaveDiagnostics { get; private set; }

        public string? Server { get; private set; }

        public static CommandLine Parse(IReadOnlyList<string> args)
        {
            var c = new CommandLine();
            for (var i = 0; i < args.Count; i++)
            {
                switch (args[i])
                {
                    case "--hidden": c.Hidden = true; break;
                    case "--after-update": c.AfterUpdate = true; break;
                    case "--shutdown": c.Shutdown = true; break;
                    case "--uninstall-hook": c.UninstallHook = true; break;
                    case "--keep-settings": c.KeepSettings = true; break;
                    case "--save-diagnostics" when i + 1 < args.Count: c.SaveDiagnostics = args[++i]; break;
                    case "--server" when i + 1 < args.Count: c.Server = args[++i]; break;
                }
            }

            return c;
        }
    }

    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            var cl = CommandLine.Parse(args);
            if (cl.Server != null) BuildInfo.OverrideServerBase(cl.Server); // DEV build only (throws otherwise)

            var sid = WindowsIdentity.GetCurrent().User?.Value ?? "user";
            using var exitSignal = new EventWaitHandle(false, EventResetMode.AutoReset, "Local\\ErpOneCAgent-Exit-" + sid);
            if (cl.Shutdown)
            {
                exitSignal.Set();
                return 0;
            }

            if (cl.UninstallHook) return Uninstall.Run(cl.KeepSettings, exitSignal);

            using var mutex = new Mutex(false, "Global\\ErpOneCAgent-" + sid, out _);
            using var showSignal = new EventWaitHandle(false, EventResetMode.AutoReset, "Local\\ErpOneCAgent-Show-" + sid);
            bool owned;
            try
            {
                owned = mutex.WaitOne(0);
            }
            catch (AbandonedMutexException)
            {
                owned = true;
            }

            if (!owned)
            {
                showSignal.Set(); // single instance (34 §3.7)
                return 0;
            }

            // Session-local marker the installer waits on (34 §4.2 — Inno cannot compute the user SID).
            using var running = new Mutex(true, "Local\\ErpOneCAgent-Running", out _);
            try
            {
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                using var host = new AppHost(new AgentPaths()) { HiddenStart = cl.Hidden };
                Texts.Language = host.Settings.Current.UiLanguage == "ru" ? "ru" : "uz";
                if (cl.SaveDiagnostics != null)
                {
                    host.Diagnostics.Build(cl.SaveDiagnostics, 3, true);
                    return 0;
                }

                host.Start();
                using var form = new MainForm(host);
                using var tray = new TrayIcon(host, form);
                host.ExitRequested += (_, __) => form.BeginInvoke(new Action(Application.Exit));
                if (!cl.Hidden || !host.Settings.Current.IsPaired) form.Show();
                if (cl.Hidden && !host.Settings.Current.IsPaired) tray.Show(Texts.T("state.not_paired"));

                // Exit / show signals from the installer, --shutdown and a second instance.
                var watcher = new Thread(() =>
                {
                    var handles = new WaitHandle[] { exitSignal, showSignal };
                    while (true)
                    {
                        var i = WaitHandle.WaitAny(handles);
                        if (i == 0)
                        {
                            form.BeginInvoke(new Action(Application.Exit));
                            return;
                        }

                        form.BeginInvoke(new Action(() =>
                        {
                            form.Show();
                            form.Activate();
                        }));
                    }
                }) { IsBackground = true };
                watcher.Start();
                Application.Run();
                host.StopAsync().Wait(TimeSpan.FromSeconds(5));
                return 0;
            }
            finally
            {
                mutex.ReleaseMutex();
            }
        }
    }

    /// <summary><c>--uninstall-hook [--keep-settings]</c> (34 §4.3).</summary>
    internal static class Uninstall
    {
        public static int Run(bool keepSettings, EventWaitHandle exitSignal)
        {
            exitSignal.Set();
            Thread.Sleep(TimeSpan.FromSeconds(3));
            var paths = new AgentPaths();
            try
            {
                using (var host = new AppHost(paths))
                {
                    if (host.Settings.Current.IsPaired)
                    {
                        host.Start();
                        Task.Run(() => host.UnpairAsync("uninstall")).Wait(TimeSpan.FromSeconds(10));
                    }
                }
            }
            catch (AggregateException)
            {
                // A-10 failed — the owner can revoke in BO-14; continue the clean-up.
            }

            foreach (var f in new[] { paths.AgentKey, paths.Results, paths.Actions, paths.LogsOutbox, paths.LocalPairs })
            {
                if (System.IO.File.Exists(f)) System.IO.File.Delete(f);
            }

            if (System.IO.Directory.Exists(paths.Updates)) System.IO.Directory.Delete(paths.Updates, true);
            if (System.IO.Directory.Exists(paths.Diag)) System.IO.Directory.Delete(paths.Diag, true);
            if (!keepSettings && System.IO.Directory.Exists(paths.Root))
            {
                System.IO.Directory.Delete(paths.Root, true);
            }

            return 0;
        }

        private static string Now() => DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture);
    }
}

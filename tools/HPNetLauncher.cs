using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class HPNetLauncher
{
    private static readonly Dictionary<string, string> Scripts =
        new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { "HPNet PDF Downloader", "HPNet-PDF-Downloader.ps1" },
            { "HPNet Upload VB Du Thao", "HPNet-Upload-VB-Du-Thao.ps1" },
            { "HPNet Duyet VB Du Thao", "HPNet-Duyet-VB-Du-Thao.ps1" },
        };

    [STAThread]
    private static int Main()
    {
        try
        {
            string executable = Path.GetFileNameWithoutExtension(Application.ExecutablePath);
            string scriptName;
            if (!Scripts.TryGetValue(executable, out scriptName))
                throw new InvalidOperationException("Tên tệp khởi chạy HPNet không được nhận diện.");

            string directory = AppDomain.CurrentDomain.BaseDirectory;
            string script = Path.Combine(directory, scriptName);
            if (!File.Exists(script))
                throw new FileNotFoundException("Không tìm thấy tệp giao diện HPNet.", script);

            string windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
            string powershell = Path.Combine(windows, "System32", "WindowsPowerShell", "v1.0", "powershell.exe");
            var start = new ProcessStartInfo
            {
                FileName = powershell,
                Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + script.Replace("\"", "\\\"") + "\"",
                WorkingDirectory = directory,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            using (Process process = Process.Start(start))
            {
                process.WaitForExit();
                return process.ExitCode;
            }
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "Không mở được công cụ HPNet", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}

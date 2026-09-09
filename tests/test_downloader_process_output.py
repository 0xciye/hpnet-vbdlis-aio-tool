"""Exercise the actual PowerShell output reader without opening HPNet."""
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell")
@pytest.mark.parametrize("tool,script_name,reader_name,end_marker", [
    ("Downloader/HPNet PDF Downloader - VNEID APP", "HPNet-PDF-Downloader.ps1", "Read-DownloaderOutput", "function Normalize-CommuneCode"),
    ("Duyet/HPNet Duyet VB Du Thao - VNEID APP", "HPNet-Duyet-VB-Du-Thao.ps1", "Read-ApprovalOutput", "function Find-HPNetRuntime"),
])
def test_downloader_reads_both_streams_and_keeps_exit_code(tmp_path, tool, script_name, reader_name, end_marker):
    source = (Path(__file__).resolve().parents[1] / "src/nodes_tools" / tool / script_name).read_text(encoding="utf-8-sig")
    reader = source[source.index("function " + reader_name):source.index(end_marker)]
    child = tmp_path / "child.ps1"
    child.write_text('1..120 | ForEach-Object { [Console]::Out.WriteLine("out-$_"); [Console]::Error.WriteLine("err-$_") }; [Console]::Out.Write("tail"); exit 7', encoding="utf-8-sig")
    harness = tmp_path / "test.ps1"
    harness.write_text("""param([string]$Child)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
""" + reader + """
$psi=New-Object Diagnostics.ProcessStartInfo
$psi.FileName='powershell.exe'
$psi.Arguments='-NoProfile -ExecutionPolicy Bypass -File "' + $Child + '"'
$psi.UseShellExecute=$false
$psi.CreateNoWindow=$true
$psi.RedirectStandardOutput=$true
$psi.RedirectStandardError=$true
$p=New-Object Diagnostics.Process
$p.StartInfo=$psi
$lines=New-Object 'System.Collections.Generic.List[string]'
try {
    $p.Start() | Out-Null
    Read-DownloaderOutput $p {param($line); $lines.Add($line)}
    if($lines.Count -ne 241 -or $p.ExitCode -ne 7){throw 'Output lost or exit code changed'}
    if(-not $lines.Contains('tail') -or -not $lines.Contains('[LỖI] err-120')){throw 'Final output missing'}
    Write-Output 'PROCESS_OUTPUT_PASS'
} finally { $p.Dispose() }
""".replace("Read-DownloaderOutput", reader_name), encoding="utf-8-sig")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness), str(child)], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert b"PROCESS_OUTPUT_PASS" in result.stdout

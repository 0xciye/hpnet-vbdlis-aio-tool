"""Exercise the actual PowerShell output reader without opening HPNet."""
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell")
def test_downloader_reads_both_streams_and_keeps_exit_code(tmp_path):
    source = (Path(__file__).resolve().parents[1] / "src/nodes_tools/Downloader/HPNet PDF Downloader - VNEID APP/HPNet-PDF-Downloader.ps1").read_text(encoding="utf-8-sig")
    reader = source[source.index("function Read-DownloaderOutput"):source.index("function Normalize-CommuneCode")]
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
""", encoding="utf-8-sig")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness), str(child)], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert b"PROCESS_OUTPUT_PASS" in result.stdout

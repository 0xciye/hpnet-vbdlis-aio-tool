$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$source = Join-Path $PSScriptRoot 'HPNetLauncher.cs'
$icon = Join-Path $projectRoot 'src\tools\vbdlis_excel_builder\resources\app_icon.ico'
if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) { throw 'Không tìm thấy trình biên dịch .NET Framework 64-bit.' }

$targets = @(
    'Downloader\HPNet PDF Downloader - VNEID APP\HPNet PDF Downloader.exe',
    'Upload\HPNet Upload VB Du Thao - VNEID APP\HPNet Upload VB Du Thao.exe',
    'Duyet\HPNet Duyet VB Du Thao - VNEID APP\HPNet Duyet VB Du Thao.exe'
)
foreach ($relative in $targets) {
    $output = Join-Path (Join-Path $projectRoot 'src\nodes_tools') $relative
    & $compiler /nologo /target:winexe /platform:anycpu /optimize+ "/win32icon:$icon" "/out:$output" $source
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $output -PathType Leaf)) { throw "Không tạo được $output" }
    $bytes = [IO.File]::ReadAllBytes($output)
    $peOffset = [BitConverter]::ToInt32($bytes, 0x3c)
    $subsystem = [BitConverter]::ToUInt16($bytes, $peOffset + 0x5c)
    if ($subsystem -ne 2) { throw "EXE không phải ứng dụng Windows GUI: $output" }
    Write-Host "HPNET_GUI_EXE_READY: $output"
}

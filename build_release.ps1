param([string]$ReleaseId = (Get-Date -Format 'yyyy.MM.dd-HHmmss'))
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
if ($ReleaseId -notmatch '^[a-zA-Z0-9._-]+$') { throw 'ReleaseId chi duoc gom chu, so, dau cham, gach ngang.' }
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Can tao .venv va cai docs\REQUIREMENTS_BUILD.txt truoc.' }
$releaseRoot = Join-Path $projectRoot "release\$ReleaseId"
$buildRoot = Join-Path $projectRoot "build\$ReleaseId"
if ((Test-Path -LiteralPath $releaseRoot) -or (Test-Path -LiteralPath $buildRoot)) {
    throw 'Thu muc phat hanh/build da ton tai. Chon ReleaseId moi; khong ghi de ban cu.'
}
$originalLocation = Get-Location
$oldPythonPath = $env:PYTHONPATH
$oldAppData = $env:APPDATA
$oldPlatform = $env:QT_QPA_PLATFORM
try {
    Set-Location -LiteralPath $projectRoot
    $env:PYTHONPATH = Join-Path $projectRoot 'src'
    & $python -X utf8 (Join-Path $projectRoot 'run_tests.py')
    if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
    New-Item -ItemType Directory -Path $releaseRoot, $buildRoot | Out-Null
    Set-Location -LiteralPath (Join-Path $projectRoot 'src')
    & $python -X utf8 -m PyInstaller HPNET_VBDLIS_Tools.spec --noconfirm --distpath $releaseRoot --workpath $buildRoot
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
    $appFolder = Join-Path $releaseRoot 'HPNET & VBDLIS Tools'
    $executable = Join-Path $appFolder 'HPNET & VBDLIS Tools.exe'
    $env:APPDATA = (New-Item -ItemType Directory -Path (Join-Path $buildRoot 'smoke-appdata')).FullName
    $env:QT_QPA_PLATFORM = 'offscreen'
    $smokeReport = Join-Path $releaseRoot 'frozen-smoke.json'
    $process = Start-Process -FilePath $executable -ArgumentList @('--smoke-test', '--smoke-report', ('"' + $smokeReport + '"')) -WorkingDirectory $buildRoot -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(60000)) {
        Stop-Process -Id $process.Id
        throw 'Packaged smoke test timed out.'
    }
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $smokeReport)) { throw 'Packaged smoke test failed. See frozen-smoke.json.' }
    $result = Get-Content -LiteralPath $smokeReport -Raw | ConvertFrom-Json
    if ($result.status -ne 'PASS') { throw $result.error }
    & $python -X utf8 (Join-Path $projectRoot 'verify_release.py') --folder $appFolder
    if ($LASTEXITCODE -ne 0) { throw 'Packaged worker/resource verification failed.' }
    # User ZIP contains only runtime resources; guides are available inside the UI.
    # QA reports stay beside the ZIP, never inside the app folder.
    $zipPath = Join-Path $releaseRoot 'HPNet VBDLIS AIO Tool.zip'
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($appFolder, $zipPath, [IO.Compression.CompressionLevel]::Optimal, $true)
    & $python -X utf8 (Join-Path $projectRoot 'verify_release.py') --folder $appFolder --zip $zipPath
    if ($LASTEXITCODE -ne 0) { throw 'ZIP verification failed.' }
    # Publish one stable ZIP name, only after the new package is verified.
    # Search the release root and its immediate build-version directories only;
    # never recurse into _internal (base_library.zip is a required runtime file).
    $releaseBase = (Resolve-Path -LiteralPath (Join-Path $projectRoot 'release')).Path
    $publicZip = Join-Path $releaseBase 'HPNet VBDLIS AIO Tool.zip'
    $archiveDirectories = @((Get-Item -LiteralPath $releaseBase)) + @(Get-ChildItem -LiteralPath $releaseBase -Directory)
    $oldArchives = @()
    foreach ($directory in $archiveDirectories) {
        if ($directory.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing to clean a linked release directory.' }
        $oldArchives += @(Get-ChildItem -LiteralPath $directory.FullName -File | Where-Object {
            ($_.Name -eq 'HPNet VBDLIS AIO Tool.zip' -or $_.Name -like 'HPNET-VBDLIS-Tools-*.zip') -and $_.FullName -ne $zipPath
        })
    }
    Add-Type -AssemblyName Microsoft.VisualBasic
    foreach ($archive in $oldArchives) {
        $oldPath = [IO.Path]::GetFullPath($archive.FullName)
        if (-not $oldPath.StartsWith($releaseBase + '\', [StringComparison]::OrdinalIgnoreCase) -or
            ($archive.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Unsafe old archive path.' }
        Write-Host "RECYCLE_OLD_RELEASE_ZIP: $oldPath"
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($oldPath,
            [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
            [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin,
            [Microsoft.VisualBasic.FileIO.UICancelOption]::ThrowException)
    }
    Move-Item -LiteralPath $zipPath -Destination $publicZip
    Get-FileHash -LiteralPath $publicZip -Algorithm SHA256
    Write-Host "RELEASE_PASS: $publicZip"
} finally {
    $env:PYTHONPATH = $oldPythonPath
    $env:APPDATA = $oldAppData
    $env:QT_QPA_PLATFORM = $oldPlatform
    Set-Location -LiteralPath $originalLocation
}

param([string]$ReleaseId = (Get-Date -Format 'yyyy.MM.dd-HHmmss'))
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
if ($ReleaseId -notmatch '^[a-zA-Z0-9._-]+$') { throw 'ReleaseId chi duoc gom chu, so, dau cham, gach ngang.' }
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Can tao .venv va cai docs\REQUIREMENTS_BUILD.txt truoc.' }
$pythonVersion = (& $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($LASTEXITCODE -ne 0 -or $pythonVersion -ne '3.14') {
    throw "Build release bat buoc dung Python 3.14; .venv hien tai la Python $pythonVersion."
}
$releaseRoot = Join-Path $projectRoot "release\$ReleaseId"
$buildRoot = Join-Path $projectRoot "build\$ReleaseId"
if ((Test-Path -LiteralPath $releaseRoot) -or (Test-Path -LiteralPath $buildRoot)) {
    throw 'Thu muc phat hanh/build da ton tai. Chon ReleaseId moi; khong ghi de ban cu.'
}
$originalLocation = Get-Location
$oldPythonPath = $env:PYTHONPATH
$oldAppData = $env:APPDATA
$oldPlatform = $env:QT_QPA_PLATFORM
function Send-SafeItemToRecycleBin([IO.FileSystemInfo]$Item, [string]$AllowedParent) {
    $parent = [IO.Path]::GetFullPath($AllowedParent).TrimEnd('\')
    $target = [IO.Path]::GetFullPath($Item.FullName).TrimEnd('\')
    if (-not $target.StartsWith($parent + '\', [StringComparison]::OrdinalIgnoreCase) -or
        ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Unsafe cleanup target: $target" }
    Write-Host "RECYCLE_BUILD_ARTIFACT: $target"
    if ($Item.PSIsContainer) {
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($target,
            [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
            [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin,
            [Microsoft.VisualBasic.FileIO.UICancelOption]::ThrowException)
    } else {
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($target,
            [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
            [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin,
            [Microsoft.VisualBasic.FileIO.UICancelOption]::ThrowException)
    }
}
try {
    Set-Location -LiteralPath $projectRoot
    $env:PYTHONPATH = Join-Path $projectRoot 'src'
    $sharedRuntime = Join-Path $projectRoot 'src\nodes_tools\runtime'
    if (-not ((Test-Path -LiteralPath (Join-Path $sharedRuntime 'node.exe') -PathType Leaf) -and
              (Test-Path -LiteralPath (Join-Path $sharedRuntime 'node_modules\playwright\package.json') -PathType Leaf))) {
        throw 'Thiếu runtime Node/Playwright dùng chung. Chạy tools\restore_runtime.ps1 từ bản release sạch trước khi build.'
    }
    & (Join-Path $projectRoot 'tools\build_hpnet_launchers.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'HPNet launcher build failed.' }
    & $python -X utf8 (Join-Path $projectRoot 'run_tests.py')
    if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
    New-Item -ItemType Directory -Path $releaseRoot, $buildRoot | Out-Null
    Set-Location -LiteralPath (Join-Path $projectRoot 'src')
    & $python -X utf8 -m PyInstaller HPNET_VBDLIS_Tools.spec --noconfirm --distpath $releaseRoot --workpath $buildRoot
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }
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
    # Replace only the public ZIP in the release root. User-maintained archive
    # directories such as release\old build are outside this cleanup scope.
    $releaseBase = (Resolve-Path -LiteralPath (Join-Path $projectRoot 'release')).Path
    $publicZip = Join-Path $releaseBase 'HPNet VBDLIS AIO Tool.zip'
    $oldArchives = @(Get-ChildItem -LiteralPath $releaseBase -File | Where-Object {
        $_.Name -eq 'HPNet VBDLIS AIO Tool.zip' -or $_.Name -like 'HPNET-VBDLIS-Tools-*.zip'
    })
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
    $publicHash = Get-FileHash -LiteralPath $publicZip -Algorithm SHA256
    $buildBase = (Resolve-Path -LiteralPath (Join-Path $projectRoot 'build')).Path
    Send-SafeItemToRecycleBin (Get-Item -LiteralPath $buildRoot) $buildBase
    Send-SafeItemToRecycleBin (Get-Item -LiteralPath $releaseRoot) $releaseBase
    if ((Test-Path -LiteralPath $buildRoot) -or (Test-Path -LiteralPath $releaseRoot)) { throw 'Generated build cleanup failed.' }
    if (-not (Test-Path -LiteralPath $publicZip -PathType Leaf)) { throw 'Public release ZIP missing after publish.' }
    $publicHash
    Write-Host "RELEASE_PASS: $publicZip"
} finally {
    $env:PYTHONPATH = $oldPythonPath
    $env:APPDATA = $oldAppData
    $env:QT_QPA_PLATFORM = $oldPlatform
    Set-Location -LiteralPath $originalLocation
}

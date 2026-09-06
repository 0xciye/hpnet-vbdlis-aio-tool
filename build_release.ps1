param(
    [string]$ReleaseId = (Get-Date -Format 'yyyy.MM.dd-HHmmss'),
    [switch]$SkipDesktopCopy
)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$productName = 'HPNet VBDLIS AIO Tool'
$desktopTemp = $null
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
$oldBuildInfo = $env:SUITE_BUILD_INFO
function Send-SafeItemToRecycleBin([IO.FileSystemInfo]$Item, [string]$AllowedParent) {
    $parent = [IO.Path]::GetFullPath($AllowedParent).TrimEnd('\')
    $target = [IO.Path]::GetFullPath($Item.FullName).TrimEnd('\')
    if (-not $target.StartsWith($parent + '\', [StringComparison]::OrdinalIgnoreCase) -or
        ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Unsafe cleanup target: $target" }
    Write-Host "RECYCLE_BUILD_ARTIFACT: $target"
    if ($env:CI -eq 'true') {
        if ($Item.PSIsContainer) { [IO.Directory]::Delete($target, $true) } else { [IO.File]::Delete($target) }
        return
    }
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
    # Dọn sạch các thư mục runtime/ thừa trong từng tool (tàn dư kiến trúc cũ).
    # Chỉ có 1 runtime dùng chung tại src\nodes_tools\runtime\; các bản khác không được đóng gói.
    $staleRuntimePaths = @(
        'src\nodes_tools\Downloader\HPNet PDF Downloader - VNEID APP\runtime',
        'src\nodes_tools\Upload\HPNet Upload VB Du Thao - VNEID APP\runtime',
        'src\nodes_tools\Duyet\HPNet Duyet VB Du Thao - VNEID APP\runtime'
    )
    foreach ($rel in $staleRuntimePaths) {
        $stale = Join-Path $projectRoot $rel
        if (Test-Path -LiteralPath $stale -PathType Container) {
            Write-Host "REMOVING_STALE_RUNTIME: $stale"
            Remove-Item -LiteralPath $stale -Recurse -Force
        }
    }
    & $python -X utf8 (Join-Path $projectRoot 'run_tests.py')
    if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
    # Sync mẫu thông báo từ research/ vào src/template/ và cập nhật evidence.
    # Đây là nguồn thật duy nhất; bản trong src/ luôn được tạo lại khi build.
    & $python -X utf8 (Join-Path $projectRoot 'tools\sync_notice_template.py')
    if ($LASTEXITCODE -ne 0) { throw 'Notice template sync failed.' }
    New-Item -ItemType Directory -Path $releaseRoot, $buildRoot | Out-Null
    $commit = if ($env:GITHUB_SHA) { $env:GITHUB_SHA } else { (& git rev-parse HEAD).Trim() }
    $buildInfo = Join-Path $buildRoot 'build_info.json'
    @{ version=$ReleaseId; commit=$commit; repository='0xciye/hpnet-vbdlis-aio-tool' } |
        ConvertTo-Json | Set-Content -LiteralPath $buildInfo -Encoding utf8
    $env:SUITE_BUILD_INFO = $buildInfo
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
    $zipPath = Join-Path $releaseRoot "$productName.zip"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($appFolder, $zipPath, [IO.Compression.CompressionLevel]::Optimal, $true)
    & $python -X utf8 (Join-Path $projectRoot 'verify_release.py') --folder $appFolder --zip $zipPath
    if ($LASTEXITCODE -ne 0) { throw 'ZIP verification failed.' }
    # Publish one stable name only after the new package is fully verified.
    $releaseBase = (Resolve-Path -LiteralPath (Join-Path $projectRoot 'release')).Path
    $buildBase = (Resolve-Path -LiteralPath (Join-Path $projectRoot 'build')).Path
    $publicZip = Join-Path $releaseBase "$productName.zip"
    $oldArchives = @(Get-ChildItem -LiteralPath $releaseBase -File | Where-Object {
        $_.Name -like "$productName*.zip" -or $_.Name -like 'HPNET-VBDLIS-Tools-*.zip'
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

    $desktopZip = $null
    if (-not $SkipDesktopCopy) {
        $desktopBase = [Environment]::GetFolderPath('Desktop')
        if (-not (Test-Path -LiteralPath $desktopBase -PathType Container)) { throw 'Không tìm thấy thư mục Desktop.' }
        $desktopZip = Join-Path $desktopBase "$productName.zip"
        $desktopTemp = Join-Path $desktopBase ".$productName.copying.zip"
        Copy-Item -LiteralPath $publicZip -Destination $desktopTemp
        if ((Get-FileHash -LiteralPath $desktopTemp -Algorithm SHA256).Hash -ne $publicHash.Hash) {
            throw 'Bản sao Desktop không khớp SHA-256 với release vừa build.'
        }
        if (Test-Path -LiteralPath $desktopZip) {
            Send-SafeItemToRecycleBin (Get-Item -LiteralPath $desktopZip) $desktopBase
        }
        Move-Item -LiteralPath $desktopTemp -Destination $desktopZip
        $desktopTemp = $null
    }

    # A successful release supersedes every prior generated staging directory.
    foreach ($directory in @(Get-ChildItem -LiteralPath $buildBase -Directory | Where-Object { $_.FullName -ne $buildRoot })) {
        Send-SafeItemToRecycleBin $directory $buildBase
    }
    foreach ($directory in @(Get-ChildItem -LiteralPath $releaseBase -Directory | Where-Object { $_.FullName -ne $releaseRoot })) {
        Send-SafeItemToRecycleBin $directory $releaseBase
    }
    Send-SafeItemToRecycleBin (Get-Item -LiteralPath $buildRoot) $buildBase
    Send-SafeItemToRecycleBin (Get-Item -LiteralPath $releaseRoot) $releaseBase
    if (@(Get-ChildItem -LiteralPath $buildBase -Directory).Count -or @(Get-ChildItem -LiteralPath $releaseBase -Directory).Count) {
        throw 'Vẫn còn thư mục build cũ sau cleanup.'
    }
    if (-not (Test-Path -LiteralPath $publicZip -PathType Leaf) -or
        (-not $SkipDesktopCopy -and -not (Test-Path -LiteralPath $desktopZip -PathType Leaf))) {
        throw 'Thiếu ZIP mới trong release hoặc Desktop sau publish.'
    }
    $publicHash
    Write-Host "RELEASE_PASS: $publicZip"
    if ($desktopZip) { Write-Host "DESKTOP_COPY_PASS: $desktopZip" }
} finally {
    if ($desktopTemp -and (Test-Path -LiteralPath $desktopTemp -PathType Leaf)) { [IO.File]::Delete($desktopTemp) }
    $env:PYTHONPATH = $oldPythonPath
    $env:APPDATA = $oldAppData
    $env:QT_QPA_PLATFORM = $oldPlatform
    $env:SUITE_BUILD_INFO = $oldBuildInfo
    Set-Location -LiteralPath $originalLocation
}
